#!/usr/bin/env python3
import argparse
import sys
from ai_news_digest.app import run_daily

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI News Daily Digest")
    parser.add_argument("--telegram", action="store_true", help="Deliver digest to Telegram instead of stdout")
    args = parser.parse_args()
    sys.exit(run_daily(deliver=args.telegram))
