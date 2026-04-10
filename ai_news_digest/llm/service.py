from __future__ import annotations

import json
import re
from pathlib import Path

import requests

from ai_news_digest.analysis.trends import format_trend_context
from ai_news_digest.config import get_llm_settings, logger
from ai_news_digest.utils.retry import with_retry

INJECTION = re.compile(
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions|disregard\s+(all\s+)?(previous|prior)\s+instructions|forget\s+(all\s+)?(previous|prior)\s+instructions|new\s+instruction(s)?:|system\s*prompt\s*leak",
    re.IGNORECASE,
)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / 'prompts'

# Expected top-level keys in structured output
REQUIRED_DIGEST_KEYS = {'brief_rundown', 'highlights'}
OPTIONAL_DIGEST_KEYS = {'trend_watch', 'also_worth_knowing', 'research_builder_signals', 'weekly_preview'}


def _sanitize(text: str) -> str:
    return INJECTION.sub('[redacted]', text)


def _load_prompt_template(name: str) -> str:
    """Load a prompt template from the prompts/ directory."""
    path = PROMPTS_DIR / f'{name}.md'
    if not path.exists():
        raise FileNotFoundError(f'Prompt template not found: {path}')
    return path.read_text(encoding='utf-8')


def _serialize_articles(articles: list[dict]) -> str:
    return json.dumps(
        [
            {
                'title': _sanitize(a['title']),
                'summary': _sanitize(a.get('summary', ''))[:700],
                'content': _sanitize(a.get('content', ''))[:1500],
                'url': a['url'],
                'source': a['source'],
                'sources': a.get('sources', [a['source']]),
                'source_count': a.get('source_count', 1),
                'subtype': a.get('subtype', ''),
                'eli5': a.get('eli5', ''),
                'ranking_debug': a.get('ranking_debug', {}),
                'hacker_news': {
                    'points': a.get('hn_points', 0),
                    'comments': a.get('hn_comments', 0),
                    'discussion_url': a.get('hn_discussion_url', ''),
                },
                'ranking_score': a.get('ranking_score', 0),
            }
            for a in articles
        ],
        indent=2,
    )


def _build_prompt(main_articles: list[dict], research_articles: list[dict], trend_snapshot: dict | None = None, weekly_preview: str = '') -> str:
    trend_context = format_trend_context(trend_snapshot or {}) or 'No strong cross-day topic shifts detected.'
    template = _load_prompt_template('daily')
    # Use replace() instead of format() to avoid KeyError when article content contains { or }
    return (
        template
        .replace('{main_articles_json}', _serialize_articles(main_articles))
        .replace('{research_articles_json}', _serialize_articles(research_articles))
        .replace('{trend_context}', trend_context)
        .replace('{weekly_preview}', weekly_preview or 'No weekly preview available.')
    )


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith('```'):
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
        cleaned = re.sub(r'\n?```\s*$', '', cleaned)
    return json.loads(cleaned)


def _validate_digest(data: dict) -> dict:
    """Validate and normalize structured digest output."""
    if not isinstance(data, dict):
        raise ValueError(f'Expected dict, got {type(data).__name__}')

    missing = REQUIRED_DIGEST_KEYS - set(data.keys())
    if missing:
        raise ValueError(f'Missing required keys: {missing}')

    # Normalize highlights to list
    if isinstance(data.get('highlights'), str):
        data['highlights'] = [{'headline': data['highlights'], 'summary': '', 'source': '', 'url': ''}]

    # Ensure lists for array fields
    for key in ['also_worth_knowing', 'research_builder_signals', 'weekly_preview']:
        if key not in data:
            data[key] = []
        elif not isinstance(data[key], list):
            data[key] = [data[key]]

    return data


def _structured_to_text(data: dict) -> str:
    """Convert structured JSON digest back to text format for backward compat."""
    lines = []

    lines.append('Brief Rundown:')
    lines.append(data.get('brief_rundown', ''))
    lines.append('')

    # Trend watch
    trend = data.get('trend_watch')
    if trend and isinstance(trend, dict):
        main_trend = trend.get('main_news', {})
        if main_trend.get('heating_up') or main_trend.get('cooling_down'):
            lines.append('Trend Watch:')
            lines.append('Main News Trend Watch:')
            if main_trend.get('heating_up'):
                lines.append('Heating Up:')
                for item in main_trend['heating_up']:
                    lines.append(f"- {item.get('topic', '')} — {item.get('why', '')}")
            if main_trend.get('cooling_down'):
                lines.append('Cooling Down:')
                for item in main_trend['cooling_down']:
                    lines.append(f"- {item.get('topic', '')} — {item.get('why', '')}")
            lines.append('')

    # Highlights
    lines.append('Highlights:')
    for idx, h in enumerate(data.get('highlights', []), 1):
        lines.append(f"{idx}. {h.get('headline', '')}")
        if h.get('summary'):
            lines.append(h['summary'])
        if h.get('source') and h.get('url'):
            lines.append(f"Source: {h['source']} ({h['url']})")
        lines.append('')

    # Also worth knowing
    also = data.get('also_worth_knowing', [])
    if also:
        lines.append('Also Worth Knowing:')
        for item in also:
            title = item.get('headline', '')
            source = item.get('source', '')
            url = item.get('url', '')
            lines.append(f"- {title} | {source} ({url})")
        lines.append('')

    # Research signals
    research = data.get('research_builder_signals', [])
    if research:
        lines.append('Research / Builder Signals:')
        for item in research:
            subtype = item.get('subtype', '')
            headline = item.get('headline', '')
            source = item.get('source', '')
            url = item.get('url', '')
            prefix = f"[{subtype}] " if subtype else ''
            lines.append(f"- {prefix}{headline} | {source} ({url})")
        lines.append('')

    # Weekly preview
    weekly = data.get('weekly_preview', [])
    if weekly:
        lines.append('Weekly Preview:')
        for bullet in weekly:
            lines.append(f"- {bullet}")

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# LLM provider calls with retry
# ---------------------------------------------------------------------------

@with_retry(max_attempts=3, delay=5.0, backoff=2.0, exceptions=(requests.RequestException, RuntimeError, json.JSONDecodeError))
def _ollama(prompt: str, settings: dict) -> str:
    response = requests.post(
        f"{settings['ollama_host']}/api/generate",
        json={'model': settings['model'], 'prompt': prompt, 'stream': False},
        timeout=settings['timeout'],
    )
    response.raise_for_status()
    result = response.json().get('response', '').strip()
    if not result:
        raise RuntimeError('Ollama returned empty response')
    return result


@with_retry(max_attempts=3, delay=5.0, backoff=2.0, exceptions=(requests.RequestException, RuntimeError, json.JSONDecodeError))
def _openai_compatible(prompt: str, settings: dict) -> str:
    provider = settings['provider']
    api_base = settings['api_base'] or {'openai': 'https://api.openai.com/v1', 'openrouter': 'https://openrouter.ai/api/v1'}[provider]
    headers = {'Authorization': f"Bearer {settings[f'{provider}_api_key']}", 'Content-Type': 'application/json'}
    if provider == 'openrouter':
        headers['HTTP-Referer'] = 'https://github.com/0xminion/ai-news-daily-digest'
        headers['X-Title'] = 'ai-news-daily-digest'
    response = requests.post(
        f"{api_base}/chat/completions",
        headers=headers,
        json={
            'model': settings['model'],
            'messages': [
                {'role': 'system', 'content': 'You create clean, accurate AI news digests. Always respond with valid JSON.'},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': 0.2,
            'max_tokens': settings['max_tokens'],
            'response_format': {'type': 'json_object'},
        },
        timeout=settings['timeout'],
    )
    response.raise_for_status()
    result = response.json()['choices'][0]['message']['content'].strip()
    if not result:
        raise RuntimeError('OpenAI returned empty response')
    return result


@with_retry(max_attempts=3, delay=5.0, backoff=2.0, exceptions=(requests.RequestException, RuntimeError, json.JSONDecodeError))
def _anthropic(prompt: str, settings: dict) -> str:
    response = requests.post(
        f"{settings['api_base'] or 'https://api.anthropic.com'}/v1/messages",
        headers={'x-api-key': settings['anthropic_api_key'], 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
        json={
            'model': settings['model'],
            'max_tokens': settings['max_tokens'],
            'temperature': 0.2,
            'system': 'You create clean, accurate AI news digests. Always respond with valid JSON.',
            'messages': [{'role': 'user', 'content': prompt}],
        },
        timeout=settings['timeout'],
    )
    response.raise_for_status()
    data = response.json()
    result = '\n'.join(block.get('text', '') for block in data.get('content', []) if block.get('type') == 'text').strip()
    if not result:
        raise RuntimeError('Anthropic returned empty response')
    return result


# ---------------------------------------------------------------------------
# Main summarize function
# ---------------------------------------------------------------------------

def summarize(main_articles: list[dict], trend_snapshot: dict | None = None, research_articles: list[dict] | None = None, weekly_preview: str = '') -> str:
    if not main_articles and not research_articles:
        return _quiet_day_message()
    research_articles = research_articles or []
    settings = get_llm_settings()
    prompt = _build_prompt(main_articles, research_articles, trend_snapshot, weekly_preview)
    logger.info(
        'Sending %d main articles and %d research articles to %s (%s)...',
        len(main_articles),
        len(research_articles),
        settings['provider'],
        settings['model'],
    )

    if settings['provider'] == 'ollama':
        raw = _ollama(prompt, settings)
    elif settings['provider'] in {'openai', 'openrouter'}:
        raw = _openai_compatible(prompt, settings)
    elif settings['provider'] == 'anthropic':
        raw = _anthropic(prompt, settings)
    else:
        raise ValueError(f"Unsupported LLM provider '{settings['provider']}'")

    # Parse structured JSON output
    try:
        parsed = _extract_json(raw)
        validated = _validate_digest(parsed)
        logger.info('Structured digest parsed successfully (%d highlights, %d research signals)',
                    len(validated.get('highlights', [])),
                    len(validated.get('research_builder_signals', [])))
        # Save structured JSON alongside text for archive
        return _structured_to_text(validated)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning('Structured parse failed (%s), falling back to raw text', exc)
        # Fallback: return raw text for backward-compatible section parsing
        if not raw:
            raise RuntimeError('LLM provider returned empty response')
        return raw


def _quiet_day_message() -> str:
    return 'Brief Rundown:\nQuiet day in AI news — nothing major from our tracked sources in the last 24 hours.\n\nHighlights:\nNo highlights today.'
