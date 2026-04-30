"""Entity extraction via LLM + cross-day linking.

Uses the configured LLM to extract people, orgs, coins, projects from digest text.
Results are persisted to SQLite and surfaced in weekly reports.
"""
from __future__ import annotations

import json
import re

from ai_news_digest.config import get_llm_settings, logger
from ai_news_digest.storage.sqlite_store import get_entity_trends, record_entities


def _extract_via_llm(text: str, settings: dict) -> list[dict]:
    """Prompt the LLM to extract entities. Returns list of {name, type}."""
    max_tokens = max(200, settings.get("max_tokens", 1800) // 4)
    provider = settings["provider"]
    prompt = (
        "Extract entities from the following AI digest text. "
        "Return ONLY a JSON array of objects with 'name' and 'type' keys.\n\n"
        "Valid types: person, org, coin, project, topic.\n\n"
        f"Text:\n{text[:4000]}\n\n"
        "JSON output:"
    )

    # Reuse the LLM service's provider dispatch via a thin wrapper.
    # _llm_summarize expects articles, but we can call the internal provider
    # functions directly. However, they are private. Instead, we use a
    # dedicated small-prompt path via the existing _ollama/_openai_compatible
    # helpers by importing them.
    from ai_news_digest.llm.service import _ollama, _openai_compatible, _anthropic

    try:
        if provider == "ollama":
            raw = _ollama(prompt, {**settings, "max_tokens": max_tokens})
        elif provider in {"openai", "openrouter"}:
            raw = _openai_compatible(prompt, {**settings, "max_tokens": max_tokens})
        elif provider == "anthropic":
            raw = _anthropic(prompt, {**settings, "max_tokens": max_tokens})
        else:
            raise ValueError(f"Unsupported LLM provider '{provider}' for entity extraction")

        # Extract JSON array
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            entities = json.loads(match.group(0))
            if isinstance(entities, list):
                return [e for e in entities if isinstance(e, dict) and "name" in e and "type" in e]
    except Exception as exc:
        logger.warning("Entity extraction LLM call failed: %s", exc)
    return []


def extract_and_record_entities(run_id: str, digest_text: str, pre_extracted: list[dict] | None = None) -> list[dict]:
    """Extract entities from digest text and record them in SQLite.

    When running in agent-native mode, the agent can pass pre-extracted entities
    directly (from the structured digest JSON) to avoid an extra LLM call.
    """
    if pre_extracted is not None:
        entities = [e for e in pre_extracted if isinstance(e, dict) and "name" in e and "type" in e]
        if entities:
            record_entities(run_id, entities)
        return entities

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
