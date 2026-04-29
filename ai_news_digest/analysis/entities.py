"""Entity extraction via LLM + cross-day linking.

Uses the configured LLM to extract people, orgs, coins, projects from digest text.
Results are persisted to SQLite and surfaced in weekly reports.
"""
from __future__ import annotations

import json
import re

import requests

from ai_news_digest.config import get_llm_settings, logger
from ai_news_digest.storage.sqlite_store import get_entity_trends, record_entities


def _extract_via_llm(text: str, settings: dict) -> list[dict]:
    """Prompt the LLM to extract entities. Returns list of {name, type}."""
    max_tokens = max(200, settings.get("max_tokens", 1800) // 4)
    provider = settings["provider"]
    model = settings["model"]
    prompt = (
        "Extract entities from the following AI digest text. "
        "Return ONLY a JSON array of objects with 'name' and 'type' keys.\n\n"
        "Valid types: person, org, coin, project, topic.\n\n"
        f"Text:\n{text[:4000]}\n\n"
        "JSON output:"
    )

    def _call_llm(prompt: str) -> str:
        if provider == "ollama":
            resp = requests.post(
                f"{settings['ollama_host']}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=settings["timeout"],
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
        elif provider in {"openai", "openrouter"}:
            api_base = settings["api_base"] or {
                "openai": "https://api.openai.com/v1",
                "openrouter": "https://openrouter.ai/api/v1",
            }[provider]
            headers = {
                "Authorization": f"Bearer {settings[f'{provider}_api_key']}",
                "Content-Type": "application/json",
            }
            if provider == "openrouter":
                headers["HTTP-Referer"] = "https://github.com/0xminion/ai-news-daily-digest"
                headers["X-Title"] = "ai-news-daily-digest"
            body = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You extract named entities. Always respond with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": settings.get("temperature", 0.2),
                "max_tokens": max_tokens,
            }
            resp = requests.post(
                f"{api_base}/chat/completions",
                headers=headers,
                json=body,
                timeout=settings["timeout"],
            )
            resp.raise_for_status()
            msg = resp.json().get("choices", [{}])[0].get("message", {})
            raw = msg.get("content", "")
            if not raw and msg.get("reasoning"):
                raw = msg["reasoning"]
            return raw
        elif provider == "anthropic":
            resp = requests.post(
                f"{settings['api_base'] or 'https://api.anthropic.com'}/v1/messages",
                headers={"x-api-key": settings["anthropic_api_key"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": settings.get("temperature", 0.2),
                    "system": "You extract named entities. Always respond with valid JSON.",
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=settings["timeout"],
            )
            resp.raise_for_status()
            data = resp.json()
            return "\n".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        else:
            raise ValueError(f"Unsupported LLM provider '{provider}' for entity extraction")

    try:
        raw = _call_llm(prompt)
        # Extract JSON array
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            entities = json.loads(match.group(0))
            if isinstance(entities, list):
                return [e for e in entities if isinstance(e, dict) and "name" in e and "type" in e]
    except Exception as exc:
        logger.warning("Entity extraction LLM call failed: %s", exc)
    return []


def extract_and_record_entities(run_id: str, digest_text: str) -> list[dict]:
    """Extract entities from digest text and record them in SQLite."""
    settings = get_llm_settings()
    entities = _extract_via_llm(digest_text, settings)
    if entities:
        record_entities(run_id, entities)
    return entities


def build_entity_trend_section(lookback_runs: int = 5) -> str:
    """Build a markdown section for the weekly report showing trending entities."""
    trends = get_entity_trends(min_mention_count=2, lookback_runs=lookback_runs)
    if not trends:
        return ""
    lines = ["📈 Mentioned across recent digests:", ""]
    for t in trends:
        name = t["name"]
        etype = t["entity_type"]
        count = t["mention_count"]
        first = t.get("first_seen_run_id", "?")[:8]
        lines.append(f"- **{name}** ({etype}) — {count} mention(s), first seen run {first}")
    lines.append("")
    return "\n".join(lines)
