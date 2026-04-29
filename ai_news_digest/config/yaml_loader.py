"""YAML configuration loader — mandatory YAML files, zero hardcoded Python defaults.

Loads `config/default.yaml`, merges `config/{ENV}.yaml` (ENV=AI_DIGEST_ENV,
defaults to `dev`), then deep-merges `config/feeds/*.yaml`. Environment variables
still override YAML values (layer order: default < env < feeds < dotenv).

Hot-reload: `get_config()` checks mtime on every call.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "config"
FEEDS_DIR = CONFIG_DIR / "feeds"

_yaml_cache: dict[str, Any] | None = None
_yaml_mtime: float = 0.0


def _config_paths() -> tuple[Path, Path]:
    env = os.getenv("AI_DIGEST_ENV", "dev").strip().lower()
    default = CONFIG_DIR / "default.yaml"
    env_file = CONFIG_DIR / f"{env}.yaml"
    if not default.exists():
        raise FileNotFoundError(f"Mandatory config file not found: {default}")
    if not env_file.exists():
        raise FileNotFoundError(f"Mandatory env config file not found: {env_file} (set AI_DIGEST_ENV)")
    return default, env_file


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _deep_merge(base: dict, override: dict) -> dict:
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val
    return base


def _load_feeds() -> dict[str, Any]:
    feeds: dict[str, Any] = {
        "rss_feeds": [],
        "page_sources": [],
        "orthogonal_rss_feeds": [],
    }
    if not FEEDS_DIR.exists():
        return feeds
    for fpath in sorted(FEEDS_DIR.glob("*.yaml")):
        data = _load_yaml(fpath)
        for key in feeds:
            if key in data:
                existing = feeds[key]
                incoming = data[key]
                if isinstance(existing, list) and isinstance(incoming, list):
                    existing.extend(incoming)
                else:
                    feeds[key] = incoming
    return feeds


def _parse_env_value(v: str) -> Any:
    if v.lower() in {"true", "yes", "on", "1"}:
        return True
    if v.lower() in {"false", "no", "off", "0"}:
        return False
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    if v.startswith(("[", "{\"", "{'")):
        try:
            return json.loads(v)
        except Exception:
            pass
    return v


def _apply_env_overrides(cfg: dict) -> dict:
    for k, v in os.environ.items():
        if k.startswith("AI_DIGEST_"):
            key = k[len("AI_DIGEST_"):].lower()
            parts = key.split("__")
            node = cfg
            for part in parts[:-1]:
                if part not in node or not isinstance(node[part], dict):
                    node[part] = {}
                node = node[part]
            node[parts[-1]] = _parse_env_value(v)
    _LEGACY_MAP: dict[str, tuple[str, ...]] = {
        "OLLAMA_MODEL": ("llm", "model"),
        "OLLAMA_HOST": ("llm", "ollama_host"),
        "OLLAMA_TIMEOUT": ("llm", "timeout"),
        "LLM_PROVIDER": ("llm", "provider"),
        "LLM_MODEL": ("llm", "model"),
        "LLM_API_BASE": ("llm", "api_base"),
        "LLM_TIMEOUT": ("llm", "timeout"),
        "LLM_MAX_TOKENS": ("llm", "max_tokens"),
        "LLM_CONTEXT_LIMIT": ("llm", "context_limit"),
        "OPENAI_API_KEY": ("secrets", "openai_api_key"),
        "OPENROUTER_API_KEY": ("secrets", "openrouter_api_key"),
        "ANTHROPIC_API_KEY": ("secrets", "anthropic_api_key"),
        "TELEGRAM_BOT_TOKEN": ("delivery", "bot_token"),
        "TELEGRAM_CHAT_ID": ("delivery", "chat_id"),
        "TELEGRAM_DESTINATIONS_JSON": ("delivery", "destinations_json"),
        "OUTPUT_MODE": ("delivery", "output_mode"),
        "DELIVERY_HOUR": ("delivery", "delivery_hour"),
        "LOG_LEVEL": ("log", "level"),
        "RETENTION_DAYS": ("archive", "retention_days"),
        "CROSS_DAY_DEDUP_DAYS": ("archive", "cross_day_dedup_days"),
        "TREND_LOOKBACK_DAYS": ("archive", "trend_lookback_days"),
        "CLUSTER_SIMILARITY_THRESHOLD": ("clustering", "similarity_threshold"),
        "MAX_ARTICLES_TO_SUMMARIZE": ("fetching", "max_articles_to_summarize"),
        "RSS_WINDOW_HOURS": ("fetching", "rss_window_hours"),
        "USER_AGENT": ("fetching", "user_agent"),
        "CONTENT_FETCH_TIMEOUT": ("fetching", "content_fetch_timeout"),
        "MIN_ARTICLE_TEXT_LENGTH": ("fetching", "min_article_text_length"),
        "FULL_CONTENT_FETCH_LIMIT": ("fetching", "full_content_fetch_limit"),
        "HN_ENABLED": ("hn", "enabled"),
        "HN_MIN_POINTS": ("hn", "min_points"),
        "HN_MIN_COMMENTS": ("hn", "min_comments"),
        "HN_MAX_STORIES": ("hn", "max_stories"),
        "HN_SIGNAL_WINDOW_HOURS": ("hn", "signal_window_hours"),
        "ORTHOGONAL_SIGNALS_ENABLED": ("signals", "orthogonal_signals_enabled"),
        "RESEARCH_SIGNALS_COUNT": ("signals", "research_signals_count"),
        "RESEARCH_TOPIC_CAP_PER_TOPIC": ("signals", "research_topic_cap_per_topic"),
        "WEEKLY_HIGHLIGHTS_COUNT": ("weekly", "highlights_count"),
        "WEEKLY_DIRECTIONS_COUNT": ("weekly", "directions_count"),
        "WEEKLY_FOCUS_COUNT": ("weekly", "focus_count"),
        "WEEKLY_QUESTIONS_COUNT": ("weekly", "questions_count"),
        "WEEKLY_RESEARCH_SIGNALS_COUNT": ("weekly", "research_signals_count"),
        "WEEKLY_EMERGING_COUNT": ("weekly", "emerging_count"),
        "FOLLOW_BUILDERS_ENABLED": ("follow_builders", "enabled"),
        "FOLLOW_BUILDERS_FEEDS_JSON": ("follow_builders", "feeds_json"),
        "FOLLOW_BUILDERS_PROMPT_STYLE": ("follow_builders", "prompt_style"),
        "FOLLOW_BUILDERS_SCHEMA_VERSION": ("follow_builders", "schema_version"),
    }
    for env_key, path in _LEGACY_MAP.items():
        val = os.getenv(env_key)
        if val is not None:
            node = cfg
            for part in path[:-1]:
                if part not in node or not isinstance(node[part], dict):
                    node[part] = {}
                node = node[part]
            node[path[-1]] = _parse_env_value(val)
    return cfg


def reload_config() -> dict[str, Any]:
    global _yaml_cache, _yaml_mtime
    default_path, env_file = _config_paths()
    cfg = _load_yaml(default_path)
    env_cfg = _load_yaml(env_file)
    _deep_merge(cfg, env_cfg)
    feeds = _load_feeds()
    _deep_merge(cfg, feeds)
    cfg = _apply_env_overrides(cfg)
    _yaml_cache = cfg
    _yaml_mtime = max(default_path.stat().st_mtime, env_file.stat().st_mtime)
    return cfg


def get_config() -> dict[str, Any]:
    global _yaml_cache, _yaml_mtime
    default_path, env_file = _config_paths()
    try:
        current_mtime = max(default_path.stat().st_mtime, env_file.stat().st_mtime)
    except FileNotFoundError:
        current_mtime = 0.0
    if _yaml_cache is None or current_mtime > _yaml_mtime:
        return reload_config()
    return _yaml_cache


def get_config_value(*path: str, default: Any = None) -> Any:
    node = get_config()
    for part in path:
        if not isinstance(node, dict):
            return default
        node = node.get(part, {})
    return node if node != {} else default


# ---------------------------------------------------------------------------
# Typed helpers
# ---------------------------------------------------------------------------


def cfg_bool(path: str) -> bool:
    val = get_config_value(*path.split("."), default=False)
    return bool(val) if val is not None else False


def cfg_int(path: str) -> int:
    val = get_config_value(*path.split("."), default=0)
    return int(val) if val is not None else 0


def cfg_str(path: str) -> str:
    val = get_config_value(*path.split("."), default="")
    return str(val) if val is not None else ""


def cfg_dict(path: str) -> dict:
    val = get_config_value(*path.split("."), default={})
    return val if isinstance(val, dict) else {}


def cfg_list(path: str) -> list:
    val = get_config_value(*path.split("."), default=[])
    return val if isinstance(val, list) else []


# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------


def get_data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))


def get_state_dir() -> Path:
    return get_data_dir() / "state"


def get_report_archive_dir() -> Path:
    return get_data_dir() / "daily_reports"


def get_weekly_archive_dir() -> Path:
    return get_data_dir() / "weekly_reports"


_dirs_initialized = False


def ensure_directories() -> None:
    global _dirs_initialized
    if not _dirs_initialized:
        for d in (get_report_archive_dir(), get_weekly_archive_dir(), get_state_dir()):
            d.mkdir(parents=True, exist_ok=True)
        _dirs_initialized = True


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------


def _resolve_hermes_llm_defaults() -> dict:
    import re
    import sys

    hermes_home = Path.home() / ".hermes"
    config_path = hermes_home / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        text = config_path.read_text(encoding="utf-8")
        provider_match = re.search(r"^model:\s*\n(?:\s+.*\n)*?\s+provider:\s*(\S+)", text, re.M)
        model_match = re.search(r"^model:\s*\n(?:\s+.*\n)*?\s+default:\s*(\S+)", text, re.M)
        provider = (provider_match.group(1) if provider_match else "").strip().lower()
        model = (model_match.group(1) if model_match else "").strip()
        if not provider or not model:
            return {}
        hermes_agent = hermes_home / "hermes-agent"
        hermes_venv = hermes_agent / "venv" / "lib" / "python3.11" / "site-packages"
        for p in (str(hermes_venv), str(hermes_home), str(hermes_agent)):
            if p not in sys.path:
                sys.path.insert(0, p)
        if provider == "nous":
            import auth as hermes_auth

            creds = hermes_auth.resolve_nous_runtime_credentials()
            return {
                "provider": "openai",
                "model": model,
                "api_base": creds.get("base_url", ""),
                "api_key": creds.get("api_key", ""),
                "key_name": "OPENAI_API_KEY",
            }
        if provider == "openrouter":
            import auth as hermes_auth

            pool = hermes_auth.read_credential_pool()
            for cred in pool.get("openrouter", []):
                token = cred.get("access_token", "")
                if token and not token.startswith("***"):
                    return {
                        "provider": "openrouter",
                        "model": model,
                        "api_base": "https://openrouter.ai/api/v1",
                        "api_key": token,
                        "key_name": "OPENROUTER_API_KEY",
                    }
        if provider == "anthropic":
            import auth as hermes_auth

            pool = hermes_auth.read_credential_pool()
            for cred in pool.get("anthropic", []):
                token = cred.get("access_token", "")
                if token and not token.startswith("***"):
                    return {
                        "provider": "anthropic",
                        "model": model,
                        "api_base": "https://api.anthropic.com",
                        "api_key": token,
                        "key_name": "ANTHROPIC_API_KEY",
                    }
        if provider in ("ollama", "custom"):
            return {"provider": "ollama", "model": model}
    except Exception:
        pass
    return {}


def get_llm_settings() -> dict:
    provider = str(get_config_value("llm", "provider", default="ollama")).strip().lower()
    model = str(get_config_value("llm", "model", default="minimax-m2.7:cloud")).strip()
    if not provider and "/" in model:
        p, m = model.split("/", 1)
        if p.lower() in {"ollama", "openai", "openrouter", "anthropic"}:
            provider, model = p.lower(), m
    provider = provider or "ollama"
    model = model or "minimax-m2.7:cloud"
    temperature = float(get_config_value("llm", "temperature", default=0.2))
    if "kimi" in model.lower():
        temperature = 1.0
    hermes_defaults = _resolve_hermes_llm_defaults()
    if hermes_defaults and not get_config_value("llm", "provider"):
        provider = hermes_defaults.get("provider", provider)
        model = hermes_defaults.get("model", model)
    api_base = str(get_config_value("llm", "api_base", default="")).rstrip("/")
    if not api_base and hermes_defaults:
        api_base = hermes_defaults.get("api_base", "").rstrip("/")
    openai_key = str(get_config_value("secrets", "openai_api_key", default=""))
    or_key = str(get_config_value("secrets", "openrouter_api_key", default=""))
    anth_key = str(get_config_value("secrets", "anthropic_api_key", default=""))
    return {
        "provider": provider,
        "model": model,
        "api_base": api_base,
        "timeout": int(get_config_value("llm", "timeout", default=120)),
        "max_tokens": int(get_config_value("llm", "max_tokens", default=1800)),
        "context_limit": get_config_value("llm", "context_limit") or None,
        "openai_api_key": openai_key,
        "openrouter_api_key": or_key,
        "anthropic_api_key": anth_key,
        "ollama_host": str(get_config_value("llm", "ollama_host", default="http://localhost:11434")),
        "temperature": temperature,
    }


# ---------------------------------------------------------------------------
# Destination helpers
# ---------------------------------------------------------------------------


def get_destination_profiles() -> dict[str, dict]:
    raw = get_config_value("delivery", "profiles", default={})
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if isinstance(v, dict)}


def get_telegram_destinations() -> list[dict]:
    raw = get_config_value("delivery", "destinations", default=[])
    if not raw:
        raw_json = get_config_value("delivery", "destinations_json", default="")
        if raw_json:
            if isinstance(raw_json, list):
                raw = raw_json
            else:
                try:
                    raw = json.loads(raw_json)
                except Exception:
                    pass
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    if not isinstance(raw, list):
        return []
    bot_token = str(get_config_value("secrets", "telegram_bot_token", default="") or get_config_value("delivery", "bot_token", default=""))
    chat_id = str(get_config_value("delivery", "chat_id", default=""))
    destinations: list[dict] = []
    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        cid = str(item.get("chat_id", "")).strip() or chat_id
        if not cid:
            continue
        destinations.append({
            "name": item.get("name") or f"destination-{idx}",
            "chat_id": cid,
            "bot_token": str(item.get("bot_token", "")).strip() or bot_token,
            "profile": item.get("profile", "default"),
        })
    if not destinations and chat_id:
        destinations.append({"name": "destination-1", "chat_id": chat_id, "bot_token": bot_token, "profile": "default"})
    return destinations


# ---------------------------------------------------------------------------
# Follow builders
# ---------------------------------------------------------------------------


def get_follow_builders_config() -> dict:
    feeds = []
    raw_json = get_config_value("follow_builders", "feeds_json", default="")
    if raw_json:
        try:
            feeds = json.loads(raw_json)
        except Exception:
            pass
    return {
        "enabled": bool(get_config_value("follow_builders", "enabled", default=False)),
        "schema_version": str(get_config_value("follow_builders", "schema_version", default="v1")),
        "prompt_style": str(get_config_value("follow_builders", "prompt_style", default="builders")),
        "feeds": feeds,
    }
