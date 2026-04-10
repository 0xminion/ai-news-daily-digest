from __future__ import annotations

import html
import re
from datetime import datetime

import requests

from ai_news_digest.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, get_destination_profiles, get_telegram_destinations, logger

TELEGRAM_MAX_LENGTH = 4096


def _escape(text: str) -> str:
    return html.escape(html.unescape(text))


def _parse_summary_sections(raw_summary: str) -> dict:
    remaining = raw_summary
    if 'BRIEF RUNDOWN:' in remaining:
        remaining = remaining.split('BRIEF RUNDOWN:', 1)[1]

    sections = {
        'rundown': '',
        'trend': '',
        'highlights': '',
        'also': '',
        'research': '',
        'weekly_preview': '',
    }

    if 'ALSO WORTH KNOWING:' in remaining:
        before_also, sections['also'] = remaining.split('ALSO WORTH KNOWING:', 1)
    else:
        before_also = remaining

    if 'RESEARCH / BUILDER SIGNALS:' in sections['also']:
        sections['also'], sections['research'] = sections['also'].split('RESEARCH / BUILDER SIGNALS:', 1)
    if 'WEEKLY PREVIEW:' in sections['research']:
        sections['research'], sections['weekly_preview'] = sections['research'].split('WEEKLY PREVIEW:', 1)
    elif 'WEEKLY PREVIEW:' in sections['also']:
        sections['also'], sections['weekly_preview'] = sections['also'].split('WEEKLY PREVIEW:', 1)

    if 'HIGHLIGHTS:' in before_also:
        pre_highlights, sections['highlights'] = before_also.split('HIGHLIGHTS:', 1)
    else:
        pre_highlights = before_also

    if 'TREND WATCH:' in pre_highlights:
        sections['rundown'], sections['trend'] = pre_highlights.split('TREND WATCH:', 1)
    else:
        sections['rundown'] = pre_highlights

    return {key: value.strip() for key, value in sections.items()}


def _limit_numbered(raw: str, limit: int) -> str:
    if limit <= 0 or not raw:
        return ''
    entries = []
    current = []
    for line in raw.split('\n'):
        if re.match(r'^\d+\.\s', line.strip()) and current:
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


def _format_highlights(raw: str, include_signal_annotations: bool = True) -> str:
    lines = []
    for line in raw.split('\n'):
        line = line.strip()
        if not line:
            continue
        source_match = re.match(r'^Source:\s*(.+?)\s*-\s*(https?://\S+)$', line)
        if source_match:
            name = _escape(source_match.group(1).strip())
            url = source_match.group(2).strip()
            lines.append(f'Source: <a href="{url}">{name}</a>')
        elif re.match(r'^\d+\.\s', line):
            if lines:
                lines.append('')
            lines.append(f'<b>{_escape(line)}</b>')
        elif not include_signal_annotations and ('Hacker News' in line or 'points' in line):
            continue
        else:
            lines.append(_escape(line))
    return '\n'.join(lines)


def _format_bullets(raw: str) -> str:
    formatted_blocks = []
    for block in _split_bullet_blocks(raw):
        lines = [line.rstrip() for line in block.split('\n') if line.strip()]
        if not lines:
            continue
        first = lines[0].strip().lstrip('- ')
        pipe = re.match(r'^(.+?)\s*\|\s*(.+?)\s*-\s*(https?://\S+)$', first)
        if pipe:
            title = _escape(pipe.group(1).strip())
            source = _escape(pipe.group(2).strip())
            url = pipe.group(3).strip()
            rendered = [f'• <a href="{url}">{title}</a> ({source})']
        else:
            rendered = [f'• {_escape(first)}']
        for extra in lines[1:]:
            rendered.append(f'  {_escape(extra.strip())}')
        formatted_blocks.append('\n'.join(rendered))
    return '\n\n'.join(formatted_blocks)


def _format_trend_watch(raw: str) -> str:
    lines = []
    for line in raw.split('\n'):
        s = line.strip()
        if not s:
            continue
        if s.endswith('Trend Watch:'):
            lines.append(f'<b>{_escape(s)}</b>')
        elif s.lower() in {'heating up:', 'cooling down:'}:
            lines.append(f'<b>{_escape(s.title())}</b>')
        elif s.startswith('-'):
            lines.append(f"• {_escape(s[1:].strip())}")
        else:
            lines.append(_escape(s))
    return '\n'.join(lines)


def _format_digest(raw_summary: str, profile_name: str = 'default') -> list[str]:
    profiles = get_destination_profiles()
    profile = profiles.get(profile_name, profiles['default'])
    sections = _parse_summary_sections(raw_summary)
    today = datetime.now().strftime('%B %d, %Y')
    header = f"<b>{profile.get('headline_prefix', '')}AI Daily Digest — {_escape(today)}</b>\n\n"
    rundown = _escape(sections['rundown'])
    trend_watch = _format_trend_watch(sections['trend']) if profile.get('show_trend_watch', True) and sections['trend'] else ''
    highlights = _format_highlights(_limit_numbered(sections['highlights'], profile.get('max_highlights', 10)), include_signal_annotations=profile.get('include_signal_annotations', True)) if sections['highlights'] else ''
    also = _format_bullets(_limit_bullets(sections['also'], profile.get('max_also', 10))) if profile.get('show_also_worth_knowing', True) and sections['also'] else ''
    research = _format_bullets(_limit_bullets(sections['research'], profile.get('max_research', 5))) if sections['research'] else ''
    weekly_preview = _format_bullets(_limit_bullets(sections['weekly_preview'], 6)) if sections['weekly_preview'] else ''

    parts = [header + rundown]
    if trend_watch:
        parts.append(f'<b>Trend Watch:</b>\n{trend_watch}')
    if highlights:
        parts.append(f'<b>Must-Know Highlights:</b>\n\n{highlights}')
    if also:
        parts.append(f'<b>Also Worth Knowing:</b>\n{also}')
    if research:
        parts.append(f'<b>Research / Builder Signals:</b>\n{research}')
    if weekly_preview:
        parts.append(f'<b>Weekly Preview:</b>\n{weekly_preview}')

    body = '\n\n'.join(part.strip() for part in parts if part.strip())
    if len(body) <= TELEGRAM_MAX_LENGTH:
        return [body]

    chunks = []
    current = ''
    for part in parts:
        candidate = (current + '\n\n' + part).strip() if current else part.strip()
        if len(candidate) <= TELEGRAM_MAX_LENGTH:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = part.strip()
    if current:
        chunks.append(current)
    return [chunk[:TELEGRAM_MAX_LENGTH] for chunk in chunks]


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
        ok = True
        for message in messages:
            if not _send_message(message, bot_token=destination.get('bot_token'), chat_id=destination.get('chat_id')):
                ok = False
                all_ok = False
                break
        if ok:
            logger.info('Digest sent to %s', destination.get('name', destination.get('chat_id')))
    return all_ok


def send_text_report(text: str, destinations: list[dict] | None = None) -> bool:
    destinations = destinations or get_telegram_destinations()
    all_ok = True
    for destination in destinations:
        if not _send_message(_escape(text), bot_token=destination.get('bot_token'), chat_id=destination.get('chat_id')):
            all_ok = False
    return all_ok
