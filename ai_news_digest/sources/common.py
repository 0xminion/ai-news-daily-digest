from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional


def parse_entry_date(entry) -> Optional[datetime]:
    for field in ('published_parsed', 'updated_parsed', 'created_parsed'):
        parsed = getattr(entry, field, None)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    for field in ('published', 'updated', 'created'):
        value = getattr(entry, field, None)
        if not value:
            continue
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def within_hours(dt: Optional[datetime], hours: int) -> bool:
    if dt is None:
        return False
    now = datetime.now(timezone.utc)
    delta = now - dt
    return 0 <= delta.total_seconds() <= hours * 3600
