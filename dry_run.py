#!/usr/bin/env python3
"""Dry run — fetch, summarize, print. No Telegram needed."""
import os, sys, logging
# Dummy Telegram so validate_config() passes
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dry-run")
os.environ.setdefault("TELEGRAM_CHAT_ID", "dry-run")
# Do NOT hardcode OLLAMA_MODEL here — respect .env or env vars so the
# pipeline can run via the configured LLM (e.g. minimax-m2.7) instead of
# falling back to minimax-m2.7:cloud.

# Reduce noise
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
for noisy in ("urllib3", "requests", "httpx", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

from ai_news_digest.app import build_daily_sample
from ai_news_digest.output.telegram import _format_digest

print("=" * 60)
print("AI NEWS DAILY DIGEST — Dry Run")
print("=" * 60)

payload, text = build_daily_sample()

print("\n" + text)
print("\n" + "=" * 60)
print(f"Articles: {len(payload.get('main_articles', []))} main + "
      f"{len(payload.get('research_articles', []))} research")
print("=" * 60)
