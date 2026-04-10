from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import REPORT_ARCHIVE_DIR, RETENTION_DAYS, logger, get_llm_settings


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def save_daily_report(summary: str, articles: list[dict], messages: list[str] | None = None) -> dict[str, str]:
    """Persist a copy of the daily report and its metadata."""
    timestamp = _utc_now()
    day_dir = REPORT_ARCHIVE_DIR / timestamp.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)

    llm = get_llm_settings()
    txt_path = day_dir / "digest.txt"
    json_path = day_dir / "digest.json"

    txt_path.write_text(summary, encoding="utf-8")
    payload = {
        "saved_at": timestamp.isoformat(),
        "provider": llm["provider"],
        "model": llm["model"],
        "article_count": len(articles),
        "articles": articles,
        "messages": messages or [],
        "summary": summary,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved daily report copy to %s", day_dir)
    return {"text": str(txt_path), "json": str(json_path)}


def prune_old_reports(retention_days: int = RETENTION_DAYS) -> list[str]:
    """Delete archived reports older than the retention window."""
    if retention_days < 1:
        raise ValueError("retention_days must be at least 1")

    REPORT_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    cutoff_date = (_utc_now() - timedelta(days=retention_days)).date()
    removed: list[str] = []

    for child in REPORT_ARCHIVE_DIR.iterdir():
        if not child.is_dir():
            continue
        try:
            day = datetime.strptime(child.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if day < cutoff_date:
            for nested in sorted(child.rglob("*"), reverse=True):
                if nested.is_file():
                    nested.unlink(missing_ok=True)
                elif nested.is_dir():
                    nested.rmdir()
            child.rmdir()
            removed.append(str(child))

    if removed:
        logger.info("Pruned %d archived report directorie(s)", len(removed))
    return removed
