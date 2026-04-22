from __future__ import annotations

from collections import defaultdict

from ai_news_digest.analysis.clustering import cluster_articles
from ai_news_digest.analysis.ranking import rank_clustered_articles
from ai_news_digest.analysis.trends import compute_trend_snapshot, extract_topics
from ai_news_digest.config import CROSS_DAY_DEDUP_DAYS, MAX_ARTICLES_TO_SUMMARIZE, RESEARCH_SIGNALS_COUNT, RESEARCH_TOPIC_CAP_PER_TOPIC, logger
from ai_news_digest.storage.archive import exclude_cross_day_duplicates
from ai_news_digest.storage.topic_memory import load_topic_memory, save_topic_memory
from .github_trending import fetch_github_trending
from .hackernews import enrich_articles_with_hn
from .orthogonal import fetch_orthogonal_signal_articles
from .pages import fetch_page_articles
from .rss import fetch_rss_articles


RESEARCH_SOURCES = {'arXiv AI', 'arXiv ML', 'GitHub Blog AI/ML', 'GitHub Trending', 'Follow Builders / x', 'Follow Builders / podcasts', 'Follow Builders / blogs'}


def _apply_source_caps(ranked: list[dict], caps: dict[str, int], default_cap: int = 5, limit: int = MAX_ARTICLES_TO_SUMMARIZE) -> list[dict]:
    used = defaultdict(int)
    selected = []
    for article in ranked:
        source = article.get('source', 'Unknown')
        cap = caps.get(source, default_cap)
        if used[source] >= cap:
            continue
        selected.append(article)
        used[source] += 1
        if len(selected) >= limit:
            break
    return selected


def _infer_subtype(article: dict) -> str:
    source = (article.get('source') or '').lower()
    title = (article.get('title') or '').lower()
    url = (article.get('url') or '').lower()
    if 'arxiv' in source:
        return 'paper'
    if 'github' in source or 'repo' in title or 'repository' in title:
        return 'repo'
    if 'follow builders' in source:
        return 'builder feed'
    if 'docs' in title or 'documentation' in title or 'docs.' in url or '/docs' in url:
        return 'product doc'
    return 'product / launch'


def _infer_eli5(article: dict) -> str:
    subtype = article.get('subtype') or _infer_subtype(article)
    mapping = {
        'paper': 'This is research work. It matters if the idea later turns into tools, products, or better models.',
        'repo': 'This is code builders can use. It matters because people can actually try or build on it.',
        'builder feed': 'This is a signal from people building things. It can hint at what is changing before headlines catch up.',
        'product doc': 'This is documentation for a product or tool. It matters because it shows what is becoming usable in real life.',
        'product / launch': 'This is a product or launch signal. It matters if it starts changing what people use or build.',
    }
    return mapping.get(subtype, 'This is a technical clue that may matter later even if it is not the biggest headline today.')


def _apply_research_topic_caps(ranked: list[dict], limit: int = RESEARCH_SIGNALS_COUNT) -> list[dict]:
    selected = []
    topic_used = defaultdict(int)
    fallback_bucket = 'Research / Other'
    overflow = []
    for article in ranked:
        topics = sorted(extract_topics(article)) or [fallback_bucket]
        article = dict(article)
        article['subtype'] = article.get('subtype') or _infer_subtype(article)
        article['eli5'] = article.get('eli5') or _infer_eli5(article)
        if any(topic_used[topic] >= RESEARCH_TOPIC_CAP_PER_TOPIC for topic in topics):
            overflow.append(article)
            continue
        selected.append(article)
        for topic in topics:
            topic_used[topic] += 1
        if len(selected) >= limit:
            return selected

    for article in overflow:
        selected.append(article)
        if len(selected) >= limit:
            break
    return selected


def fetch_digest_inputs() -> dict:
    core_articles = []
    core_articles.extend(fetch_rss_articles())
    core_articles.extend(fetch_page_articles())

    # Research/builder signals from orthogonal sources
    research_articles = fetch_orthogonal_signal_articles()

    # GitHub trending (3 fast-moving AI repos daily)
    trending_articles = fetch_github_trending(top_n=3)
    if trending_articles:
        research_articles.extend(trending_articles)
        logger.info('Added %d GitHub trending repos to research signals', len(trending_articles))

    core_articles = enrich_articles_with_hn(core_articles)
    logger.info('Found %d core AI articles and %d research/builder signal articles before cross-day dedup', len(core_articles), len(research_articles))

    core_articles, skipped_core = exclude_cross_day_duplicates(core_articles, days=CROSS_DAY_DEDUP_DAYS)
    research_articles, skipped_research = exclude_cross_day_duplicates(research_articles, days=CROSS_DAY_DEDUP_DAYS)
    if skipped_core:
        logger.info('Cross-day dedup skipped %d core article(s)', skipped_core)
    if skipped_research:
        logger.info('Cross-day dedup skipped %d research article(s)', skipped_research)

    all_articles = core_articles + research_articles
    trend_snapshot = compute_trend_snapshot(all_articles)
    topic_memory = load_topic_memory()

    core_clusters = cluster_articles(core_articles)
    research_clusters = cluster_articles(research_articles)

    ranked_core = rank_clustered_articles(core_clusters, trend_snapshot=trend_snapshot, topic_memory=topic_memory)
    ranked_research = rank_clustered_articles(research_clusters, trend_snapshot=trend_snapshot, topic_memory=topic_memory)

    capped_core = _apply_source_caps(
        ranked_core,
        caps={'Fortune': 3},
        default_cap=5,
        limit=MAX_ARTICLES_TO_SUMMARIZE,
    )
    source_capped_research = _apply_source_caps(
        ranked_research,
        caps={'arXiv AI': 2, 'arXiv ML': 1, 'GitHub Blog AI/ML': 1, 'GitHub Trending': 3},
        default_cap=2,
        limit=max(8, RESEARCH_SIGNALS_COUNT + 3),
    )
    capped_research = _apply_research_topic_caps(source_capped_research, limit=RESEARCH_SIGNALS_COUNT)

    day_counts = trend_snapshot.get('daily_topic_counts', [])
    save_topic_memory({
        'saved_at': day_counts[-1].get('date') if day_counts else _utc_now().isoformat()[:10],
        'topic_counts': day_counts[-1].get('counts', {}) if day_counts else {},
    })

    return {
        'main_articles': capped_core[:MAX_ARTICLES_TO_SUMMARIZE],
        'research_articles': capped_research,
        'trend_snapshot': trend_snapshot,
        'main_clusters': core_clusters,
        'research_clusters': research_clusters,
    }


def fetch_articles() -> tuple[list[dict], dict, list[dict]]:
    payload = fetch_digest_inputs()
    return payload['main_articles'], payload['trend_snapshot'], payload['main_clusters']
