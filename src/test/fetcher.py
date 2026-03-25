"""RSS feed fetcher for AI news."""

from __future__ import annotations

import feedparser
from datetime import datetime, timedelta, timezone

from test.news_sources import SOURCES

AI_KEYWORDS = [
    # Core AI terms
    "artificial intelligence", "machine learning", "deep learning",
    "llm", "large language model",
    # Model names (standalone)
    "gpt-", "gpt4", "gpt5", "chatgpt", "claude", "gemini",
    "stable diffusion", "midjourney", "dall-e", "dalle",
    # AI companies (as topic signal)
    "openai", "anthropic", "google deepmind", "deepmind",
    "mistral ai", "meta ai", "x ai", "ibm watson",
    # AI-adjacent tech
    "neural network", "diffusion model", "transformer model",
    "multimodal model", "AI model", "generative ai", "robotics",
]

# Must have at least one of these in the title (not summary alone)
CORE_AI_TITLE_SIGNALS = [
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "llm", "large language model", "chatgpt", "claude", "gpt",
    "openai", "anthropic", "deepmind", "gemini",
    "stable diffusion", "generative ai", "neural network",
    "robotics", "autonomous", "AI model", "AI chip", "AI safety",
    "AI policy", "AI regulation", "AI research",
]

# Broader signals — require additional AI evidence in summary to qualify
BROAD_AI_TITLE_SIGNALS = [
    "ai",  # "the AI Hype Index", "AI news"
]

# Company names that indicate a real AI story (not just a mention)
AI_COMPANY_SIGNALS = [
    "openai", "anthropic", "deepmind", "google deepmind", "mistral",
    "meta ai", "x ai", "ibm watson", "microsoft ai", "nvidia ai",
    "a16z", "y combinator", "seed fund",
]

# Strong negative — these phrases in title almost always mean non-AI story
TITLE_BLOCKLIST = [
    "deal", "sale", "coupon", "discount", "earnings", "revenue share",
    "stock", "crypto", "bitcoin", "ipo", "acquisition", "merger",
    "layoffs", "lawsuit", "scandal", "rumor", " Tes", "tesla",
    "samsung", "apple event", "google pixel", "iphone",
    "oneplus", "oppo find", "xiaomi phone",
]

# Moderate negative — these phrases suggest peripheral/soft AI stories
TITLE_WARNLIST = [
    "raises $", "raises $", "raises ", "secures $", "closes $",
    "funding round", "series a", "series b", "series c",
    "venture capital", "vc funding", "startup",
    "laptop", "smartphone", "phone review", "headphone",
    "smartwatch", "wearable", "tablet", "chromebook",
]


def _has_blocklist_hit(title_lower: str) -> bool:
    return any(bad in title_lower for bad in TITLE_BLOCKLIST)


def _has_warnlist_hit(title_lower: str) -> bool:
    return any(warn in title_lower for warn in TITLE_WARNLIST)


def is_ai_related(title: str, summary: str) -> bool:
    """Strict AI news filter with source-quality signals.

    Logic:
    1. Title has CORE_AI signal -> pass (unless blocklist hit)
    2. Title has BROAD_AI signal AND (AI company in summary OR strong summary signals) -> pass
    3. Any AI keyword in BOTH title AND summary AND no warnlist -> pass
    4. Otherwise -> reject
    """
    import re

    title_lower = title.lower()
    summary_lower = summary.lower()

    def _has_word(text: str, keyword: str) -> bool:
        """Match keyword as whole word (not substring)."""
        return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text))

    def _has_any_word(text: str, keywords: list[str]) -> bool:
        return any(_has_word(text, kw) for kw in keywords)

    # Hard block — never pass these
    if _has_blocklist_hit(title_lower):
        return False

    # --- Check 1: Strong core signal in title ---
    if _has_any_word(title_lower, CORE_AI_TITLE_SIGNALS):
        if _has_warnlist_hit(title_lower):
            if any(company in summary_lower for company in AI_COMPANY_SIGNALS):
                return True
            return False
        return True

    # --- Check 2: Broad AI signal in title + AI company in summary ---
    if _has_word(title_lower, "ai"):
        if any(company in summary_lower for company in AI_COMPANY_SIGNALS):
            return True

    # --- Check 3: AI keyword in BOTH title AND summary, no warnlist ---
    ai_in_title = _has_any_word(title_lower, AI_KEYWORDS)
    ai_in_summary = _has_any_word(summary_lower, AI_KEYWORDS)
    if ai_in_title and ai_in_summary and not _has_warnlist_hit(title_lower):
        return True

    return False


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
                # Skip entries with no publication date
                continue

            if pub_date < cutoff:
                continue

            title = entry.get("title", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            link = entry.get("link", "")

            if not is_ai_related(title, summary):
                continue

            articles.append({
                "title": title.strip(),
                "summary": summary.strip(),
                "link": link,
                "source": source["name"],
                "published": pub_date.isoformat(),
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
