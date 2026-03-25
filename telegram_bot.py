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
    full_message = f"{rundown_section}{highlights_section}{also_section_formatted}"

    # Split if too long — try to fit in as few messages as possible
    if len(full_message) <= TELEGRAM_MAX_LENGTH:
        return [full_message]

    # Try 2 messages: rundown | highlights + also
    msg1 = rundown_section
    if len(msg1) > TELEGRAM_MAX_LENGTH:
        sentences = rundown.split(". ")
        truncated = ". ".join(sentences[:3]) + "."
        msg1 = f"{header}{truncated}"

    msg2_content = f"<b>Must-Know Highlights:</b>\n\n{highlights}{also_section_formatted}"
    if len(msg2_content) <= TELEGRAM_MAX_LENGTH:
        return [msg1, msg2_content]

    # 3 messages: rundown | highlights | also worth knowing
    msg2 = f"<b>Must-Know Highlights:</b>\n\n{highlights}"
    if len(msg2) > TELEGRAM_MAX_LENGTH:
        msg2 = msg2[:TELEGRAM_MAX_LENGTH - 3] + "..."

    messages = [msg1, msg2]
    if also_section:
        msg3 = f"<b>Also Worth Knowing:</b>\n{also_section}"
        if len(msg3) > TELEGRAM_MAX_LENGTH:
            msg3 = msg3[:TELEGRAM_MAX_LENGTH - 3] + "..."
        messages.append(msg3)

    return messages


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
