#!/usr/bin/env python3
import sys
from ai_news_digest.app import run_weekly

if __name__ == '__main__':
    sys.exit(run_weekly(deliver=True))
