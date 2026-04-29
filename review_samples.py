from __future__ import annotations

import json
from pathlib import Path

from ai_news_digest.analysis.weekly import render_weekly_highlights
from ai_news_digest.app import _render_sample_daily
from ai_news_digest.output.telegram import _format_digest

BASE_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = BASE_DIR / 'examples' / 'fixtures'
OUTPUT_DIR = BASE_DIR / 'generated_samples'


def _load_json(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding='utf-8'))


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily_payload = _load_json('daily_payload.json')
    weekly_payload = _load_json('weekly_payload.json')

    daily_text = _render_sample_daily(daily_payload)
    weekly_text = render_weekly_highlights(weekly_payload)
    default_chunks = _format_digest(daily_text, profile_name='default')
    compact_chunks = _format_digest(daily_text, profile_name='compact')

    outputs = {
        'fixture-daily-sample.txt': daily_text,
        'fixture-weekly-sample.txt': weekly_text,
        'fixture-daily-telegram-default.md': '\n\n--- CHUNK ---\n\n'.join(default_chunks),
        'fixture-daily-telegram-compact.md': '\n\n--- CHUNK ---\n\n'.join(compact_chunks),
    }
    for name, content in outputs.items():
        (OUTPUT_DIR / name).write_text(content, encoding='utf-8')
        print(OUTPUT_DIR / name)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
