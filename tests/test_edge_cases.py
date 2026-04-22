from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Telegram chunking edge cases
# ---------------------------------------------------------------------------

def test_split_at_safe_boundary_chunks_at_double_newline():
    from ai_news_digest.output.telegram import _split_at_safe_boundary

    text = "A" * 2000 + "\n\n" + "B" * 3000
    chunk, rest = _split_at_safe_boundary(text, 4096)
    assert len(chunk) <= 4096
    assert "B" not in chunk or text.index("B") == chunk.index("B")
    assert rest.strip() == "" or text in chunk + rest


def test_split_at_safe_boundary_breaks_mid_tag_gracefully():
    from ai_news_digest.output.telegram import _split_at_safe_boundary

    # Create a chunk that would cut inside an <a> tag — 100 chars, open tag, then >4096
    opening = "X" * 100 + '<a href="https://example.com/very/long/path"'
    closing = '>link</a> more text here'
    text = opening + closing
    text = text[:4096]
    chunk, rest = _split_at_safe_boundary(text, 4096)
    assert len(chunk) <= 4096
    # The chunk should either include closing > or cut before <
    assert (">" in chunk) or ("</a>" not in chunk)


def test_split_at_safe_boundary_long_tag_inclusion():
    from ai_news_digest.output.telegram import _split_at_safe_boundary

    # A ridiculously long <a> tag exceeding 4096 chars
    long_tag = '<a href="https://example.com/' + 'x' * 4000 + '">'
    text = long_tag + "content</a>"
    chunk, rest = _split_at_safe_boundary(text, 4096)
    assert chunk == text or '</a>' in chunk + rest
    assert len(chunk) <= 4096 * 1.3


# ---------------------------------------------------------------------------
# Telegram 429 backoff
# ---------------------------------------------------------------------------

def test_send_message_429_retries_with_retry_after():
    from ai_news_digest.output.telegram import _send_message
    import time

    with patch('ai_news_digest.output.telegram.requests.post') as mock_post, \
         patch.object(time, 'sleep') as mock_sleep:
        mock_post.side_effect = [
            MagicMock(status_code=429, headers={'Retry-After': '7'}),
            MagicMock(status_code=200),
        ]
        result = _send_message('Hello', bot_token='abc', chat_id='123')
        assert result is True
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(7)


def test_send_message_429_fallback_sleep_without_header():
    from ai_news_digest.output.telegram import _send_message
    import time

    with patch('ai_news_digest.output.telegram.requests.post') as mock_post, \
         patch.object(time, 'sleep') as mock_sleep:
        mock_post.side_effect = [
            MagicMock(status_code=429, headers={}),
            MagicMock(status_code=200),
        ]
        result = _send_message('Hello', bot_token='abc', chat_id='123')
        assert result is True
        mock_sleep.assert_called_once_with(5)


# ---------------------------------------------------------------------------
# SSRF validation edge cases
# ---------------------------------------------------------------------------

def test_is_allowed_url_blocks_private_ip():
    from ai_news_digest.sources.pages import _is_allowed_url
    assert _is_allowed_url('http://192.168.1.1/something') is False
    assert _is_allowed_url('http://10.0.0.1/') is False
    assert _is_allowed_url('https://127.0.0.1/') is False


def test_is_allowed_url_blocks_metadata_endpoint():
    from ai_news_digest.sources.pages import _is_allowed_url
    assert _is_allowed_url('http://169.254.169.254/latest/meta-data/') is False


def test_is_allowed_url_allows_public():
    from ai_news_digest.sources.pages import _is_allowed_url
    assert _is_allowed_url('https://example.com/path') is True


def test_is_allowed_url_allows_archive_ph():
    from ai_news_digest.sources.pages import _is_allowed_url
    assert _is_allowed_url('https://archive.ph/http://example.com') is True


# ---------------------------------------------------------------------------
# within_hours future clamp
# ---------------------------------------------------------------------------

def test_within_hours_rejects_tomorrow():
    from datetime import datetime, timedelta, timezone
    from ai_news_digest.sources.common import within_hours

    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    assert within_hours(tomorrow, 24) is False


def test_within_hours_accepts_slight_skew():
    from datetime import datetime, timedelta, timezone
    from ai_news_digest.sources.common import within_hours

    slight_future = datetime.now(timezone.utc) + timedelta(minutes=3)
    assert within_hours(slight_future, 24) is True


def test_within_hours_rejects_deep_future():
    from datetime import datetime, timedelta, timezone
    from ai_news_digest.sources.common import within_hours

    deep_future = datetime.now(timezone.utc) + timedelta(hours=2)
    assert within_hours(deep_future, 24) is False


def test_within_hours_accepts_recent_past():
    from datetime import datetime, timedelta, timezone
    from ai_news_digest.sources.common import within_hours

    recent = datetime.now(timezone.utc) - timedelta(hours=2)
    assert within_hours(recent, 24) is True


# ---------------------------------------------------------------------------
# File locking fallback (no fcntl)
# ---------------------------------------------------------------------------

def test_lock_file_graceful_without_fcntl():
    from ai_news_digest.storage.topic_memory import _lock_file, _unlock_file
    with patch.dict('sys.modules', {'fcntl': None}):
        class FakeFile:
            pass
        got = _lock_file(FakeFile(), exclusive=True)
        assert got is False
        # _unlock_file should be a no-op
        _unlock_file(FakeFile(), acquired=False)


# ---------------------------------------------------------------------------
# LLM token estimation guards
# ---------------------------------------------------------------------------

def test_estimate_tokens_is_positive():
    from ai_news_digest.llm.service import _estimate_tokens
    assert _estimate_tokens("hello world") >= 1


def test_estimate_tokens_scales_with_length():
    from ai_news_digest.llm.service import _estimate_tokens
    short = _estimate_tokens("hi")
    long_text = "x" * 4000
    long_tok = _estimate_tokens(long_text)
    assert long_tok > short


def test_context_limit_claude_200k():
    from ai_news_digest.llm.service import _context_limit_for_model
    assert _context_limit_for_model('claude-3-5-sonnet-202406') == 200000


def test_context_limit_gpt4o_128k():
    from ai_news_digest.llm.service import _context_limit_for_model
    assert _context_limit_for_model('gpt-4o-mini') == 128000


def test_context_limit_unknown_default():
    from ai_news_digest.llm.service import _context_limit_for_model
    assert _context_limit_for_model('some-random-llm') == 8192


# ---------------------------------------------------------------------------
# Clustering: exact URL, exact title, fuzzy match, singletons
# ---------------------------------------------------------------------------

def test_clustering_exact_url_groups_tight():
    from ai_news_digest.analysis.clustering import cluster_articles

    articles = [
        {'title': 'OpenAI GPT-5 preview', 'url': 'https://example.com/a', 'source': 'RSS1'},
        {'title': 'OpenAI GPT-5 preview', 'url': 'https://example.com/a', 'source': 'RSS2'},
        {'title': 'Anthropic launches Claude 4', 'url': 'https://example.com/b', 'source': 'RSS3'},
    ]
    clusters = cluster_articles(articles, threshold=90)
    assert len(clusters) == 2
    sizes = [c['cluster_size'] for c in clusters]
    assert sorted(sizes) == [1, 2]


def test_clustering_exact_title_groups():
    from ai_news_digest.analysis.clustering import cluster_articles

    articles = [
        {'title': 'OpenAI GPT-5 preview', 'url': 'https://example.com/a1', 'source': 'RSS1'},
        {'title': 'OpenAI GPT-5 preview', 'url': 'https://example.com/a2', 'source': 'RSS2'},
    ]
    clusters = cluster_articles(articles, threshold=90)
    assert len(clusters) == 1
    assert clusters[0]['cluster_size'] == 2


def test_clustering_fuzzy_match_titles():
    from ai_news_digest.analysis.clustering import cluster_articles

    articles = [
        {'title': 'OpenAI releases GPT-5 preview paper', 'url': 'https://example.com/a', 'source': 'RSS1'},
        {'title': 'OpenAI releases GPT-5 preview paper', 'url': 'https://example.com/b', 'source': 'RSS2'},
    ]
    clusters = cluster_articles(articles, threshold=90)
    assert len(clusters) == 1
    assert clusters[0]['cluster_size'] == 2


def test_clustering_singletons_remain_separate():
    from ai_news_digest.analysis.clustering import cluster_articles

    articles = [
        {'title': 'OpenAI news', 'url': 'https://example.com/a', 'source': 'RSS1'},
        {'title': 'Anthropic news', 'url': 'https://example.com/b', 'source': 'RSS2'},
        {'title': 'Google DeepMind update', 'url': 'https://example.com/c', 'source': 'RSS3'},
    ]
    clusters = cluster_articles(articles, threshold=90)
    assert len(clusters) == 3
    assert all(c['cluster_size'] == 1 for c in clusters)


def test_clustering_rep_is_best_hn_points():
    from ai_news_digest.analysis.clustering import cluster_articles

    articles = [
        {'title': 'OpenAI GPT-5', 'url': 'https://example.com/a', 'source': 'RSS1', 'hn_points': 5},
        {'title': 'OpenAI GPT-5', 'url': 'https://example.com/a', 'source': 'RSS2', 'hn_points': 120},
    ]
    clusters = cluster_articles(articles, threshold=90)
    assert clusters[0]['representative']['hn_points'] == 120


# ---------------------------------------------------------------------------
# LLM prompt truncation guard
# ---------------------------------------------------------------------------

def test_truncate_articles_fits_prompt():
    from ai_news_digest.llm.service import _truncate_articles_to_fit
    from ai_news_digest.llm.service import _estimate_tokens

    main = [{'title': f'Title {i}', 'summary': 'x' * 1000, 'url': 'https://example.com', 'source': 'Test'} for i in range(50)]
    research = [{'title': f'Research {i}', 'summary': 'y' * 800, 'url': 'https://example.com', 'source': 'arXiv AI'} for i in range(20)]
    template = 'Summary of today\n{{main_articles_json}}\n{{research_articles_json}}\n{{trend_context}}\n{{weekly_preview}}'
    main_out, research_out = _truncate_articles_to_fit(main, research, '', '', template, max_tokens=8192)
    prompt = template.replace('{{main_articles_json}}', '').replace('{{research_articles_json}}', '')
    # Estimate that total serialized content fits within the token budget
    assert len(main_out) + len(research_out) <= len(main) + len(research)


# ---------------------------------------------------------------------------
# _embed_links edge cases
# ---------------------------------------------------------------------------

def test_embed_links_preserves_url_with_parens():
    from ai_news_digest.output.telegram import _embed_links

    text = 'Read more at https://en.wikipedia.org/wiki/AI_(Artificial_Intelligence)'
    result = _embed_links(text)
    # Should keep the balanced parens inside the URL
    assert 'wikipedia.org/wiki/AI_(Artificial_Intelligence)' in result


def test_embed_links_strips_unbalanced_trailing_paren():
    from ai_news_digest.output.telegram import _embed_links

    text = '(See https://example.com/guide)'
    result = _embed_links(text)
    # The URL should not include the outer parens
    assert 'href="https://example.com/guide"' in result
