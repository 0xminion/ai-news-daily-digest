#!/usr/bin/env python3
"""Full pipeline dry run — fetch, summarize, format, print. No Telegram delivery."""
import logging
import os


def _setup():
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dry-run")
    os.environ.setdefault("TELEGRAM_CHAT_ID", "dry-run")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    for n in ("urllib3", "requests", "httpx", "httpcore"):
        logging.getLogger(n).setLevel(logging.WARNING)


if __name__ == "__main__":
    _setup()
    from ai_news_digest.config import validate_config
    from ai_news_digest.llm import AgentSummarizationRequired, summarize
    from ai_news_digest.output.telegram import _format_digest
    from ai_news_digest.pipeline import fetch_digest_inputs

    validate_config()

    payload = fetch_digest_inputs()

    try:
        summary = summarize(
            payload['main_articles'],
            research_articles=payload['research_articles'],
        )
    except AgentSummarizationRequired as exc:
        print(f"\n{'='*60}")
        print("AGENT SUMMARIZATION REQUIRED")
        print(f"{'='*60}")
        print(f"Prompt saved to: {exc.prompt_path}")
        print(f"Please generate the structured JSON digest and save it to:")
        print(f"  {exc.response_path}")
        print(f"\nThen re-run this script.")
        print(f"{'='*60}\n")
        raise SystemExit(2)

    messages = _format_digest(summary)

    print("\n".join(messages))
    print(f"\n{'=' * 60}")
    print(f"Articles: {len(payload.get('main_articles', []))} main + {len(payload.get('research_articles', []))} research")
    print(f"Messages: {len(messages)}  |  Total chars: {sum(len(m) for m in messages)}")
