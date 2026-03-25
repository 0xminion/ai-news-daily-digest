"""AI News Summarizer — Daily digest of top AI news."""

from test.fetcher import fetch_all_articles
from test.formatter import format_digest


def main() -> None:
    """Fetch AI news and print formatted digest to stdout."""
    print("Fetching AI news from RSS feeds...", flush=True)
    articles = fetch_all_articles()
    print(f"Found {len(articles)} AI-related articles in past 24h.", flush=True)
    digest = format_digest(articles)
    print("\n" + digest)


if __name__ == "__main__":
    main()