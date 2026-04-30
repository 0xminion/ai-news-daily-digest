#!/usr/bin/env python3
"""Weekly digest entry point."""
import argparse
import sys

from ai_news_digest.app import run_weekly


def main() -> int:
    parser = argparse.ArgumentParser(description="AI News Weekly Digest")
    parser.add_argument("--telegram", action="store_true", help="Deliver weekly report to Telegram instead of stdout")
    args = parser.parse_args()
    return run_weekly(deliver=args.telegram)


if __name__ == "__main__":
    sys.exit(main())
