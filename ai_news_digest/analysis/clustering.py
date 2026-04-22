from __future__ import annotations

from collections import defaultdict
from rapidfuzz import fuzz, process

from ai_news_digest.config import CLUSTER_SIMILARITY_THRESHOLD
from ai_news_digest.storage.archive import normalize_title, normalize_url


def _best_representative(articles: list[dict]) -> dict:
    return max(
        articles,
        key=lambda a: (a.get('hn_points', 0), a.get('source_count', 1), a.get('ranking_score', 0)),
    ).copy()


def cluster_articles(articles: list[dict], threshold: int = CLUSTER_SIMILARITY_THRESHOLD) -> list[dict]:
    """Cluster articles with a two-pass approach: exact URL/title via dict (O(N)),
    then fuzzy title match against cluster representatives (O(N log C))."""
    # Pre-normalize
    normalized = []
    for article in articles:
        normalized.append({
            'article': article,
            'url': normalize_url(article.get('url')),
            'title': normalize_title(article.get('title')),
        })

    # Pass 1: exact URL grouping
    url_buckets: dict[str, list[int]] = defaultdict(list)
    loose = []
    for i, item in enumerate(normalized):
        if item['url']:
            url_buckets[item['url']].append(i)
        else:
            loose.append(i)

    # Pass 2: exact title grouping on remaining
    title_buckets: dict[str, list[int]] = defaultdict(list)
    still_loose = []
    for i in loose:
        if normalized[i]['title']:
            title_buckets[normalized[i]['title']].append(i)
        else:
            still_loose.append(i)

    # Convert exact buckets to clusters (singletons go back to loose)
    cluster_indices: list[list[int]] = []
    for indices in list(url_buckets.values()) + list(title_buckets.values()):
        if len(indices) > 1:
            cluster_indices.append(indices)
        else:
            still_loose.extend(indices)

    # Build rep titles for fuzzy matching
    rep_titles: list[str] = []
    for indices in cluster_indices:
        rep = _best_representative([normalized[i]['article'] for i in indices])
        rep_titles.append(normalize_title(rep.get('title', '')))

    # Pass 3: fuzzy match singletons against cluster reps or each other
    new_clusters: list[list[int]] = []
    for i in still_loose:
        item = normalized[i]
        matched = None
        # Fuzzy match against existing cluster reps (length-bounded)
        if item['title'] and rep_titles:
            candidates = [t for t in rep_titles if abs(len(t) - len(item['title'])) <= 10]
            if candidates:
                best = process.extractOne(item['title'], candidates, scorer=fuzz.ratio, score_cutoff=threshold)
                if best:
                    matched_idx = rep_titles.index(best[0])
                    cluster_indices[matched_idx].append(i)
                    # Rebuild rep for matched cluster
                    rep = _best_representative([normalized[j]['article'] for j in cluster_indices[matched_idx]])
                    rep_titles[matched_idx] = normalize_title(rep.get('title', ''))
                    matched = True

        if not matched:
            # Fuzzy match against newly formed singleton clusters
            for ci, nc in enumerate(new_clusters):
                other_title = normalize_title(normalized[nc[0]]['article'].get('title', ''))
                if (item['title'] and other_title and
                        abs(len(other_title) - len(item['title'])) <= 10 and
                        fuzz.ratio(item['title'], other_title) >= threshold):
                    nc.append(i)
                    matched = True
                    break

        if not matched:
            new_clusters.append([i])

    cluster_indices.extend(new_clusters)

    # Build final clusters
    result = []
    for idx, indices in enumerate(cluster_indices, start=1):
        cluster_articles_list = [normalized[i]['article'] for i in indices]
        sources = sorted({a.get('source', 'Unknown') for a in cluster_articles_list})
        rep = _best_representative(cluster_articles_list)
        rep['cluster_id'] = f'cluster-{idx}'
        rep['source_count'] = len(sources)
        rep['sources'] = sources
        rep['cluster_size'] = len(cluster_articles_list)
        result.append({
            'representative': rep,
            'articles': cluster_articles_list,
            'sources': sources,
            'cluster_size': len(cluster_articles_list),
        })
    return result
