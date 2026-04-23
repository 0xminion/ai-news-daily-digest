#!/usr/bin/env python3
"""Full pipeline dry run — fetch, summarize, format, print. No Telegram."""
import os, sys, logging
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dry-run")
os.environ.setdefault("TELEGRAM_CHAT_ID", "dry-run")
os.environ.setdefault("OLLAMA_MODEL", "minimax-m2.7:cloud")
os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
for n in ("urllib3", "requests", "httpx", "httpcore"):
    logging.getLogger(n).setLevel(logging.WARNING)

from ai_news_digest.app import _ensure_weekly_payload, build_weekly_preview
from ai_news_digest.config import validate_config, get_telegram_destinations
from ai_news_digest.llm import summarize
from ai_news_digest.output.telegram import _format_digest
from ai_news_digest.sources.pipeline import fetch_digest_inputs
from ai_news_digest.storage.archive import prune_old_reports

validate_config()

payload = fetch_digest_inputs()
weekly_payload = _ensure_weekly_payload(payload)
weekly_preview = build_weekly_preview(weekly_payload)

summary = summarize(
    payload['main_articles'],
    trend_snapshot=payload['trend_snapshot'],
    research_articles=payload['research_articles'],
    weekly_preview=weekly_preview,
)

messages = _format_digest(summary)

print("\n".join(messages))
print(f"\n{'=' * 60}")
print(f"Articles: {len(payload.get('main_articles', []))} main + {len(payload.get('research_articles', []))} research")
print(f"Messages: {len(messages)}  |  Total chars: {sum(len(m) for m in messages)}")
