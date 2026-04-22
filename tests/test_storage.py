from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import ai_news_digest.storage.archive as archive


def test_save_daily_report_writes_files(tmp_path):
    with patch.object(archive, 'REPORT_ARCHIVE_DIR', tmp_path), patch.object(
        archive, 'get_llm_settings', return_value={'provider': 'openrouter', 'model': 'anthropic/claude-sonnet-4'}
    ), patch.object(
        archive, '_utc_now', return_value=datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc)
    ):
        paths = archive.save_daily_report(
            'BRIEF RUNDOWN:\nTest', [{'title': 'A', 'url': 'https://example.com/a'}], trends={'heating_up': []}
        )

    assert Path(paths['text']).exists()
    assert Path(paths['json']).exists()
    assert '"provider": "openrouter"' in Path(paths['json']).read_text(encoding='utf-8')
    assert '"trends"' in Path(paths['json']).read_text(encoding='utf-8')


def test_prune_old_reports_removes_only_expired(tmp_path):
    old_dir = tmp_path / '2026-03-01'
    fresh_dir = tmp_path / '2026-04-05'
    old_dir.mkdir()
    fresh_dir.mkdir()
    (old_dir / 'digest.txt').write_text('old', encoding='utf-8')
    (fresh_dir / 'digest.txt').write_text('fresh', encoding='utf-8')

    with patch.object(archive, 'REPORT_ARCHIVE_DIR', tmp_path), patch.object(
        archive, 'WEEKLY_ARCHIVE_DIR', tmp_path / 'weekly'
    ), patch.object(
        archive, '_utc_now', return_value=datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc)
    ):
        removed = archive.prune_old_reports(retention_days=30)

    assert str(old_dir) in removed
    assert not old_dir.exists()
    assert fresh_dir.exists()


def test_exclude_cross_day_duplicates_uses_recent_archives(tmp_path):
    day_dir = tmp_path / '2026-04-09'
    day_dir.mkdir()
    (day_dir / 'digest.json').write_text(
        '{"articles":[{"title":"OpenAI launches new coding model","url":"https://example.com/a?utm_source=x"}]}',
        encoding='utf-8',
    )

    with patch.object(archive, 'REPORT_ARCHIVE_DIR', tmp_path), patch.object(
        archive, '_utc_now', return_value=datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc)
    ):
        filtered, skipped = archive.exclude_cross_day_duplicates(
            [
                {'title': 'OpenAI launches new coding model today', 'url': 'https://another-site.com/rewrite'},
                {'title': 'Anthropic launches something else', 'url': 'https://example.com/b'},
            ],
            days=7,
        )

    assert skipped == 1
    assert len(filtered) == 1
    assert filtered[0]['title'] == 'Anthropic launches something else'
