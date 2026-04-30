from __future__ import annotations

from ai_news_digest.analysis.weekly import build_weekly_highlights_payload
from ai_news_digest.config import OUTPUT_MODE, RESEARCH_SIGNALS_COUNT, USER_AGENT, get_llm_settings, get_telegram_destinations, logger, validate_config
from ai_news_digest.llm import AgentSummarizationRequired, summarize
from ai_news_digest.output.telegram import _format_digest, render_weekly_highlights, send_digest, send_weekly_report
from ai_news_digest.pipeline import fetch_digest_inputs
from ai_news_digest.storage.archive import prune_old_reports, save_daily_report, save_weekly_report


from ai_news_digest.storage.sqlite_store import migrate_from_json
from ai_news_digest.config import STATE_DIR

# Lazy migration on first import — only once per process
import threading
_migration_done = False
_migration_lock = threading.Lock()


def _lazy_migrate():
    global _migration_done
    if _migration_done:
        return
    with _migration_lock:
        if _migration_done:
            return
        try:
            migrate_from_json(STATE_DIR)
        except Exception:
            pass
        _migration_done = True


_lazy_migrate()

def _check_ollama() -> None:
    llm = get_llm_settings()
    if llm['provider'] != 'ollama':
        return
    try:
        import requests
        resp = requests.get(f"{llm['ollama_host']}/api/tags", timeout=5, headers={'User-Agent': USER_AGENT})
        if resp.status_code != 200:
            logger.warning('Ollama at %s returned status %s — summarization may fail.', llm['ollama_host'], resp.status_code)
    except Exception as exc:
        logger.warning('Cannot reach Ollama at %s (%s) — summarization may fail.', llm['ollama_host'], exc)


def run_daily(deliver: bool | None = None) -> int:
    if deliver is None:
        deliver = OUTPUT_MODE != "stdout"
    validate_config(skip_telegram=not deliver)
    _check_ollama()
    payload = fetch_digest_inputs()
    try:
        summary = summarize(
            payload['main_articles'],
            research_articles=payload['research_articles'],
        )
    except AgentSummarizationRequired as exc:
        logger.info('Agent summarization required for daily digest')
        print(f"\n{'='*60}")
        print('AGENT SUMMARIZATION REQUIRED')
        print(f"{'='*60}")
        print(f'Prompt saved to: {exc.prompt_path}')
        print('Please generate the structured JSON digest and save it to:')
        print(f'  {exc.response_path}')
        print(f"\nThen re-run: python3 scripts/daily.py{' --telegram' if deliver else ''}")
        print(f"{'='*60}\n")
        return 2
    from ai_news_digest.analysis.entities import extract_and_record_entities
    prune_old_reports()
    save_daily_report(
        summary,
        payload['main_articles'] + payload['research_articles'],
        trends=payload['trend_snapshot'],
        clusters=payload['main_clusters'] + payload['research_clusters'],
    )
    extract_and_record_entities(payload['run_id'], summary)
    if deliver:
        ok = send_digest(summary, destinations=get_telegram_destinations())
        return 0 if ok else 1
    # stdout mode — print formatted digest without Telegram
    messages = _format_digest(summary)
    for msg in messages:
        print(msg)
    return 0


def _fallback_weekly_payload_from_daily(payload: dict) -> dict:
    return {
        'window_days': 7,
        'executive_summary': 'This fallback weekly view is built from today\u2019s run so you can inspect structure before a full week of archives exists.',
        'highlights_of_the_week': [
            {
                'headline': article['title'],
                'source': article['source'],
                'url': article['url'],
                'why_it_matters': f"Representative daily sample item with ranking score {article.get('ranking_score', 0)}.",
                'eli5': 'ELI5: This story kept bubbling up, so it is probably worth paying attention to.',
                'confidence': 'Medium confidence',
            }
            for article in payload.get('main_articles', [])[:3]
        ],
        'trending_directions': [],
        'research_focus': [],
        'research_builder_signals': [
            {
                'headline': article['title'],
                'source': article['source'],
                'subtype': 'paper' if 'arXiv' in article['source'] else 'product / launch',
                'confidence': 'Early signal',
                'why_it_matters': 'Research / builder signal sample pulled from the current live run.',
                'eli5': 'ELI5: This is a technical or builder-side clue that may matter later even if it is not the biggest news item today.',
            }
            for article in payload.get('research_articles', [])[:RESEARCH_SIGNALS_COUNT]
        ],
        'missed_but_emerging': [
            {
                'headline': article['title'],
                'source': article['source'],
                'url': article['url'],
                'subtype': 'product / launch',
                'confidence': 'Early signal',
                'why_now': 'It is not dominant yet, but it is showing up often enough to watch.',
                'eli5': 'ELI5: This is a smaller story that could grow into something bigger soon.',
            }
            for article in payload.get('main_articles', [])[3:5]
        ],
    }


def _ensure_weekly_payload(payload: dict) -> dict:
    weekly_payload = build_weekly_highlights_payload(days=7)
    if weekly_payload.get('highlights_of_the_week'):
        return weekly_payload
    return _fallback_weekly_payload_from_daily(payload)


def build_daily_sample() -> tuple[dict, str]:
    payload = fetch_digest_inputs()
    text = _render_sample_daily(payload)
    return payload, text


def _render_sample_daily(payload: dict) -> str:
    main_articles = payload['main_articles']
    research_articles = payload['research_articles']
    lines = [
        'BRIEF RUNDOWN:',
        'This is a layout/sample render for structure checking. Main news stays separate from research/builder signals.',
        '',
    ]
    lines.append('HIGHLIGHTS:')
    for idx, article in enumerate(main_articles[:5], start=1):
        lines.append(f"{idx}. {article['title']}")
        lines.append(f"Representative score: {article.get('ranking_score', 0)}")
        lines.append(f"Source: {article['source']} ({article['url']})")
        lines.append('')
    lines.append('ALSO WORTH KNOWING:')
    for article in main_articles[5:9]:
        lines.append(f"- {article['title']} | {article['source']} ({article['url']})")
    if research_articles:
        lines.append('')
        lines.append('RESEARCH / BUILDER SIGNALS:')
        for article in research_articles[:RESEARCH_SIGNALS_COUNT]:
            subtype = article.get('subtype', 'signal')
            lines.append(f"- [{subtype}] {article['title']} | {article['source']} ({article['url']})")
    return '\n'.join(lines)


def build_weekly_sample() -> tuple[dict, str]:
    payload = _ensure_weekly_payload(fetch_digest_inputs())
    text = render_weekly_highlights(payload)
    return payload, text


def run_weekly(deliver: bool | None = None) -> int:
    if deliver is None:
        deliver = OUTPUT_MODE != "stdout"
    validate_config(skip_telegram=not deliver)
    try:
        payload, text = build_weekly_sample()
    except AgentSummarizationRequired as exc:
        logger.info('Agent summarization required for weekly digest')
        print(f"\n{'='*60}")
        print('AGENT SUMMARIZATION REQUIRED')
        print(f"{'='*60}")
        print(f'Prompt saved to: {exc.prompt_path}')
        print('Please generate the structured JSON digest and save it to:')
        print(f'  {exc.response_path}')
        print(f"\nThen re-run: python3 scripts/weekly.py{' --telegram' if deliver else ''}")
        print(f"{'='*60}\n")
        return 2
    save_weekly_report(payload, text)
    if deliver:
        ok = send_weekly_report(text, destinations=get_telegram_destinations())
        return 0 if ok else 1
    print(text)
    return 0
