from __future__ import annotations

from collections import defaultdict

from ai_news_digest.analysis.clustering import cluster_articles
from ai_news_digest.analysis.ranking import rank_clustered_articles
from ai_news_digest.analysis.trends import compute_trend_snapshot
from ai_news_digest.config import CROSS_DAY_DEDUP_DAYS, MAX_ARTICLES_TO_SUMMARIZE, logger
from ai_news_digest.storage.archive import exclude_cross_day_duplicates
from ai_news_digest.storage.topic_memory import load_topic_memory, save_topic_memory
from .hackernews import enrich_articles_with_hn
from .orthogonal import fetch_orthogonal_signal_articles
from .pages import fetch_page_articles
from .rss import fetch_rss_articles


RESEARCH_SOURCES = {'arXiv AI', 'arXiv ML', 'GitHub Blog AI/ML', 'Follow Builders / x', 'Follow Builders / podcasts', 'Follow Builders / blogs'}


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


def fetch_digest_inputs() -> dict:
    core_articles = []
    core_articles.extend(fetch_rss_articles())
    core_articles.extend(fetch_page_articles())
    research_articles = fetch_orthogonal_signal_articles()

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
    capped_research = _apply_source_caps(
        ranked_research,
        caps={'arXiv AI': 2, 'arXiv ML': 1, 'GitHub Blog AI/ML': 1},
        default_cap=2,
        limit=4,
    )

    save_topic_memory({
        'saved_at': trend_snapshot.get('daily_topic_counts', [{}])[-1].get('date'),
        'topic_counts': trend_snapshot.get('daily_topic_counts', [{}])[-1].get('counts', {}),
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
