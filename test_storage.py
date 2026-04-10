from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import storage


def test_save_daily_report_writes_files(tmp_path):
    with patch.object(storage, "REPORT_ARCHIVE_DIR", tmp_path), patch.object(
        storage, "get_llm_settings", return_value={"provider": "openrouter", "model": "anthropic/claude-sonnet-4"}
    ), patch.object(
        storage, "_utc_now", return_value=datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc)
    ):
        paths = storage.save_daily_report("BRIEF RUNDOWN:\nTest", [{"title": "A"}], ["message"])

    assert Path(paths["text"]).exists()
    assert Path(paths["json"]).exists()
    assert "BRIEF RUNDOWN" in Path(paths["text"]).read_text(encoding="utf-8")
    assert '"provider": "openrouter"' in Path(paths["json"]).read_text(encoding="utf-8")


def test_prune_old_reports_removes_only_expired(tmp_path):
    old_dir = tmp_path / "2026-03-01"
    fresh_dir = tmp_path / "2026-04-05"
    old_dir.mkdir()
    fresh_dir.mkdir()
    (old_dir / "digest.txt").write_text("old", encoding="utf-8")
    (fresh_dir / "digest.txt").write_text("fresh", encoding="utf-8")

    with patch.object(storage, "REPORT_ARCHIVE_DIR", tmp_path), patch.object(
        storage, "_utc_now", return_value=datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc)
    ):
        removed = storage.prune_old_reports(retention_days=30)

    assert str(old_dir) in removed
    assert not old_dir.exists()
    assert fresh_dir.exists()
