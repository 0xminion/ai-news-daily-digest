from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from ai_news_digest.config import TREND_LOOKBACK_DAYS, TREND_TOPICS
from ai_news_digest.config.topics import RESEARCH_SIGNAL_SOURCES
from ai_news_digest.storage.archive import load_recent_report_payloads


def _article_text(article: dict) -> str:
    return ' '.join([
        str(article.get('title', '')),
        str(article.get('summary', '')),
        str(article.get('content', '')),
    ]).lower()


def extract_topics(article: dict) -> set[str]:
    text = _article_text(article)
    matched = set()
    for topic, patterns in TREND_TOPICS.items():
        if any(pattern.lower() in text for pattern in patterns):
            matched.add(topic)
    return matched


def count_topics(articles: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for article in articles:
        for topic in extract_topics(article):
            counts[topic] += 1
    return dict(counts)


def _safe_date(payload: dict) -> str:
    saved_at = payload.get('saved_at')
    if saved_at:
        try:
            return datetime.fromisoformat(saved_at.replace('Z', '+00:00')).date().isoformat()
        except ValueError:
            pass
    return 'unknown'


def _streak(counts: list[int]) -> int:
    streak = 0
    for value in reversed(counts):
        if value > 0:
            streak += 1
        else:
            break
    return streak


def _compute_section_snapshot(current_articles: list[dict], historical_payloads: list[dict], lookback_days: int) -> dict:
    day_rows = []
    for payload in sorted(historical_payloads, key=_safe_date):
        day_rows.append({'date': _safe_date(payload), 'counts': count_topics(payload.get('articles', []))})
    today = datetime.now(timezone.utc).date().isoformat()
    day_rows.append({'date': today, 'counts': count_topics(current_articles)})

    topic_names = set(TREND_TOPICS.keys())
    for row in day_rows:
        topic_names.update(row['counts'].keys())

    heating_up = []
    cooling_down = []
    for topic in topic_names:
        series = [row['counts'].get(topic, 0) for row in day_rows]
        current = series[-1] if series else 0
        previous = series[:-1]
        avg_previous = (sum(previous) / len(previous)) if previous else 0.0
        delta = current - avg_previous
        streak = _streak(series)
        entry = {
            'topic': topic,
            'current_count': current,
            'previous_average': round(avg_previous, 2),
            'delta': round(delta, 2),
            'streak': streak,
        }
        if current >= 2 and (avg_previous == 0 or delta >= 1):
            heating_up.append(entry)
        elif avg_previous >= 1 and (current == 0 or delta <= -1):
            cooling_down.append(entry)
    heating_up.sort(key=lambda item: (item['delta'], item['current_count'], item['streak']), reverse=True)
    cooling_down.sort(key=lambda item: (item['delta'], -item['current_count'], -item['streak']))
    return {
        'window_days': lookback_days,
        'heating_up': heating_up[:5],
        'cooling_down': cooling_down[:5],
        'daily_topic_counts': day_rows,
    }


def compute_trend_snapshot(current_articles: list[dict], lookback_days: int = TREND_LOOKBACK_DAYS) -> dict:
    history = load_recent_report_payloads(days=max(lookback_days - 1, 1), include_today=False)
    main_history = []
    research_history = []
    for payload in history:
        main_articles = []
        research_articles = []
        for article in payload.get('articles', []):
            if article.get('source') in RESEARCH_SIGNAL_SOURCES:
                research_articles.append(article)
            else:
                main_articles.append(article)
        main_history.append({'saved_at': payload.get('saved_at'), 'articles': main_articles})
        research_history.append({'saved_at': payload.get('saved_at'), 'articles': research_articles})

    main_current = [a for a in current_articles if a.get('source') not in RESEARCH_SIGNAL_SOURCES]
    research_current = [a for a in current_articles if a.get('source') in RESEARCH_SIGNAL_SOURCES]

    combined = _compute_section_snapshot(current_articles, history, lookback_days)
    return {
        'window_days': lookback_days,
        'main_news': _compute_section_snapshot(main_current, main_history, lookback_days),
        'research_builder': _compute_section_snapshot(research_current, research_history, lookback_days),
        'daily_topic_counts': combined.get('daily_topic_counts', []),
    }


def _format_section(label: str, snapshot: dict) -> list[str]:
    lines = [label]
    heating = snapshot.get('heating_up', [])
    cooling = snapshot.get('cooling_down', [])
    if heating:
        lines.append('Heating up:')
        for item in heating:
            lines.append(f"- {item.get('topic', 'Unknown')}: {item.get('current_count', '?')} article(s) today vs {item.get('previous_average', '?')} avg previously")
    if cooling:
        lines.append('Cooling down:')
        for item in cooling:
            lines.append(f"- {item.get('topic', 'Unknown')}: {item.get('current_count', '?')} article(s) today vs {item.get('previous_average', '?')} avg previously")
    return lines if len(lines) > 1 else []


def format_trend_context(snapshot: dict) -> str:
    if not snapshot:
        return ''
    lines = [f"Trend lookback: {snapshot.get('window_days', '?')} days"]
    lines.extend(_format_section('Main News Trend Watch:', snapshot.get('main_news', {})))
    return '\n'.join(lines) if len(lines) > 1 else 'No strong cross-day topic shifts detected.'
