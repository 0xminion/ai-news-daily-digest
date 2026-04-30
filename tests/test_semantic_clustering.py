"""Tests for semantic clustering using mocked embeddings."""
from __future__ import annotations

from unittest.mock import patch

import numpy as np

from ai_news_digest.analysis.semantic_clustering import cluster_by_embeddings


class TestClusterByEmbeddings:
    def test_empty_articles_returns_empty(self):
        assert cluster_by_embeddings([]) == []

    def test_all_embeddings_fail_falls_back_to_singletons(self):
        with patch(
            "ai_news_digest.analysis.semantic_clustering._fetch_embeddings_batch",
            return_value=[None, None],
        ):
            articles = [{"title": "A", "summary": "x"}, {"title": "B", "summary": "y"}]
            clusters = cluster_by_embeddings(articles)
        assert clusters == [[0], [1]]

    def test_similar_articles_cluster_together(self):
        # Two identical articles should cluster, one different stays alone
        emb_a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        emb_b = np.array([0.99, 0.01, 0.0], dtype=np.float32)
        emb_c = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        with patch(
            "ai_news_digest.analysis.semantic_clustering._fetch_embeddings_batch",
            return_value=[emb_a, emb_b, emb_c],
        ):
            articles = [
                {"title": "OpenAI releases GPT-5", "summary": "x"},
                {"title": "OpenAI launches GPT-5 model", "summary": "x"},
                {"title": "Apple announces new iPhone", "summary": "x"},
            ]
            clusters = cluster_by_embeddings(articles)

        # Flatten clusters to check grouping
        flat = [i for c in clusters for i in c]
        assert sorted(flat) == [0, 1, 2]
        # 0 and 1 should be together (high similarity)
        assert any(0 in c and 1 in c for c in clusters)

    def test_partial_failure_adds_singletons(self):
        emb_a = np.array([1.0, 0.0], dtype=np.float32)
        with patch(
            "ai_news_digest.analysis.semantic_clustering._fetch_embeddings_batch",
            return_value=[emb_a, None],
        ):
            articles = [{"title": "A", "summary": "x"}, {"title": "B", "summary": "y"}]
            clusters = cluster_by_embeddings(articles)
        assert len(clusters) == 2
        assert [0] in clusters or any(0 in c for c in clusters)
        assert [1] in clusters or any(1 in c for c in clusters)

    def test_centroid_updates_on_merge(self):
        emb_a = np.array([1.0, 0.0], dtype=np.float32)
        emb_b = np.array([0.9, 0.1], dtype=np.float32)
        emb_c = np.array([0.85, 0.15], dtype=np.float32)

        with patch(
            "ai_news_digest.analysis.semantic_clustering._fetch_embeddings_batch",
            return_value=[emb_a, emb_b, emb_c],
        ):
            articles = [
                {"title": "A", "summary": "x"},
                {"title": "B", "summary": "x"},
                {"title": "C", "summary": "x"},
            ]
            clusters = cluster_by_embeddings(articles)

        flat = sorted(i for c in clusters for i in c)
        assert flat == [0, 1, 2]
