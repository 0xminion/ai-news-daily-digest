#!/usr/bin/env python3
"""Daily digest entry point."""
import argparse
import sys

from ai_news_digest.app import run_daily


def main() -> int:
    parser = argparse.ArgumentParser(description="AI News Daily Digest")
    parser.add_argument("--telegram", action="store_true", help="Deliver digest to Telegram instead of stdout")
    args = parser.parse_args()
    return run_daily(deliver=args.telegram)


if __name__ == "__main__":
    sys.exit(main())
