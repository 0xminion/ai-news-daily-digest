"""Source adapter protocol and implementations.

Provides a uniform interface over heterogeneous fetch functions so the pipeline
can treat RSS, page scrapers, orthogonal feeds, and GitHub trending identically.
"""
from __future__ import annotations

from typing import Protocol

from ai_news_digest.config import RSS_FEEDS, PAGE_SOURCES


class SourceAdapter(Protocol):
    """Uniform interface for all article sources."""

    name: str

    def fetch(self) -> list[dict]:
        """Return a list of article dicts."""
        ...


class RSSSourceAdapter:
    """Adapter for RSS feed sources."""

    name = "rss"

    def __init__(self, feeds: list[tuple[str, str]] | None = None) -> None:
        self.feeds = feeds or RSS_FEEDS

    def fetch(self) -> list[dict]:
        from ai_news_digest.analysis.health import filter_disabled_sources, source_check
        from .rss import fetch_rss_articles

        active = filter_disabled_sources(self.feeds)
        try:
            articles = fetch_rss_articles(feeds=active)
            for name, _ in active:
                count = len([a for a in articles if a.get("source") == name])
                source_check(name, success=True, article_count=count)
            return articles
        except Exception:
            for name, _ in active:
                source_check(name, success=False, article_count=0)
            raise


class PageSourceAdapter:
    """Adapter for page-scraped sources (e.g. Fortune)."""

    name = "pages"

    def __init__(self, sources: list[dict] | None = None) -> None:
        self.sources = sources or PAGE_SOURCES

    def fetch(self) -> list[dict]:
        from .pages import fetch_page_articles

        return fetch_page_articles(sources=self.sources)


class OrthogonalSourceAdapter:
    """Adapter for orthogonal signal feeds (research / builder)."""

    name = "orthogonal"

    def fetch(self) -> list[dict]:
        from .orthogonal import fetch_orthogonal_signal_articles

        return fetch_orthogonal_signal_articles()


class GitHubTrendingAdapter:
    """Adapter for GitHub trending repos."""

    name = "github_trending"

    def __init__(self, top_n: int | None = None) -> None:
        self.top_n = top_n

    def fetch(self) -> list[dict]:
        from .github_trending import fetch_github_trending

        return fetch_github_trending(top_n=self.top_n)


def build_default_adapters() -> list[SourceAdapter]:
    """Return the standard set of source adapters used by the daily pipeline."""
    return [
        RSSSourceAdapter(),
        PageSourceAdapter(),
        OrthogonalSourceAdapter(),
        GitHubTrendingAdapter(top_n=3),
    ]
