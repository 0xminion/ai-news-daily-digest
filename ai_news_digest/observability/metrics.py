"""Observability metrics — lightweight in-process counters.

All functions are no-ops until an exporter is wired in.
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger("ai-digest.metrics")

_run_id: str | None = None
_start_ts: float = 0.0


def set_run_id(run_id: str) -> None:
    global _run_id
    _run_id = run_id
    logger.debug("run_id=%s", run_id)


def pipeline_start() -> None:
    global _start_ts
    _start_ts = time.time()
    logger.debug("pipeline_start")


def pipeline_success(duration: float | None = None) -> None:
    dur = duration if duration is not None else (time.time() - _start_ts)
    logger.info("pipeline_success duration=%.3fs", dur)


def fetch_latency(source: str, duration: float) -> None:
    logger.debug("fetch_latency source=%s duration=%.3fs", source, duration)


def articles_fetched(count: int) -> None:
    logger.debug("articles_fetched count=%d", count)


def fetch_failed(source: str, error: str) -> None:
    logger.warning("fetch_failed source=%s error=%s", source, error)


def cluster_count(count: int) -> None:
    logger.debug("cluster_count=%d", count)


def dedup_hit_rate(hits: int, evaluated: int) -> None:
    rate = hits / evaluated if evaluated else 0.0
    logger.debug("dedup_hit_rate %.2f%% (%d/%d)", rate * 100, hits, evaluated)
