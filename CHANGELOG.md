# Changelog

## 2026-04-10

### Added
- Added Fortune AI section as a new source via page scraping: https://fortune.com/section/artificial-intelligence/
- Added `cloudscraper` and `beautifulsoup4` dependencies for blocked page retrieval and HTML extraction.
- Added archive fallback support using the Wayback Machine and archive.ph/archive.today when pages are blocked, unavailable, or subscription-gated.
- Added `storage.py` to save a local copy of each daily report.
- Added automatic retention pruning for archived reports older than 30 days.
- Added support for configurable LLM providers/models through environment variables, with inheritance from agent primary provider/model when available.
- Added tests for archive fallback, Fortune extraction helpers, provider routing, and report retention.

### Changed
- Updated the fetch pipeline to support both RSS sources and page-based sources.
- Updated summarization to support `ollama`, `openai`, `openrouter`, and `anthropic`.
- Updated runtime checks so Ollama health is only probed when Ollama is the active provider.
- Updated documentation and `.env.example` for new provider and retention settings.

### Notes
- Daily reports are now archived under `data/daily_reports/YYYY-MM-DD/` as both `digest.txt` and `digest.json`.
- Retention defaults to 30 days and can be configured with `RETENTION_DAYS`.
