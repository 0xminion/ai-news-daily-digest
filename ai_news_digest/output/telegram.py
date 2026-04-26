from __future__ import annotations

import html
import re
import time
from datetime import datetime

import requests

from ai_news_digest.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, get_destination_profiles, get_telegram_destinations, logger

TELEGRAM_MAX_LENGTH = 4096
HTML_CHUNK_REPAIR_HEADROOM = 128
HTML_BALANCE_TAG_RE = re.compile(r'<(/?)(a|b)(?:\s+[^>]*)?>', re.IGNORECASE)


def _repair_html_boundary(chunk: str, remaining: str) -> tuple[str, str]:
    """Close still-open inline tags in this chunk and reopen them in the remainder."""
    stack: list[tuple[str, str]] = []
    for match in HTML_BALANCE_TAG_RE.finditer(chunk):
        is_closing = match.group(1) == '/'
        tag = match.group(2).lower()
        token = match.group(0)
        if not is_closing:
            stack.append((tag, token))
            continue
        for index in range(len(stack) - 1, -1, -1):
            if stack[index][0] == tag:
                del stack[index:]
                break
    if not stack:
        return chunk, remaining
    closing_tags = ''.join(f'</{tag}>' for tag, _ in reversed(stack))
    reopening_tags = ''.join(token for _, token in stack)
    return chunk + closing_tags, reopening_tags + remaining


def _split_at_safe_boundary(html: str, max_len: int) -> tuple[str, str]:
    """Split HTML at a safe boundary (newline or tag end) without breaking tags."""
    if len(html) <= max_len:
        return html, ""
    candidate = html[:max_len]
    # Try to split at a double newline first
    last_double_newline = candidate.rfind("\n\n")
    if last_double_newline > max_len * 0.5:
        return html[:last_double_newline], html[last_double_newline:].lstrip()
    # Try to split at a single newline
    last_newline = candidate.rfind("\n")
    if last_newline > max_len * 0.5:
        return html[:last_newline], html[last_newline:].lstrip()
    # Try to split after the last complete HTML tag
    last_tag_end = candidate.rfind(">")
    if last_tag_end > max_len * 0.5:
        return html[:last_tag_end + 1], html[last_tag_end + 1:]
    # Fallback: just cut — but strip trailing partial tags to avoid breaking
    truncated = candidate
    # If we're inside a tag, walk back to before the <
    if "<" in truncated and (">" not in truncated or truncated.rfind("<") > truncated.rfind(">")):
        last_open = truncated.rfind("<")
        if last_open > max_len * 0.3:
            truncated = truncated[:last_open]
        else:
            # The tag itself is longer than max_len — try to include the closing >
            close_tag = html.find(">", max_len)
            if close_tag != -1 and close_tag <= max_len * 1.3:
                truncated = html[:close_tag + 1]
            else:
                # Tag is absurdly long; hard cut before the opening <
                truncated = html[:last_open]
    return truncated, html[len(truncated):]


SECTION_MARKERS = {
    'brief_rundown': 'Brief Rundown:',
    'highlights': 'Highlights:',
    'also_worth_knowing': 'Also Worth Knowing:',
    'research_builder_signals': 'Research / Builder Signals:',
}


def _escape(text: str) -> str:
    return html.escape(html.unescape(text))


def _normalize_heading_variants(text: str) -> str:
    normalized = text
    pattern_map = {
        r'^\s*brief\s+rundown:\s*$': SECTION_MARKERS['brief_rundown'],
        r'^\s*highlights:\s*$': SECTION_MARKERS['highlights'],
        r'^\s*also\s+worth\s+knowing:\s*$': SECTION_MARKERS['also_worth_knowing'],
        r'^\s*research\s*/\s*builder\s+signals:\s*$': SECTION_MARKERS['research_builder_signals'],
    }
    lines = []
    for line in normalized.split('\n'):
        stripped = line.strip()
        replaced = stripped
        for pattern, canonical in pattern_map.items():
            if re.match(pattern, stripped, flags=re.IGNORECASE):
                replaced = canonical
                break
        lines.append(replaced if stripped else line)
    return '\n'.join(lines)


def _parse_summary_sections(raw_summary: str) -> dict:
    remaining = _normalize_heading_variants(raw_summary)
    brief = SECTION_MARKERS['brief_rundown']
    highlights = SECTION_MARKERS['highlights']
    also = SECTION_MARKERS['also_worth_knowing']
    research = SECTION_MARKERS['research_builder_signals']

    if brief in remaining:
        remaining = remaining.split(brief, 1)[1]

    sections = {
        'rundown': '',
        'highlights': '',
        'also': '',
        'research': '',
    }

    if also in remaining:
        before_also, sections['also'] = remaining.split(also, 1)
    else:
        before_also = remaining

    if research in sections['also']:
        sections['also'], sections['research'] = sections['also'].split(research, 1)

    if highlights in before_also:
        sections['rundown'], sections['highlights'] = before_also.split(highlights, 1)
    else:
        sections['rundown'] = before_also

    return {key: value.strip() for key, value in sections.items()}


def _limit_numbered(raw: str, limit: int) -> str:
    if limit <= 0 or not raw:
        return ''
    entries = []
    current = []
    # Match 1.  1)  •  -  etc.
    pattern = re.compile(r'^(?:\d+[.\)]+\s+|•\s+|\-\s+)')
    for line in raw.split('\n'):
        if pattern.match(line.strip()) and current:
            entries.append('\n'.join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        entries.append('\n'.join(current).strip())
    return '\n\n'.join(entry for entry in entries[:limit] if entry)


def _split_bullet_blocks(raw: str) -> list[str]:
    blocks = []
    current = []
    for line in raw.split('\n'):
        stripped = line.rstrip()
        if not stripped.strip():
            if current:
                current.append('')
            continue
        if stripped.lstrip().startswith('- '):
            if current:
                blocks.append('\n'.join(current).strip())
            current = [stripped.strip()]
        elif current:
            current.append(stripped)
    if current:
        blocks.append('\n'.join(current).strip())
    return blocks


def _limit_bullets(raw: str, limit: int) -> str:
    if limit <= 0 or not raw:
        return ''
    return '\n\n'.join(_split_bullet_blocks(raw)[:limit])


def _source_match(line: str):
    """Match a plain source attribution line (URL now lives in the title markdown link)."""
    patterns = [
        r'^Source:\s*(?P<name>.+?)$',
    ]
    for pattern in patterns:
        match = re.match(pattern, line)
        if match:
            return match
    return None


def _bullet_match(line: str):
    """Match bullet lines like: • [Title](url) (Source) or • [subtype] [Title](url) (Source)"""
    patterns = [
        r'^\[?(?P<subtype>\w+)\]?\s+\[(?P<title>.+?)\]\((?P<url>https?://\S+?)\)\s*\((?P<source>.+?)\)$',
        r'^\[(?P<title>.+?)\]\((?P<url>https?://\S+?)\)\s*\((?P<source>.+?)\)$',
    ]
    for pattern in patterns:
        match = re.match(pattern, line)
        if match:
            return match
    return None


def _extract_markdown_link(line: str) -> tuple[str, str, str] | None:
    """Extract the first markdown [text](url) from a line.
    Returns (prefix, text, url) or None.
    Prefix is any text before the markdown link (e.g. '1. ').
    """
    m = re.search(r'^(?P<prefix>.*?)\[(?P<text>.+?)\]\((?P<url>https?://\S+?)\)(?P<suffix>.*)$', line)
    if m:
        return m.group('prefix'), m.group('text'), m.group('url')
    return None


def _split_inline_source(line: str) -> tuple[str, tuple[str, str] | None]:
    """Body text may no longer carry inline sources (source is on its own line now)."""
    return line, None


def _embed_links(text: str) -> str:
    """Convert bare URLs in body text into hidden embedded links on domain name."""
    def _replace_url(m):
        url = m.group(0)
        # Strip trailing punctuation that got caught by \S+ — but NOT parens (handled below)
        stripped = url.rstrip('.,>\'\"]!?;:$')
        # Parentheses are special: only strip if unbalanced
        open_parens = stripped.count('(')
        close_parens = stripped.count(')')
        if close_parens > open_parens:
            # Likely the ) is sentence punctuation, not part of the URL
            stripped = stripped.rstrip(')')
        if stripped.startswith('(') and not stripped.endswith(')'):
            stripped = stripped.lstrip('(')
        # If stripping removed everything (unlikely), keep original
        url = stripped if stripped else url
        domain = re.sub(r'^https?://(www\.)?', '', url).split('/')[0]
        return f'<a href="{url}">{_escape(domain)}</a>'
    return re.sub(r'https?://\S+', _replace_url, text)


def _format_highlights(raw: str, include_signal_annotations: bool = True) -> str:
    blocks = [block for block in raw.split('\n\n') if block.strip()]
    rendered_blocks = []
    for block in blocks:
        lines_in = [line.strip() for line in block.split('\n') if line.strip()]
        if not lines_in:
            continue
        title_line = lines_in[0]
        body_lines = []
        source_name = None
        source_url = None
        # Extract markdown link from title line, e.g. "1. [Title](url)"
        md_link = _extract_markdown_link(title_line)
        if md_link:
            prefix, title_line, source_url = md_link
            title_line = prefix + title_line
        for line in lines_in[1:]:
            source_match = _source_match(line)
            if source_match:
                source_name = source_match.group('name').strip()
                continue
            body, inline_source = _split_inline_source(line)
            if body:
                if not include_signal_annotations and ('Hacker News' in body or 'points' in body):
                    continue
                body_lines.append(_embed_links(_escape(body)))
            if inline_source:
                source_name, source_url = inline_source
        if source_url:
            rendered_title = f'<b><a href="{source_url}">{_escape(title_line)}</a></b>'
        else:
            rendered_title = f'<b>{_escape(title_line)}</b>'
        rendered = [rendered_title]
        rendered.extend(body_lines)
        if source_name:
            rendered.append(f'Source: {_escape(source_name)}')
        rendered_blocks.append('\n'.join(rendered))
    return '\n\n'.join(rendered_blocks)


def _format_bullets(raw: str) -> str:
    formatted_blocks = []
    for block in _split_bullet_blocks(raw):
        lines = [line.rstrip() for line in block.split('\n') if line.strip()]
        if not lines:
            continue
        first = lines[0].strip().lstrip('- ').lstrip('• ')
        # Normalize escaped brackets: \\[paper\\] → [paper]
        first = first.replace('\\[', '[').replace('\\]', ']')
        pipe = _bullet_match(first)
        if pipe:
            title = _escape(pipe.group('title').strip())
            source = _escape(pipe.group('source').strip())
            url = pipe.group('url').strip()
            subtype = pipe.groupdict().get('subtype')
            subtype_prefix = f"[{_escape(subtype.strip('[]'))}] " if subtype else ''
            rendered = [f'• {subtype_prefix}<a href="{url}">{title}</a> ({source})']
        else:
            rendered = [f'• {_embed_links(_escape(first))}']
        for extra in lines[1:]:
            rendered.append(f'  {_embed_links(_escape(extra.strip()))}')
        formatted_blocks.append('\n'.join(rendered))
    return '\n\n'.join(formatted_blocks)


def _format_digest(raw_summary: str, profile_name: str = 'default') -> list[str]:
    profiles = get_destination_profiles()
    profile = profiles.get(profile_name, profiles['default'])
    sections = _parse_summary_sections(raw_summary)
    today = datetime.now().strftime('%B %d, %Y')
    header = f"<b>{profile.get('headline_prefix', '')}AI Daily Digest — {_escape(today)}</b>\n\n"
    rundown = _escape(sections['rundown'])
    highlights = _format_highlights(_limit_numbered(sections['highlights'], profile.get('max_highlights', 10)), include_signal_annotations=profile.get('include_signal_annotations', True)) if sections['highlights'] else ''
    also = _format_bullets(_limit_bullets(sections['also'], profile.get('max_also', 10))) if profile.get('show_also_worth_knowing', True) and sections['also'] else ''
    research = _format_bullets(_limit_bullets(sections['research'], profile.get('max_research', 5))) if sections['research'] else ''

    parts = [header + rundown]
    if highlights:
        parts.append(f'<b>Highlights</b>\n\n{highlights}')
    if also:
        parts.append(f'<b>Also Worth Knowing</b>\n{also}')
    if research:
        parts.append(f'<b>Research / Builder Signals</b>\n{research}')

    body = '\n\n'.join(part.strip() for part in parts if part.strip())
    if len(body) <= TELEGRAM_MAX_LENGTH:
        return [body]

    chunks: list[str] = []
    current = ''
    for part in parts:
        candidate = (current + '\n\n' + part).strip() if current else part.strip()
        if len(candidate) <= TELEGRAM_MAX_LENGTH:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(part.strip()) <= TELEGRAM_MAX_LENGTH:
            current = part.strip()
        else:
            remaining = part.strip()
            split_limit = max(512, TELEGRAM_MAX_LENGTH - HTML_CHUNK_REPAIR_HEADROOM)
            while remaining:
                chunk, remaining = _split_at_safe_boundary(remaining, split_limit)
                if chunk:
                    chunk, remaining = _repair_html_boundary(chunk, remaining)
                    chunks.append(chunk)
            current = ''
    if current:
        if len(current) <= TELEGRAM_MAX_LENGTH:
            chunks.append(current)
        else:
            remaining = current
            split_limit = max(512, TELEGRAM_MAX_LENGTH - HTML_CHUNK_REPAIR_HEADROOM)
            while remaining:
                chunk, remaining = _split_at_safe_boundary(remaining, split_limit)
                if chunk:
                    chunk, remaining = _repair_html_boundary(chunk, remaining)
                    chunks.append(chunk)
    return chunks


def _send_message(text: str, retry: bool = True, bot_token: str | None = None, chat_id: str | None = None) -> bool:
    bot_token = bot_token or TELEGRAM_BOT_TOKEN
    chat_id = chat_id or TELEGRAM_CHAT_ID
    response = requests.post(
        f'https://api.telegram.org/bot{bot_token}/sendMessage',
        json={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True},
        timeout=30,
    )
    if response.status_code == 200:
        return True
    if response.status_code == 403:
        logger.error('Telegram 403: Bot was removed from the chat or chat ID is invalid.')
        return False
    if response.status_code == 429:
        retry_after = response.headers.get('Retry-After')
        if retry_after:
            wait = max(int(retry_after), 1)
            logger.warning('Telegram 429 — rate limited. Waiting %ds before retry.', wait)
            time.sleep(wait)
        else:
            time.sleep(5)
    if retry:
        return _send_message(text, retry=False, bot_token=bot_token, chat_id=chat_id)
    return False


def send_digest(raw_summary: str, destinations: list[dict] | None = None) -> bool:
    destinations = destinations or get_telegram_destinations()
    if not destinations:
        logger.error('No Telegram destinations configured')
        return False
    all_ok = True
    for destination in destinations:
        messages = _format_digest(raw_summary, profile_name=destination.get('profile', 'default'))
        dest_ok = True
        failed_messages = []
        for message in messages:
            if not _send_message(message, bot_token=destination.get('bot_token'), chat_id=destination.get('chat_id')):
                dest_ok = False
                all_ok = False
                failed_messages.append(message[:100])
        if dest_ok:
            logger.info('Digest sent to %s', destination.get('name', destination.get('chat_id')))
        else:
            logger.warning('Digest partially failed for %s: %d/%d messages sent', destination.get('name', destination.get('chat_id')), len(messages) - len(failed_messages), len(messages))
    return all_ok


def _chunk_html(html: str, max_len: int) -> list[str]:
    """Split HTML string into chunks that fit Telegram's message limit without breaking tags."""
    chunks = []
    remaining = html
    split_limit = max(512, max_len - HTML_CHUNK_REPAIR_HEADROOM)
    while remaining:
        chunk, remaining = _split_at_safe_boundary(remaining, split_limit)
        if chunk:
            chunk, remaining = _repair_html_boundary(chunk, remaining)
            chunks.append(chunk)
        if not remaining:
            break
    return chunks


def send_weekly_report(weekly_html: str, destinations: list[dict] | None = None) -> bool:
    """Send a weekly report (already HTML) to destinations with safe chunking."""
    destinations = destinations or get_telegram_destinations()
    if not destinations:
        logger.error('No Telegram destinations configured')
        return False
    all_ok = True
    chunks = _chunk_html(weekly_html, TELEGRAM_MAX_LENGTH)
    for destination in destinations:
        ok = True
        failed_chunks = []
        for chunk in chunks:
            if not _send_message(chunk, bot_token=destination.get('bot_token'), chat_id=destination.get('chat_id')):
                ok = False
                all_ok = False
                failed_chunks.append(chunk[:100])
        if ok:
            logger.info('Weekly report sent to %s', destination.get('name', destination.get('chat_id')))
        else:
            logger.warning('Weekly report partially failed for %s: %d/%d chunks sent',
                           destination.get('name', destination.get('chat_id')),
                           len(chunks) - len(failed_chunks), len(chunks))
    return all_ok


def send_text_report(text: str, destinations: list[dict] | None = None) -> bool:
    destinations = destinations or get_telegram_destinations()
    all_ok = True
    for destination in destinations:
        if not _send_message(_escape(text), bot_token=destination.get('bot_token'), chat_id=destination.get('chat_id')):
            all_ok = False
    return all_ok
