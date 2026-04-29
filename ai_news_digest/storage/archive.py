from __future__ import annotations
import json
import shutil
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from rapidfuzz import fuzz

from ai_news_digest.config import CROSS_DAY_DEDUP_DAYS, RETENTION_DAYS, REPORT_ARCHIVE_DIR, WEEKLY_ARCHIVE_DIR, logger, get_llm_settings, _ensure_directories

_TRACKING_QUERY_KEYS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id", "utm_name", "ref", "ref_src", "fbclid", "gclid", "mc_cid", "mc_eid"}

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    parsed = urlparse(str(url).strip())
    if not parsed.scheme or not parsed.netloc:
        return str(url).strip()
    query = urlencode([(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in _TRACKING_QUERY_KEYS], doseq=True)
    normalized = parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower(), path=str(parsed.path).rstrip('/') or '/', query=query, fragment='')
    return urlunparse(normalized)

def normalize_title(title: str | None) -> str:
    raw = (title or '').strip().lower()
    out = ''.join(ch if ch.isalnum() or ch in {' ', '+', '#', '-'} else ' ' for ch in raw)
    return ' '.join(out.split())

def article_fingerprint(article: dict) -> str:
    return normalize_url(article.get('url')) or normalize_title(article.get('title'))

def save_daily_report(summary: str, articles: list[dict], trends: dict | None = None, clusters: list[dict] | None = None) -> dict[str, str]:
    _ensure_directories()
    timestamp = _utc_now()
    day_dir = None
    day_dir = REPORT_ARCHIVE_DIR / timestamp.strftime('%Y-%m-%d')
    day_dir.mkdir(parents=True, exist_ok=True)
    llm = get_llm_settings()
    txt_path = day_dir / 'digest.txt'
    json_path = day_dir / 'digest.json'
    txt_path.write_text(summary, encoding='utf-8')
    payload = {
        'saved_at': timestamp.isoformat(),
        'provider': llm['provider'],
        'model': llm['model'],
        'article_count': len(articles),
        'articles': articles,
        'summary': summary,
        'trends': trends or {},
        'clusters': clusters or [],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    # Also store in SQLite FTS
    try:
        highlights = json.dumps(payload.get('articles', [])[:10])
        research = json.dumps([a for a in payload.get('articles', []) if a.get('source') in {'arXiv AI','arXiv ML','GitHub Blog AI/ML'}])
        topics = json.dumps(trends or {})
        from ai_news_digest.storage.sqlite_store import save_daily_report as sql_save
        sql_save(
            run_id=str(timestamp.timestamp()),
            saved_at=timestamp.isoformat(),
            digest_text=summary,
            highlights_json=highlights,
            research_json=research,
            topics_json=topics,
            article_count=len(articles),
            provider=llm['provider'],
            model=llm['model'],
            filepath=str(json_path),
        )
    except Exception as e:
        logger.warning("SQLite FTS save failed: %s", e)
    logger.info('Saved daily report copy to %s', day_dir)
    return {'text': str(txt_path), 'json': str(json_path)}

def save_weekly_report(payload: dict, text: str) -> dict[str, str]:
    _ensure_directories()
    timestamp = _utc_now()
    from ai_news_digest.config import WEEKLY_ARCHIVE_DIR
    week_dir = WEEKLY_ARCHIVE_DIR / timestamp.strftime('%Y-W%U')
    week_dir.mkdir(parents=True, exist_ok=True)
    txt_path = week_dir / 'weekly.txt'
    json_path = week_dir / 'weekly.json'
    txt_path.write_text(text, encoding='utf-8')
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    try:
        from ai_news_digest.storage.sqlite_store import save_weekly_report as sql_save_weekly
        sql_save_weekly(
            run_id=f"weekly-{timestamp.timestamp()}",
            saved_at=timestamp.isoformat(),
            digest_text=text,
            highlights_json=json.dumps(payload.get('highlights_of_the_week', [])),
            topics_json=json.dumps(payload.get('trending_directions', [])),
            provider='',
            model='',
            filepath=str(json_path),
        )
    except Exception as e:
        logger.warning("SQLite weekly save failed: %s", e)
    return {'text': str(txt_path), 'json': str(json_path)}

def load_recent_report_payloads(days: int, include_today: bool = False) -> list[dict]:
    _ensure_directories()
    REPORT_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    cutoff_date = (_utc_now() - timedelta(days=days)).date()
    today = _utc_now().date()
    payloads = []
    for child in sorted(REPORT_ARCHIVE_DIR.iterdir(), reverse=True):
        if not child.is_dir():
            continue
        try:
            day = datetime.strptime(child.name, '%Y-%m-%d').date()
        except ValueError:
            continue
        if day < cutoff_date:
            continue
        if not include_today and day == today:
            continue
        digest_path = child / 'digest.json'
        if not digest_path.exists():
            continue
        try:
            payloads.append(json.loads(digest_path.read_text(encoding='utf-8')))
        except json.JSONDecodeError as exc:
            logger.warning('Skipping unreadable archive %s: %s', digest_path, exc)
    return payloads

def load_recent_articles(days: int, include_today: bool = False) -> list[dict]:
    articles = []
    for payload in load_recent_report_payloads(days, include_today=include_today):
        articles.extend(payload.get('articles', []))
    return articles

def exclude_cross_day_duplicates(articles: list[dict], days: int = CROSS_DAY_DEDUP_DAYS) -> tuple[list[dict], int]:
    historical_articles = load_recent_articles(days=days, include_today=False)
    historical = {article_fingerprint(article) for article in historical_articles}
    historical_titles = [normalize_title(article.get('title')) for article in historical_articles if normalize_title(article.get('title'))]
    historical_title_set = set(historical_titles)
    filtered, skipped, seen_current, seen_current_set = [], 0, set(), set()
    for article in articles:
        fp = article_fingerprint(article)
        title_fp = normalize_title(article.get('title'))
        if fp and fp in historical:
            skipped += 1
            continue
        if fp and fp in seen_current:
            skipped += 1
            continue
        if title_fp and title_fp in historical_title_set:
            skipped += 1
            continue
        if title_fp and title_fp in seen_current_set:
            skipped += 1
            continue
        fuzzy_historical, fuzzy_current = False, False
        if title_fp:
            for prior_title in historical_titles:
                if abs(len(prior_title) - len(title_fp)) <= 10 and fuzz.ratio(title_fp, prior_title) >= 90:
                    fuzzy_historical = True
                    break
            if not fuzzy_historical:
                for prior_title in list(seen_current_set):
                    if abs(len(prior_title) - len(title_fp)) <= 10 and fuzz.ratio(title_fp, prior_title) >= 90:
                        fuzzy_current = True
                        break
        if fuzzy_historical:
            skipped += 1
            continue
        if fuzzy_current:
            skipped += 1
            continue
        if fp:
            seen_current.add(fp)
        if title_fp:
            seen_current_set.add(title_fp)
        filtered.append(article)
    return filtered, skipped

def prune_old_reports(retention_days: int = RETENTION_DAYS) -> list[str]:
    _ensure_directories()
    if retention_days < 1:
        raise ValueError('retention_days must be at least 1')
    removed = []
    cutoff_date = (_utc_now() - timedelta(days=retention_days)).date()
    for base in (REPORT_ARCHIVE_DIR, WEEKLY_ARCHIVE_DIR):
        base.mkdir(parents=True, exist_ok=True)
        for child in list(base.iterdir()):
            if not child.is_dir():
                continue
            try:
                if base == REPORT_ARCHIVE_DIR:
                    day = datetime.strptime(child.name, '%Y-%m-%d').date()
                else:
                    year, week = child.name.split('-W')
                    day = datetime.strptime(f'{year} {week} 1', '%Y %U %w').date()
            except Exception:
                continue
            if day < cutoff_date:
                shutil.rmtree(str(child), ignore_errors=True)
                removed.append(str(child))
    return removed
