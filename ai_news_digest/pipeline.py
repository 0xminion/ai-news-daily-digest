from __future__ import annotations

import os
from collections import defaultdict
import time

from ai_news_digest.analysis.clustering import cluster_articles
from ai_news_digest.analysis.ranking import rank_clustered_articles
from ai_news_digest.analysis.trends import compute_trend_snapshot, extract_topics
from ai_news_digest.analysis.semantic_clustering import cluster_by_embeddings
from ai_news_digest.analysis.relevance import filter_by_relevance
from ai_news_digest.config import CROSS_DAY_DEDUP_DAYS, MAX_ARTICLES_TO_SUMMARIZE, RESEARCH_SIGNALS_COUNT, RESEARCH_TOPIC_CAP_PER_TOPIC, logger, cfg_bool
from ai_news_digest.storage.unified import storage as _storage
from ai_news_digest.observability.metrics import set_run_id, fetch_latency, articles_fetched, fetch_failed, cluster_count, dedup_hit_rate, pipeline_start, pipeline_success
from ai_news_digest.sources.adapter import build_default_adapters, SourceAdapter
from ai_news_digest.sources.common import _utc_today
from ai_news_digest.sources.hackernews import enrich_articles_with_hn

def _apply_semantic_clustering(articles: list[dict]) -> list[dict]:
    if not cfg_bool("embedding.semantic_clustering_enabled"):
        return articles
    clusters = cluster_by_embeddings(articles)
    reps = []
    for indices in clusters:
        group = [articles[i] for i in indices]
        rep = max(group, key=lambda a: (a.get("hn_points", 0), len(a.get("sources", [a.get("source")]))))
        rep["cluster_size"] = len(group)
        rep["sources"] = sorted({a.get("source", "Unknown") for a in group})
        rep["source_count"] = len(rep["sources"])
        reps.append(rep)
    return reps

def _apply_source_caps(ranked: list[dict], caps: dict[str, int], default_cap: int = 5, limit: int = MAX_ARTICLES_TO_SUMMARIZE) -> list[dict]:
    used = defaultdict(int)
    selected = []
    for article in ranked:
        source = article.get("source", "Unknown")
        cap = caps.get(source, default_cap)
        if used[source] >= cap:
            continue
        selected.append(article)
        used[source] += 1
        if len(selected) >= limit:
            break
    return selected

def _infer_subtype(article: dict) -> str:
    source = (article.get("source") or "").lower()
    title = (article.get("title") or "").lower()
    if "arxiv" in source:
        return "paper"
    if "github" in source or "repo" in title:
        return "repo"
    if "docs" in title or "documentation" in title:
        return "product doc"
    return "product / launch"

def _infer_eli5(article: dict) -> str:
    subtype = article.get("subtype") or _infer_subtype(article)
    mapping = {
        "paper": "This is research work. It matters if the idea later turns into tools, products, or better models.",
        "repo": "This is code builders can use. It matters because people can actually try or build on it.",
        "builder feed": "This is a signal from people building things. It can hint at what is changing before headlines catch up.",
        "product doc": "This is documentation for a product or tool. It matters because it shows what is becoming usable in real life.",
        "product / launch": "This is a product or launch signal. It matters if it starts changing what people use or build.",
    }
    return mapping.get(subtype, "This is a technical clue that may matter later.")

def _apply_research_topic_caps(ranked: list[dict], limit: int = RESEARCH_SIGNALS_COUNT) -> list[dict]:
    selected = []
    topic_used = defaultdict(int)
    fallback_bucket = "Research / Other"
    overflow = []
    for article in ranked:
        topics = sorted(extract_topics(article)) or [fallback_bucket]
        article = dict(article)
        article["subtype"] = article.get("subtype") or _infer_subtype(article)
        article["eli5"] = article.get("eli5") or _infer_eli5(article)
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

def fetch_digest_inputs(adapters: list[SourceAdapter] | None = None) -> dict:
    run_id = _storage.start_run()
    set_run_id(run_id)
    pipeline_start()
    start_time = time.time()

    adapters = adapters or build_default_adapters()
    core_articles: list[dict] = []
    research_articles: list[dict] = []

    for adapter in adapters:
        source_start = time.time()
        try:
            articles = adapter.fetch()
            articles_fetched(len(articles))
            if adapter.name == "github_trending":
                research_articles.extend(articles)
                if articles:
                    logger.info("Added %d GitHub trending repos", len(articles))
            elif adapter.name == "orthogonal":
                research_articles.extend(articles)
            else:
                core_articles.extend(articles)
        except Exception as exc:
            logger.error("%s fetch failed: %s", adapter.name, exc)
            fetch_failed(adapter.name, str(exc))
        fetch_latency(adapter.name, time.time() - source_start)

    core_articles = enrich_articles_with_hn(core_articles)
    logger.info("Found %d core and %d research articles before dedup", len(core_articles), len(research_articles))

    core_articles, skipped_core = _storage.exclude_cross_day_duplicates(core_articles, days=CROSS_DAY_DEDUP_DAYS)
    research_articles, skipped_research = _storage.exclude_cross_day_duplicates(research_articles, days=CROSS_DAY_DEDUP_DAYS)
    dedup_hit_rate(hits=skipped_core + skipped_research, evaluated=len(core_articles) + len(research_articles) + skipped_core + skipped_research)

    # Semantic clustering (disabled by default — qwen3-embedding:0.6b on CPU adds
    # ~90s for 32 core articles with no quality improvement at typical daily volume)
    if cfg_bool("embedding.semantic_clustering_enabled"):
        core_articles = _apply_semantic_clustering(core_articles)
        if not os.environ.get("AI_DIGEST_SKIP_RESEARCH_EMBEDDING"):
            research_articles = _apply_semantic_clustering(research_articles)
    cluster_count(len(core_articles) + len(research_articles))

    # Relevance filtering
    core_articles = filter_by_relevance(core_articles)
    research_articles = filter_by_relevance(research_articles)

    all_articles = core_articles + research_articles
    trend_snapshot = compute_trend_snapshot(all_articles)
    topic_memory = _storage.load_topic_memory()

    core_clusters = cluster_articles(core_articles)
    research_clusters = cluster_articles(research_articles)

    ranked_core = rank_clustered_articles(core_clusters, trend_snapshot=trend_snapshot, topic_memory=topic_memory)
    ranked_research = rank_clustered_articles(research_clusters, trend_snapshot=trend_snapshot, topic_memory=topic_memory)

    capped_core = _apply_source_caps(
        ranked_core,
        caps={"Fortune": 3},
        default_cap=5,
        limit=MAX_ARTICLES_TO_SUMMARIZE,
    )
    source_capped_research = _apply_source_caps(
        ranked_research,
        caps={"arXiv AI": 2, "arXiv ML": 1, "GitHub Blog AI/ML": 1, "GitHub Trending": 3},
        default_cap=2,
        limit=max(8, RESEARCH_SIGNALS_COUNT + 3),
    )
    capped_research = _apply_research_topic_caps(source_capped_research, limit=RESEARCH_SIGNALS_COUNT)

    day_counts = trend_snapshot.get("daily_topic_counts", [])
    _storage.save_topic_memory(run_id, {
        "saved_at": day_counts[-1].get("date") if day_counts else _utc_today(),
        "topic_counts": day_counts[-1].get("counts", {}) if day_counts else {},
    })

    duration = time.time() - start_time
    pipeline_success(duration)
    _storage.end_run(run_id)

    return {
        "run_id": run_id,
        "main_articles": capped_core[:MAX_ARTICLES_TO_SUMMARIZE],
        "research_articles": capped_research,
        "trend_snapshot": trend_snapshot,
        "main_clusters": core_clusters,
        "research_clusters": research_clusters,
    }

def fetch_articles() -> tuple[list[dict], dict, list[dict]]:
    payload = fetch_digest_inputs()
    return payload["main_articles"], payload["trend_snapshot"], payload["main_clusters"]
