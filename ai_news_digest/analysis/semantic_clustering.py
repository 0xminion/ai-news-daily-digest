"""Semantic clustering using Ollama embeddings.

Clusters articles by cosine similarity of title+snippet embeddings.
Model: qwen3-embedding:0.6b (or configured embedding.model).
"""
from __future__ import annotations

import logging

import numpy as np
import requests

from ai_news_digest.config.yaml_loader import cfg_str, get_config_value

logger = logging.getLogger("ai-digest")


def _embedding_url() -> str:
    host = str(get_config_value("embedding", "host") or cfg_str("llm.ollama_host")).rstrip("/")
    return f"{host}/api/embed"


def _embedding_model() -> str:
    return str(get_config_value("embedding", "model") or "qwen3-embedding:0.6b")


def _embedding_threshold() -> float:
    val = get_config_value("embedding", "similarity_threshold")
    return float(val) if val is not None else 0.85


def _fetch_embeddings_batch(texts: list[str]) -> list[np.ndarray | None]:
    """Fetch embeddings for a batch of texts. Returns list aligned with input."""
    try:
        resp = requests.post(
            _embedding_url(),
            json={"model": _embedding_model(), "input": [t[:512] for t in texts]},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("embeddings")
        if embeddings and len(embeddings) == len(texts):
            return [np.array(e, dtype=np.float32) for e in embeddings]
    except Exception as exc:
        logger.warning("Embedding batch failed (%d texts): %s", len(texts), exc)
    return [None] * len(texts)


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(dot / norm) if norm > 0 else 0.0


def cluster_by_embeddings(articles: list[dict]) -> list[list[int]]:
    """Return list of clusters, each cluster is a list of article indices."""
    if not articles:
        return []

    threshold = _embedding_threshold()
    texts = []
    for a in articles:
        title = (a.get("title") or "").strip()
        snippet = (a.get("text") or a.get("summary") or "").strip()[:256]
        texts.append(f"{title}\n{snippet}")

    logger.info("Fetching embeddings for %d articles (%s)", len(articles), _embedding_model())
    embeddings: list[np.ndarray | None] = [None] * len(texts)
    batch_size = int(get_config_value("embedding", "batch_size") or 32)
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i : i + batch_size]
        batch_embs = _fetch_embeddings_batch(batch_texts)
        for j, emb in enumerate(batch_embs):
            embeddings[i + j] = emb

    valid_indices = [i for i, e in enumerate(embeddings) if e is not None]
    if not valid_indices:
        logger.warning("No embeddings returned; falling back to singleton clusters")
        return [[i] for i in range(len(articles))]

    clusters: list[list[int]] = []
    centroids: list[np.ndarray] = []

    for i in valid_indices:
        emb = embeddings[i]  # type: ignore[arg-type]
        best_idx = -1
        best_sim = -1.0
        for cidx, centroid in enumerate(centroids):
            sim = _cosine_sim(emb, centroid)
            if sim > best_sim:
                best_sim = sim
                best_idx = cidx
        if best_sim >= threshold:
            clusters[best_idx].append(i)
            # Update centroid as mean of cluster embeddings
            members = [embeddings[j] for j in clusters[best_idx]]
            centroids[best_idx] = np.mean(members, axis=0)  # type: ignore[assignment]
        else:
            clusters.append([i])
            centroids.append(emb)

    # Add back articles that failed embedding as singletons
    failed = [i for i, e in enumerate(embeddings) if e is None]
    for i in failed:
        clusters.append([i])

    return clusters
