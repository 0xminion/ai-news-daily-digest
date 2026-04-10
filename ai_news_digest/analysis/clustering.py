from __future__ import annotations

from rapidfuzz import fuzz

from ai_news_digest.config import CLUSTER_SIMILARITY_THRESHOLD
from ai_news_digest.storage.archive import normalize_title, normalize_url


def cluster_articles(articles: list[dict], threshold: int = CLUSTER_SIMILARITY_THRESHOLD) -> list[dict]:
    clusters = []
    for article in articles:
        article_url = normalize_url(article.get('url'))
        article_title = normalize_title(article.get('title'))
        matched = None
        for cluster in clusters:
            rep = cluster['representative']
            rep_url = normalize_url(rep.get('url'))
            rep_title = normalize_title(rep.get('title'))
            same_url = article_url and rep_url and article_url == rep_url
            similar_title = article_title and rep_title and fuzz.ratio(article_title, rep_title) >= threshold
            if same_url or similar_title:
                matched = cluster
                break
        if matched is None:
            matched = {'representative': article.copy(), 'articles': []}
            clusters.append(matched)
        matched['articles'].append(article)
        rep = matched['representative']
        if article.get('hn_points', 0) > rep.get('hn_points', 0):
            matched['representative'] = article.copy()
    for idx, cluster in enumerate(clusters, start=1):
        sources = sorted({item.get('source', 'Unknown') for item in cluster['articles']})
        rep = cluster['representative']
        rep['cluster_id'] = f'cluster-{idx}'
        rep['source_count'] = len(sources)
        rep['sources'] = sources
        rep['cluster_size'] = len(cluster['articles'])
        cluster['sources'] = sources
        cluster['cluster_size'] = len(cluster['articles'])
    return clusters
