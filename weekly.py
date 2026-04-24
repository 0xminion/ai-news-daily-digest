#!/usr/bin/env python3
import argparse
import sys
from ai_news_digest.app import run_weekly

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="AI News Weekly Digest")
    parser.add_argument("--telegram", action="store_true", help="Deliver weekly report to Telegram instead of stdout")
    args = parser.parse_args()
    sys.exit(run_weekly(deliver=args.telegram))
