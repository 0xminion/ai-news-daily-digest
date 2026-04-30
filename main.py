#!/usr/bin/env python3
"""Backward-compatible entry point. Use scripts/daily.py for new code."""
import sys

from scripts.daily import main

if __name__ == "__main__":
    sys.exit(main())
