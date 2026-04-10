from ai_news_digest.sources.pipeline import *
from ai_news_digest.sources.pages import *
from ai_news_digest.sources.hackernews import *
from ai_news_digest.sources.rss import matches_ai_keywords
from ai_news_digest.sources.common import parse_entry_date as get_publish_date


def is_within_window(entry, hours=24):
    dt = get_publish_date(entry)
    from ai_news_digest.sources.common import within_hours
    return within_hours(dt, hours)
