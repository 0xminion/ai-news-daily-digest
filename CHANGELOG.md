# Changelog

## 2026-04-30

### Changed
- **Semantic clustering disabled by default**: After live benchmarking, `qwen3-embedding:0.6b` on CPU adds ~90s for 32 core articles with zero output difference on typical daily volume. Set `embedding.semantic_clustering_enabled: false` in `config/default.yaml`. Opt-in by setting the env var `AI_DIGEST_embedding__semantic_clustering_enabled=true` or editing config.
- Embedding HTTP timeout bumped from 120s to 300s to accommodate larger batches when opted-in.
- Added `AI_DIGEST_SKIP_RESEARCH_EMBEDDING` env var to skip research-article embedding even when semantic clustering is enabled.

### Fixed
- Agent-mode weekly summary now returns a validated dict instead of a JSON string, fixing `AttributeError` in weekly agent path.

## 2026-04-23

### Added
- **Hermes auto-detection**: When no explicit `LLM_PROVIDER`/`LLM_MODEL` env vars are set, the pipeline reads `~/.hermes/config.yaml` and resolves runtime credentials so the digest automatically follows the same model/provider as the active agent session. Supports Nous Research, OpenRouter, Anthropic, and Ollama/custom providers.
- **kimi-k2.6 compatibility**: Added reasoning-model support — detects empty `content` responses and falls back to `reasoning` field. Auto-sets `temperature=1` for kimi models. Gracefully handles unsupported `response_format` by retrying without it.
- **Token guard**: Prompts are automatically truncated to fit within the target model's context window, preventing overflow errors on large article batches.

### Fixed
- Fixed missing `summarize_weekly` import in `analysis/weekly.py` that broke weekly LLM synthesis.
- Removed hardcoded `minimax-m2.7:cloud` fallback from `dry_run.py` and `full_dry_run.py` so scripts respect env/.env/Hermes config.
- Fixed Telegram renderer to embed links on headlines instead of source names, matching modern Telegram formatting preferences.
- Removed dead `send_to_chat.py` script.

## 2026-04-10

### Added
- Added Fortune AI section as a new source via page scraping.
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
