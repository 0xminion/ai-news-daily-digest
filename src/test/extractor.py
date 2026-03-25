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
        if char_count + len(sent) <= 200:
            summary_parts.append(sent)
            char_count += len(sent)
        else:
            break
    return " ".join(summary_parts)
