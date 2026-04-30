# Comprehensive Code Review — ai-news-daily-digest
**Date:** 2026-04-29  
**Commit:** ee3b636  
**Tests:** 76/76 passing  
**Rating:** 7.5/10 (solid architecture, several live bugs and integration gaps)

---

## Critical Issues (fix before production)

### C1 — Weekly reports saved to daily_reports table
**File:** `ai_news_digest/storage/archive.py:92`  
`save_weekly_report()` imports `save_daily_report` from `sqlite_store` (aliased as `sql_save`) and writes weekly data into the `daily_reports` table. The `weekly_reports` table exists in schema but is never written to.

**Fix:** Use `save_weekly_report` from `sqlite_store`.

### C2 — Circuit breaker never updates state
**File:** `ai_news_digest/analysis/health.py`  
`source_check()` is defined but **never called** by `fetch_digest_inputs()` or any fetcher. The circuit breaker always sees empty state, so `filter_disabled_sources()` is a no-op. All the JSON-state machinery is dead weight.

**Fix:** Wire `source_check()` into RSS/page/orthogonal fetch loops with success/failure + article counts.

### C3 — Entity extraction is completely un wired
**File:** `ai_news_digest/analysis/entities.py`  
`extract_and_record_entities()` is defined but **never invoked**. The entities table in SQLite will always be empty. The weekly `build_entity_trend_section()` will always return `""`.

**Fix:** Call `extract_and_record_entities(run_id, summary)` after LLM summarization in `app.py`.

### C4 — Observability metrics are defined but never instrumented
**File:** `ai_news_digest/observability/metrics.py`  
`fetch_latency()`, `articles_fetched()`, `fetch_failed()` are defined but never called in `pipeline.py`. Only `set_run_id`, `pipeline_start`, `pipeline_success`, `cluster_count`, and `dedup_hit_rate` are used.

**Fix:** Instrument RSS/page/orthogonal fetch loops with latency and count calls.

### C5 — Cluster dicts mixed with articles in daily archive
**File:** `ai_news_digest/app.py:39`  
`save_daily_report(..., clusters=payload['main_clusters'] + payload['research_clusters'])` concatenates cluster dicts (which contain nested `representative`, `articles`, etc.) with flat article dicts. The archive JSON stores heterogeneous objects in the `articles` array.

**Fix:** Store clusters separately or extract only representative articles.

---

## High Issues

### H1 — Circuit breaker uses JSON instead of SQLite
**File:** `ai_news_digest/analysis/health.py`  
Inconsistent with the rest of the codebase which migrated to SQLite. JSON file locking is best-effort; SQLite handles concurrency properly.

**Fix:** Migrate `source_health.json` to a `source_health` table in `digest.db`.

### H2 — Serial embedding HTTP calls (performance)
**File:** `ai_news_digest/analysis/semantic_clustering.py:70-72`  
Embeddings are fetched one at a time in a loop. For 20 articles this is 20 serial HTTP round-trips (~20×60ms = 1.2s minimum). Ollama's `/api/embeddings` supports single-prompt calls; batching would require `/api/embed` but even parallel `ThreadPoolExecutor` would help.

**Fix:** Use `concurrent.futures.ThreadPoolExecutor` to parallelize embedding fetches.

### H3 — Entity extraction duplicates LLM service logic
**File:** `ai_news_digest/analysis/entities.py:30-89`  
`_call_llm()` re-implements the exact same provider switchboard (`ollama`/`openai`/`openrouter`/`anthropic`) that exists in `llm/service.py`. Any provider fix needs to be made in two places.

**Fix:** Refactor to call `summarize()` or extract a `_call_provider()` helper from `llm/service.py`.

### H4 — Dead code: `_fetch_articles_from_rss()`
**File:** `ai_news_digest/sources/pipeline.py:102-104`  
Defined but never called.

**Fix:** Remove.

### H5 — Dead variable: `_all_sources`
**File:** `ai_news_digest/sources/pipeline.py:115`  
Computed but never referenced.

**Fix:** Remove.

### H6 — Unused imports (ruff F401)
- `ai_news_digest/analysis/health.py:9` — `sqlite3`
- `ai_news_digest/analysis/health.py:11` — `time`
- `ai_news_digest/analysis/health.py:16` — `get_config_value`
- `ai_news_digest/analysis/relevance.py:10` — `cfg_str`
- `ai_news_digest/analysis/semantic_clustering.py:9` — `typing.Any`

### H7 — Hardcoded constants still in Python modules
**Files:** `config/topics.py`, `config/keywords.py`, `config/trust.py`  
The user mandate was "zero hardcoded Python defaults." Topic maps, keyword regexes, and trust weights are still hardcoded. These should live in `config/default.yaml` or feed fragments.

**Fix:** Move to YAML with typed loaders.

---

## Medium Issues

### M1 — `dry_run.py` / `full_dry_run.py` duplicate boilerplate
Both set dummy env vars and configure logging identically. Could be consolidated.

### M2 — `review_samples.py` uses `.html` extension for Telegram text
Line 33 writes Telegram MarkdownV2 chunks to `*.html` files. Misleading extension.

### M3 — Telegram 429 only retries once
`_send_message()` retries once on 429 then gives up. Aggressive rate limits may need 2-3 retries with backoff.

### M4 — Lazy migration runs on every config import
**File:** `ai_news_digest/config/__init__.py:55-67`  
`_lazy_migrate()` fires on every process start. On a server running multiple digests per day, this is harmless but unnecessary after the first run.

### M5 — `_format_digest` KeyError risk on empty profiles
**File:** `ai_news_digest/output/telegram.py:318`  
If `profiles` dict is empty, `profiles['default']` raises `KeyError`.

---

## Low / Cleanup

- **L1:** Remove `tests/__pycache__` from tracking (already in `.gitignore` but may be committed).
- **L2:** `requirements.txt` should include `pytest-asyncio>=0.23` if async tests are used.
- **L3:** README references old hardcoded config model; needs update for YAML-first system.
- **L4:** `SKILL.md` needs update for new observability and entity extraction features.
- **L5:** `generated_samples/` output files use stale `.html` extension.

---

## Test Coverage Gaps

1. No test for `semantic_clustering` (embedding-dependent, hard to unit test — mock Ollama response).
2. No test for `health.py` circuit breaker logic.
3. No test for `entities.py` extraction.
4. No test for `sqlite_store.py` migration from JSON.
5. `test_telegram_bot.py` only covers formatting, not actual `_send_message` failure modes.

---

## Honest Rating Justification

**7.5/10** — The codebase is well-structured with good separation of concerns, clean YAML config migration, and solid Telegram formatting. The test suite passes and covers core paths. However:
- **3 features are completely un wired** (circuit breaker, entity extraction, observability metrics)
- **1 data corruption bug** (weekly saved to daily table)
- **Performance regression** (serial embedding calls)
- **Code duplication** (LLM provider switchboard in 2 places)
- **Config mandate not fully realized** (topics/keywords/trust still hardcoded)

Fixing C1-C5 and H1-H7 would bring this to **8.5+/10**.
