from __future__ import annotations

from datetime import datetime, timezone

from ai_news_digest.analysis.trends import extract_topics
from ai_news_digest.config import SOURCE_TRUST_WEIGHTS
from ai_news_digest.config.topics import RESEARCH_SIGNAL_SOURCES

ORTHOGONAL_SOURCES = {'arXiv AI', 'arXiv ML', 'GitHub Blog AI/ML'}


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


def _trend_bucket_for_article(article: dict, trend_snapshot: dict | None) -> dict:
    if not trend_snapshot:
        return {}
    source = article.get('source', '')
    if source in RESEARCH_SIGNAL_SOURCES:
        return trend_snapshot.get('research_builder', {})
    return trend_snapshot.get('main_news', {})


def score_article(article: dict, trend_snapshot: dict | None = None, topic_memory: dict | None = None) -> float:
    return score_article_with_reasons(article, trend_snapshot=trend_snapshot, topic_memory=topic_memory)['score']


def score_article_with_reasons(article: dict, trend_snapshot: dict | None = None, topic_memory: dict | None = None) -> dict:
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
    orthogonal_penalty = -0.2 if source in ORTHOGONAL_SOURCES and article.get('source_count', 1) <= 1 and article.get('hn_points', 0) == 0 else 0.0

    topics = extract_topics(article)
    trend_bucket = _trend_bucket_for_article(article, trend_snapshot)
    heating_topics = {item['topic'] for item in trend_bucket.get('heating_up', [])}
    cooling_topics = {item['topic'] for item in trend_bucket.get('cooling_down', [])}
    trend_bonus = 0.35 if topics & heating_topics else 0.0
    trend_penalty = -0.15 if topics & cooling_topics else 0.0

    memory_bonus = 0.0
    if topic_memory:
        latest = (topic_memory.get('history') or [])[-1:] or []
        latest_counts = latest[0].get('topic_counts', {}) if latest else {}
        memory_bonus = min(sum(latest_counts.get(topic, 0) for topic in topics) / 20, 0.25)

    contributions = {
        'recency': round(recency * 0.35, 4),
        'source_trust': round(source_weight * 0.25, 4),
        'source_breadth': round(cluster_bonus * 0.15, 4),
        'hn_attention': round(hn_bonus * 0.15, 4),
        'trend_bonus': round(trend_bonus, 4),
        'trend_penalty': round(trend_penalty, 4),
        'topic_memory': round(memory_bonus, 4),
        'orthogonal_penalty': round(orthogonal_penalty, 4),
    }
    score = round(sum(contributions.values()), 4)

    reasons = []
    if contributions['source_breadth'] > 0.15:
        reasons.append(f"Multiple outlets clustered around it ({article.get('source_count', 1)} source(s)).")
    if contributions['hn_attention'] >= 0.2:
        reasons.append(f"Technical attention showed up on Hacker News ({article.get('hn_points', 0)} points / {article.get('hn_comments', 0)} comments).")
    if contributions['trend_bonus'] > 0:
        reasons.append(f"Matched a heating-up topic: {', '.join(sorted(topics & heating_topics))}.")
    if contributions['topic_memory'] > 0:
        reasons.append('This topic has been showing up across recent runs.')
    if contributions['orthogonal_penalty'] < 0:
        reasons.append('Solo research signal got a small penalty so it would not drown out the main news.')
    if not reasons:
        reasons.append('Strong enough overall score without one giant signal dominating it.')

    return {
        'score': score,
        'components': contributions,
        'reasons': reasons[:3],
    }


def rank_clustered_articles(clusters: list[dict], trend_snapshot: dict | None = None, topic_memory: dict | None = None) -> list[dict]:
    ranked = []
    for cluster in clusters:
        rep = cluster['representative']
        debug = score_article_with_reasons(rep, trend_snapshot=trend_snapshot, topic_memory=topic_memory)
        rep['ranking_score'] = debug['score']
        rep['ranking_debug'] = debug
        ranked.append(rep)
    ranked.sort(key=lambda item: (item.get('ranking_score', 0), item.get('hn_points', 0), item.get('source_count', 1)), reverse=True)
    return ranked
