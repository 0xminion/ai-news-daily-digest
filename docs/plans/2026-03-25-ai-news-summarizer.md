# AI News Summarizer — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** A Python program that extracts top 10 AI news articles from the past 24 hours (Wired, The Economist, Reuters, TechCrunch, The Verge, Ars Technica, MIT Technology Review), generates a brief rundown summary + 5 must-know highlights with clickable source links, and delivers to a Telegram user via Hermes cron job.

**Architecture:**
- Python script in `~/projects/test/src/test/` that fetches articles via RSS feeds, extracts content, and generates a formatted news digest
- Hermes cron job runs it daily (or on-demand) and delivers output via `send_message` to Telegram
- Uses `feedparser` for RSS, `httpx` for HTTP fetching, and `newspaper4k` (or `trafilatura`) for article extraction/summarization

**Tech Stack:** Python 3.10+, feedparser, httpx, trafilatura, Hermes send_message tool, Telegram

---

## Task 1: Install Dependencies

**Objective:** Install required Python packages in the project venv.

**Files:**
- Modify: `requirements.txt`
- Modify: `requirements-dev.txt`

**Step 1: Update requirements.txt**

```txt
# Core dependencies
feedparser>=6.0
httpx>=0.27
trafilatura>=1.8
```

**Step 2: Update requirements-dev.txt**

```txt
-r requirements.txt
pytest>=8.0
pytest-cov>=4.0
black>=24.0
ruff>=0.2.0
```

**Step 3: Install in venv**

```bash
cd ~/projects/test
source venv/bin/activate
pip install -r requirements.txt
```

---

## Task 2: Define News Sources Config

**Objective:** Centralized RSS feed configuration for reputable AI/tech news sources.

**Files:**
- Create: `src/test/news_sources.py`

**Step 1: Create news_sources.py**

```python
"""RSS feed sources for AI news."""

SOURCES = [
    {
        "name": "Wired",
        "url": "https://www.wired.com/feed/rss",
        "category": "technology",
        "tags": ["ai", "artificial intelligence", "machine learning"],
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "category": "technology",
        "tags": ["ai", "artificial intelligence", "machine learning"],
    },
    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "category": "technology",
        "tags": ["ai", "artificial intelligence"],
    },
    {
        "name": "Reuters",
        "url": "https://feeds.reuters.com/reuters/technologyNews",
        "category": "news",
        "tags": ["ai", "artificial intelligence"],
    },
    {
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "category": "technology",
        "tags": ["ai", "artificial intelligence"],
    },
    {
        "name": "MIT Technology Review",
        "url": "https://www.technologyreview.com/feed/",
        "category": "technology",
        "tags": ["ai", "artificial intelligence"],
    },
    {
        "name": "The Economist",
        "url": "https://www.economist.com/ai-briefing/rss.xml",
        "category": "business",
        "tags": ["ai", "artificial intelligence"],
    },
]
```

---

## Task 3: Build RSS Fetcher

**Objective:** Fetch recent articles from all RSS feeds, filter for AI-related content within 24h.

**Files:**
- Create: `src/test/fetcher.py`

**Step 1: Create fetcher.py**

```python
"""RSS feed fetcher for AI news."""

from __future__ import annotations

import feedparser
from datetime import datetime, timedelta, timezone
from typing import Annotated

import httpx

from test.news_sources import SOURCES


def is_ai_related(title: str, summary: str, tags: list[str]) -> bool:
    """Check if article is AI-related using keyword matching."""
    content = f"{title} {summary}".lower()
    ai_keywords = ["ai", "artificial intelligence", "machine learning", "deep learning", "llm", "gpt", "openai", "anthropic", "google deepmind", "neural network", "chatgpt", "claude", "gemini model", "stable diffusion", "generative ai"]
    return any(kw in content for kw in ai_keywords)


def fetch_feed(source: dict) -> list[dict]:
    """Fetch and parse a single RSS feed, return AI-related articles from past 24h."""
    feed = feedparser.parse(source["url"])
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    articles = []

    for entry in feed.entries:
        try:
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                pub_date = datetime(*published[:6], tzinfo=timezone.utc)
            else:
                pub_date = datetime.now(timezone.utc)

            if pub_date < cutoff:
                continue

            title = entry.get("title", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            link = entry.get("link", "")

            if not is_ai_related(title, summary, source.get("tags", [])):
                continue

            articles.append({
                "title": title.strip(),
                "summary": summary.strip(),
                "link": link,
                "source": source["name"],
                "published": pub_date.isoformat(),
                "tags": source.get("tags", []),
            })
        except Exception:
            continue

    return articles


def fetch_all_articles() -> list[dict]:
    """Fetch articles from all configured sources."""
    all_articles = []
    for source in SOURCES:
        try:
            articles = fetch_feed(source)
            all_articles.extend(articles)
        except Exception:
            continue
    return all_articles
```

**Step 2: Commit**

```bash
git add src/test/fetcher.py src/test/news_sources.py
git commit -m "feat: add RSS fetcher and news sources config"
```

---

## Task 4: Build Article Extractor & Summarizer

**Objective:** Extract full article content and generate concise summaries using trafilatura.

**Files:**
- Create: `src/test/extractor.py`

**Step 1: Create extractor.py**

```python
"""Article content extraction and summarization."""

from __future__ import annotations

from typing import Optional
import trafilatura


def extract_article_text(url: str) -> Optional[str]:
    """Extract full article text from URL using trafilatura."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded)
            return text
    except Exception:
        pass
    return None


def summarize_article(title: str, text: str, max_sentences: int = 3) -> str:
    """Generate a short summary of an article from its full text."""
    if not text:
        return ""
    # Simple extractive summarization: take first N sentences
    sentences = text.replace("\n", " ").split(". ")
    summary_parts = []
    char_count = 0
    for sent in sentences[:max_sentences]:
        sent = sent.strip()
        if not sent.endswith("."):
            sent += "."
        if char_count + len(sent) < 200:
            summary_parts.append(sent)
            char_count += len(sent)
    return " ".join(summary_parts)
```

**Step 2: Commit**

```bash
git add src/test/extractor.py
git commit -m "feat: add article extractor with trafilatura"
```

---

## Task 5: Build News Digest Formatter

**Objective:** Format the final output as a readable Telegram message with rundown + 5 highlights + source links.

**Files:**
- Create: `src/test/formatter.py`

**Step 1: Create formatter.py**

```python
"""Formatter for AI News Digest output."""

from __future__ import annotations

from datetime import datetime
from typing import List


def format_digest(articles: List[dict], top_n: int = 10, highlights_n: int = 5) -> str:
    """Format a news digest for Telegram delivery.

    Args:
        articles: List of article dicts with title, summary, link, source, published
        top_n: How many articles to include in the digest (default 10)
        highlights_n: How many bullet highlights (default 5)

    Returns:
        Formatted Telegram message string.
    """
    date_str = datetime.now().strftime("%B %d, %Y")
    header = f"🤖 AI News Briefing — {date_str}\n"
    header += "=" * 40 + "\n\n"

    # Use top articles sorted by recency
    sorted_articles = sorted(articles, key=lambda a: a["published"], reverse=True)[:top_n]

    # Brief rundown — 2-3 sentence summary of the day's theme
    rundown = _generate_rundown(sorted_articles)

    # 5 must-know highlights
    highlights = _generate_highlights(sorted_articles[:highlights_n])

    footer = "\n— Your daily AI briefing. More at @YourChannel"

    return header + rundown + "\n\n" + highlights + footer


def _generate_rundown(articles: list[dict]) -> str:
    """Generate a 2-3 sentence brief rundown of the day's AI news theme."""
    if not articles:
        return "No significant AI news found in the past 24 hours."

    sources = [a["source"] for a in articles]
    unique_sources = list(dict.fromkeys(sources))  # preserve order, remove dups
    source_list = ", ".join(unique_sources[:5])

    topics = []
    for a in articles[:5]:
        title_lower = a["title"].lower()
        if "openai" in title_lower or "chatgpt" in title_lower:
            topics.append("OpenAI and GPT models")
        elif "google" in title_lower or "gemini" in title_lower:
            topics.append("Google AI developments")
        elif "anthropic" in title_lower or "claude" in title_lower:
            topics.append("Anthropic and Claude")
        elif "regulation" in title_lower or "government" in title_lower or "eu" in title_lower:
            topics.append("AI policy and regulation")
        elif "research" in title_lower or "study" in title_lower:
            topics.append("AI research breakthroughs")
        elif "startup" in title_lower or "funding" in title_lower:
            topics.append("AI startup funding")
        elif "robotics" in title_lower or "autonomous" in title_lower:
            topics.append("Robotics and autonomous systems")

    unique_topics = list(dict.fromkeys(topics))[:3]
    topic_str = ", ".join(unique_topics) if unique_topics else "major AI developments"

    rundown = (
        f"Today saw AI in focus across {source_list} and other outlets. "
        f"Key themes included {topic_str}. "
        f"Here's what matters most:"
    )
    return rundown


def _generate_highlights(articles: list[dict]) -> str:
    """Generate numbered highlight bullets with source links."""
    lines = ["📌 5 Must-Know Highlights:\n"]
    for i, article in enumerate(articles, 1):
        title = article["title"]
        link = article["link"]
        source = article["source"]
        # Escape any Markdown special chars in title for Telegram
        title_escaped = title.replace("*", " ").replace("_", " ").replace("[", "(").replace("]", ")")
        lines.append(f"{i}. {title_escaped}\n   Source: {source} | [Read more]({link})\n")
    return "\n".join(lines)
```

**Step 2: Commit**

```bash
git add src/test/formatter.py
git commit -m "feat: add digest formatter for Telegram output"
```

---

## Task 6: Wire Together the Main Entry Point

**Objective:** Create `python -m test.main` that fetches, extracts, formats, and prints the digest.

**Files:**
- Modify: `src/test/main.py`

**Step 1: Replace main.py**

```python
"""AI News Summarizer — Daily digest of top AI news."""

from test.fetcher import fetch_all_articles
from test.formatter import format_digest


def main() -> None:
    """Fetch AI news and print formatted digest to stdout."""
    print("Fetching AI news from RSS feeds...")
    articles = fetch_all_articles()
    print(f"Found {len(articles)} AI-related articles in past 24h.")

    digest = format_digest(articles)
    print("\n" + digest)


if __name__ == "__main__":
    main()
```

**Step 2: Run to verify it works**

```bash
cd ~/projects/test
source venv/bin/activate
python -m test.main
```

Expected: Fetches feeds, prints digest to stdout. If no articles, print fallback message.

**Step 3: Commit**

```bash
git add src/test/main.py
git commit -m "feat: wire main entry point for AI news digest"
```

---

## Task 7: Add Tests

**Objective:** Cover core logic with unit tests.

**Files:**
- Create: `tests/test_fetcher.py`
- Create: `tests/test_formatter.py`

**Step 1: Write test_formatter.py**

```python
"""Tests for digest formatter."""

from test.formatter import format_digest, _generate_rundown, _generate_highlights


def test_generate_highlights_with_articles():
    articles = [
        {
            "title": "OpenAI announces GPT-5 breakthrough",
            "link": "https://example.com/article1",
            "source": "TechCrunch",
            "published": "2026-03-25T10:00:00+00:00",
        },
        {
            "title": "EU passes new AI regulation law",
            "link": "https://example.com/article2",
            "source": "Reuters",
            "published": "2026-03-25T09:00:00+00:00",
        },
    ]
    result = _generate_highlights(articles)
    assert "1." in result
    assert "OpenAI announces GPT-5 breakthrough" in result
    assert "https://example.com/article1" in result
    assert "TechCrunch" in result


def test_generate_rundown_empty():
    result = _generate_rundown([])
    assert "No significant" in result


def test_format_digest_empty():
    result = format_digest([])
    assert "No significant" in result
```

**Step 2: Write test_fetcher.py**

```python
"""Tests for fetcher."""

from test.fetcher import is_ai_related


def test_is_ai_related_true():
    assert is_ai_related(
        "OpenAI releases GPT-5",
        "A new language model",
        ["ai"]
    )


def test_is_ai_related_false():
    assert not is_ai_related(
        "Local bakery wins award",
        "Best bread in town",
        []
    )
```

**Step 3: Run tests**

```bash
cd ~/projects/test
source venv/bin/activate
pytest tests/ -v
```

Expected: 4 passed

**Step 4: Commit**

```bash
git add tests/test_formatter.py tests/test_fetcher.py
git commit -m "test: add formatter and fetcher unit tests"
```

---

## Task 8: Set Up Hermes Cron Job for Daily Delivery

**Objective:** Create a daily cron job that runs the script and delivers results to Telegram.

**Step 1: Create the cron prompt**

The cron job prompt will call the Python script and use `send_message` to deliver output to the user's Telegram.

In Hermes CLI, create the cron job:

```
/cron create "AI News Digest"
```

Or via cronjob tool — the prompt would be:

```
Fetch and deliver the daily AI news digest. Run:
cd ~/projects/test && source venv/bin/activate && python -m test.main
Then send the full output to telegram using send_message tool targeting the user's Telegram DM.
```

**Note:** The actual cron creation is done via Hermes `/cron` command or `cronjob` tool in the gateway. The Python script outputs the formatted digest to stdout, so Hermes captures it and delivers it.

**Step 2: Verify end-to-end**

```bash
cd ~/projects/test
source venv/bin/activate
python -m test.main 2>&1
```

Copy the output, then manually send it to Telegram:

```
/send telegram <output>
```

---

## Task 9: Push to GitHub

**Step 1: Push all commits**

```bash
cd ~/projects/test
git push
```

---

## Summary of File Changes

| File | Action |
|------|--------|
| `src/test/news_sources.py` | Create — RSS feed config |
| `src/test/fetcher.py` | Create — RSS fetch + 24h filter |
| `src/test/extractor.py` | Create — article text extraction |
| `src/test/formatter.py` | Create — Telegram digest output |
| `src/test/main.py` | Modify — wire everything together |
| `src/test/__init__.py` | Modify — module init |
| `tests/test_fetcher.py` | Create — fetcher unit tests |
| `tests/test_formatter.py` | Create — formatter unit tests |
| `requirements.txt` | Modify — add deps |
| `docs/plans/2026-03-25-ai-news-summarizer.md` | Create — this plan |

## Execution Order

1. Task 1 — Install deps
2. Task 2 — news_sources.py
3. Task 3 — fetcher.py
4. Task 4 — extractor.py
5. Task 5 — formatter.py
6. Task 6 — main.py
7. Task 7 — tests
8. Task 8 — cron setup (manual via Hermes)
9. Task 9 — push

---

**Plan complete.** Ready to execute using subagent-driven-development — I'll dispatch a fresh subagent per task with two-stage review. Shall I proceed?
