import html
import re
from datetime import datetime

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, logger


TELEGRAM_MAX_LENGTH = 4096


def _escape(text: str) -> str:
    """Escape text for Telegram HTML parse mode."""
    return html.escape(text)


def _format_section_lines(raw: str) -> str:
    """Format numbered highlights with source links."""
    lines = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        source_match = re.match(
            r"^Source:\s*(.+?)\s*-\s*(https?://\S+)$", line
        )
        if source_match:
            name = _escape(source_match.group(1).strip())
            url = source_match.group(2).strip()
            lines.append(f'Source: <a href="{url}">{name}</a>')
        elif re.match(r"^\d+\.\s", line):
            lines.append(f"<b>{_escape(line)}</b>")
        else:
            lines.append(_escape(line))
    return "\n".join(lines)


def _format_digest(raw_summary: str) -> list[str]:
    """Format the LLM summary into Telegram HTML messages.

    Returns a list of 1 or 2 messages, each under 4096 chars.
    """
    today = datetime.now().strftime("%B %d, %Y")
    header = f"<b>AI Daily Digest \u2014 {_escape(today)}</b>\n\n"

    # Parse the LLM output into rundown, highlights, and also-worth-knowing
    rundown_raw = ""
    highlights_raw = ""
    also_raw = ""

    remaining = raw_summary
    if "BRIEF RUNDOWN:" in remaining:
        remaining = remaining.split("BRIEF RUNDOWN:", 1)[1]

    if "ALSO WORTH KNOWING:" in remaining:
        before_also, also_raw = remaining.split("ALSO WORTH KNOWING:", 1)
        also_raw = also_raw.strip()
    else:
        before_also = remaining

    if "HIGHLIGHTS:" in before_also:
        rundown_raw, highlights_raw = before_also.split("HIGHLIGHTS:", 1)
        rundown_raw = rundown_raw.strip()
        highlights_raw = highlights_raw.strip()
    else:
        rundown_raw = before_also.strip()

    # Format rundown
    rundown = _escape(rundown_raw)

    # Format highlights — convert URLs to clickable links
    highlights = _format_section_lines(highlights_raw) if highlights_raw else ""

    # Format also-worth-knowing — title links only
    also_section = ""
    if also_raw:
        also_lines = []
        for line in also_raw.split("\n"):
            line = line.strip().lstrip("- ")
            if not line:
                continue
            # Match "Headline | Source - URL"
            pipe_match = re.match(
                r"^(.+?)\s*\|\s*(.+?)\s*-\s*(https?://\S+)$", line
            )
            if pipe_match:
                title = _escape(pipe_match.group(1).strip())
                source = _escape(pipe_match.group(2).strip())
                url = pipe_match.group(3).strip()
                also_lines.append(
                    f'\u2022 <a href="{url}">{title}</a> ({source})'
                )
            else:
                # Fallback: try "Headline - URL" or just escaped text
                url_match = re.search(r"(https?://\S+)", line)
                if url_match:
                    url = url_match.group(1)
                    title_part = line[: url_match.start()].rstrip(" -|")
                    also_lines.append(
                        f'\u2022 <a href="{url}">{_escape(title_part.strip())}</a>'
                    )
                else:
                    also_lines.append(f"\u2022 {_escape(line)}")
        if also_lines:
            also_section = "\n".join(also_lines)

    # Build the full message
    rundown_section = f"{header}{rundown}"
    highlights_section = (
        f"\n\n<b>Must-Know Highlights:</b>\n\n{highlights}"
        if highlights
        else ""
    )
    also_section_formatted = (
        f"\n\n<b>Also Worth Knowing:</b>\n{also_section}"
        if also_section
        else ""
    )

    return _build_messages(header, rundown,
                           highlights_section,
                           also_section_formatted)


def _build_messages(header: str, rundown: str,
                     formatted_highlights: str,
                     formatted_also: str) -> list[str]:
    """Build Telegram messages from structured parts, splitting at highlight
    boundaries to never cut a highlight mid-sentence.

    Strategy:
      - 1 msg  : everything fits
      - 2 msgs : rundown in msg1, highlights+also in msg2
      - 3+ msgs: rundown | highlights (overflow to msg3+) | also
    """
    MARGIN = 10   # safety buffer below hard limit

    def make_msg(parts: list[str]) -> str:
        """Join non-empty parts into a single message, strip trailing newlines."""
        return "\n\n".join(p.strip() for p in parts if p.strip())

    def truncate_sentence(text: str, limit: int) -> str:
        """Truncate at last sentence boundary before limit. Falls back to char cut."""
        if len(text) <= limit:
            return text
        # Find last '. ' before limit
        cutoff = text.rfind(". ", 0, limit - 2)
        if cutoff > limit * 0.4:   # only if we found a decent boundary
            return text[:cutoff + 1]
        return text[:limit - 3].rstrip() + "…"

    # ── Try: 1 message ────────────────────────────────────────────────────────
    one = make_msg([header + rundown,
                    formatted_highlights,
                    formatted_also])
    if len(one) <= TELEGRAM_MAX_LENGTH:
        return [one]

    # ── Try: 2 messages (rundown | highlights + also) ───────────────────────
    # Rundown is the hard part — truncate at sentence boundary if needed
    msg1_raw = truncate_sentence(rundown, TELEGRAM_MAX_LENGTH - len(header) - 2)
    msg1 = header + msg1_raw

    # Try putting highlights + also in msg2
    msg2 = make_msg([formatted_highlights, formatted_also])
    if len(msg2) <= TELEGRAM_MAX_LENGTH:
        return [msg1, msg2]

    # msg2 still too big — highlights overflow. Split highlights across msgs.
    # msg2 = formatted_highlights (as many as fit), msg3+ = overflow highlights
    # msg2 may still be > 4096 if a SINGLE highlight is huge; handle below.
    messages = [msg1]

    # Split highlights into individual blocks (each highlight is 3 lines)
    highlight_blocks = []
    block = []
    for line in formatted_highlights.split("\n"):
        if line.strip() == "":
            if block:
                highlight_blocks.append("\n".join(block))
                block = []
        else:
            block.append(line)
    if block:
        highlight_blocks.append("\n".join(block))

    current_msg = ""
    for block in highlight_blocks:
        trial = (current_msg + "\n\n" + block).strip()
        if len(trial) <= TELEGRAM_MAX_LENGTH - MARGIN:
            current_msg = trial
        else:
            if current_msg:
                messages.append(current_msg)
            # If a single block is already > limit, truncate it
            if len(block) > TELEGRAM_MAX_LENGTH - MARGIN:
                current_msg = block[:TELEGRAM_MAX_LENGTH - MARGIN - 3].rstrip() + "…"
            else:
                current_msg = block
    if current_msg.strip():
        messages.append(current_msg)

    # Append also-worth-knowing to the last message if there's room
    if formatted_also:
        last = messages[-1]
        trial = (last + "\n\n" + formatted_also).strip()
        if len(trial) <= TELEGRAM_MAX_LENGTH:
            messages[-1] = trial
        else:
            # Also-worth-knowing is its own message
            messages.append(formatted_also)

    # Final safety: any message still over limit gets hard-truncated at char
    def hard_truncate(text: str) -> str:
        if len(text) <= TELEGRAM_MAX_LENGTH:
            return text
        return text[:TELEGRAM_MAX_LENGTH - 3].rstrip() + "…"

    return [hard_truncate(m) for m in messages]


def send_digest(raw_summary: str) -> bool:
    """Format and send the digest to Telegram. Returns True on success."""
    messages = _format_digest(raw_summary)

    for i, message in enumerate(messages):
        success = _send_message(message)
        if not success:
            logger.error(f"Failed to send message part {i + 1}/{len(messages)}")
            return False

    logger.info(f"Digest sent successfully ({len(messages)} message(s))")
    return True


def _send_message(text: str, retry: bool = True) -> bool:
    """Send a single message to Telegram. Retries once on failure."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=30)

        if response.status_code == 200:
            return True

        if response.status_code == 403:
            logger.error(
                "Telegram 403: Bot was removed from the chat or chat ID is invalid. "
                "Check TELEGRAM_CHAT_ID and ensure the bot is added to the group."
            )
            return False

        logger.warning(
            f"Telegram API error {response.status_code}: {response.text}"
        )

        if retry:
            logger.info("Retrying Telegram send...")
            return _send_message(text, retry=False)

        return False

    except requests.RequestException as e:
        logger.error(f"Telegram request failed: {e}")
        if retry:
            logger.info("Retrying Telegram send...")
            return _send_message(text, retry=False)
        return False
