from __future__ import annotations

from datetime import datetime, timezone

from ai_news_digest.config import SOURCE_TRUST_WEIGHTS
from ai_news_digest.analysis.trends import extract_topics


def _parse_date(value: str | None):
    if not value or value == 'Unknown':
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def score_article(article: dict, trend_snapshot: dict | None = None, topic_memory: dict | None = None) -> float:
    published = _parse_date(article.get('published'))
    now = datetime.now(timezone.utc)
    recency = 0.0
    if published is not None:
        hours = max((now - published).total_seconds() / 3600, 0)
        recency = max(0.0, 1 - min(hours / 48, 1))
    source = article.get('source', '')
    source_weight = SOURCE_TRUST_WEIGHTS.get(source, 0.75)
    cluster_bonus = min(article.get('source_count', 1) / 4, 1)
    hn_bonus = min(article.get('hn_points', 0) / 250, 1) * 0.8 + min(article.get('hn_comments', 0) / 120, 1) * 0.4
    orthogonal_penalty = -0.2 if source in {'arXiv AI', 'arXiv ML', 'GitHub Blog AI/ML'} and article.get('source_count', 1) <= 1 and article.get('hn_points', 0) == 0 else 0.0
    topics = extract_topics(article)
    heating_topics = {item['topic'] for item in (trend_snapshot or {}).get('heating_up', [])}
    cooling_topics = {item['topic'] for item in (trend_snapshot or {}).get('cooling_down', [])}
    trend_bonus = 0.35 if topics & heating_topics else 0.0
    trend_penalty = -0.15 if topics & cooling_topics else 0.0
    memory_bonus = 0.0
    if topic_memory:
        latest = (topic_memory.get('history') or [])[-1:] or []
        latest_counts = latest[0].get('topic_counts', {}) if latest else {}
        memory_bonus = min(sum(latest_counts.get(topic, 0) for topic in topics) / 20, 0.25)
    return round((recency * 0.35) + (source_weight * 0.25) + (cluster_bonus * 0.15) + (hn_bonus * 0.15) + trend_bonus + trend_penalty + memory_bonus + orthogonal_penalty, 4)


def rank_clustered_articles(clusters: list[dict], trend_snapshot: dict | None = None, topic_memory: dict | None = None) -> list[dict]:
    ranked = []
    for cluster in clusters:
        rep = cluster['representative']
        rep['ranking_score'] = score_article(rep, trend_snapshot=trend_snapshot, topic_memory=topic_memory)
        ranked.append(rep)
    ranked.sort(key=lambda item: (item.get('ranking_score', 0), item.get('hn_points', 0), item.get('source_count', 1)), reverse=True)
    return ranked
