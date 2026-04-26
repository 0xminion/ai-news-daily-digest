#!/usr/bin/env python3
"""Full pipeline dry run — fetch, summarize, format, print. No Telegram."""
import os, sys, logging
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dry-run")
os.environ.setdefault("TELEGRAM_CHAT_ID", "dry-run")
# Do NOT hardcode OLLAMA_MODEL here — respect .env or env vars so the
# pipeline can run via the configured LLM (e.g. kimi-k2.6) instead of
# falling back to minimax-m2.7:cloud.

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
for n in ("urllib3", "requests", "httpx", "httpcore"):
    logging.getLogger(n).setLevel(logging.WARNING)

from ai_news_digest.config import validate_config, get_telegram_destinations
from ai_news_digest.llm import summarize
from ai_news_digest.output.telegram import _format_digest
from ai_news_digest.sources.pipeline import fetch_digest_inputs
from ai_news_digest.storage.archive import prune_old_reports

validate_config()

payload = fetch_digest_inputs()

summary = summarize(
    payload['main_articles'],
    research_articles=payload['research_articles'],
)

messages = _format_digest(summary)

print("\n".join(messages))
print(f"\n{'=' * 60}")
print(f"Articles: {len(payload.get('main_articles', []))} main + {len(payload.get('research_articles', []))} research")
print(f"Messages: {len(messages)}  |  Total chars: {sum(len(m) for m in messages)}")
