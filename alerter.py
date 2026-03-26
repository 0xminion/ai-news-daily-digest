#!/usr/bin/env python3
"""Alerter — deliver ad-hoc alerts to Telegram via direct Bot API.

Replaces the broken subprocess approach:
  BEFORE (broken): subprocess.run(["hermes", "chat", ...])
    — spawns a new Hermes process with no access to the active Telegram session

  AFTER (fixed): requests.post to https://api.telegram.org/bot{TOKEN}/sendMessage
    — direct Bot API call, no subprocess, no session dependency
"""
import html
import logging
import os
import textwrap
from datetime import datetime, timezone

import requests

logger = logging.getLogger("ai-digest.alerter")

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
TELEGRAM_MAX_LENGTH = 4096
TELEGRAM_TIMEOUT = 30


def send_alert(
    message: str,
    bot_token: str | None = None,
    chat_id: str | None = None,
    parse_mode: str = "HTML",
    compact: bool = False,
) -> bool:
    """Send a short alert message to Telegram.

    Args:
        message: Text to send. Will be truncated at 4096 chars.
        bot_token: Telegram bot token. Falls back to TELEGRAM_BOT_TOKEN env var.
        chat_id: Target chat ID. Falls back to TELEGRAM_CHAT_ID env var.
        parse_mode: "HTML" (default) or "MarkdownV2". Use "Text" to disable.
        compact: If True, omit the timestamp header.

    Returns:
        True if the message was sent successfully.
    """
    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    target = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    if not token or not target:
        logger.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
        return False

    if not compact:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        header = f"<b>[Alert · {ts}]</b>\n\n"
    else:
        header = ""

    full = header + message
    if len(full) > TELEGRAM_MAX_LENGTH:
        full = full[: TELEGRAM_MAX_LENGTH - 3] + "…"

    payload = {
        "chat_id": target,
        "text": full,
        "parse_mode": parse_mode if parse_mode in ("HTML", "MarkdownV2") else None,
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(
            TELEGRAM_API.format(token=token),
            json=payload,
            timeout=TELEGRAM_TIMEOUT,
        )

        if response.status_code == 200:
            logger.info("Alert sent successfully")
            return True

        # Surface actionable errors without leaking credentials or internals
        if response.status_code == 403:
            logger.error(
                "Telegram 403: bot was removed from chat or chat_id is invalid"
            )
        elif response.status_code == 400:
            logger.error(
                "Telegram 400: malformed message or invalid parse_mode. "
                "Try parse_mode='Text'"
            )
        else:
            logger.warning("Telegram API error %s", response.status_code)
        return False

    except requests.RequestException as e:
        logger.error("Telegram request failed: %s", e)
        return False


def send_file_content(
    filepath: str,
    caption: str = "",
    bot_token: str | None = None,
    chat_id: str | None = None,
    max_chars: int = 4000,
) -> bool:
    """Read a file and send its contents as a Telegram message.

    Large files are truncated to max_chars with a notice.

    Args:
        filepath: Path to the file to send.
        caption: Optional prefix text before the file content.
        bot_token: Telegram bot token. Falls back to TELEGRAM_BOT_TOKEN.
        chat_id: Target chat ID. Falls back to TELEGRAM_CHAT_ID.
        max_chars: Maximum characters to send (default 4000, Telegram limit - header).

    Returns:
        True if the file was sent successfully.
    """
    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    target = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    if not token or not target:
        logger.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
        return False

    try:
        filepath = os.path.realpath(filepath)
        safe_base = os.path.realpath(os.environ.get("ALERTER_ALLOWED_DIR", "/home/linuxuser/projects/test"))
        if not filepath.startswith(safe_base + os.sep):
            logger.error("Blocked path traversal attempt: %s", filepath)
            return False
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        logger.error("Cannot read file %s: %s", filepath, e)
        return False

    if len(content) > max_chars:
        content = content[: max_chars - 3] + "…\n\n[Truncated]"

    if caption:
        message = f"{caption}\n\n{html.escape(content)}"
    else:
        message = html.escape(content)

    return send_alert(message, bot_token=token, chat_id=target)


def send_digest_alert(
    summary: str,
    article_count: int,
    bot_token: str | None = None,
    chat_id: str | None = None,
) -> bool:
    """Send a formatted digest alert.

    Used by cron jobs or external triggers to push a pre-generated digest.
    For the normal daily digest flow, use main.py + telegram_bot.py directly.

    Args:
        summary: Pre-generated digest text.
        article_count: Number of articles in the digest.
        bot_token: Telegram bot token.
        chat_id: Target chat ID.

    Returns:
        True if sent successfully.
    """
    ts = datetime.now(timezone.utc).strftime("%B %d, %Y")
    header = f"<b>AI Daily Digest — {ts}</b>\n"
    header += f"<i>{article_count} articles</i>\n\n"

    full = header + summary
    if len(full) > TELEGRAM_MAX_LENGTH:
        full = full[: TELEGRAM_MAX_LENGTH - 3] + "…"

    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    target = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    if not token or not target:
        logger.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
        return False

    payload = {
        "chat_id": target,
        "text": full,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(
            TELEGRAM_API.format(token=token),
            json=payload,
            timeout=TELEGRAM_TIMEOUT,
        )
        if response.status_code == 200:
            logger.info("Digest alert sent (%d articles)", article_count)
            return True
        logger.warning("Telegram API error %s", response.status_code)
        return False
    except requests.RequestException as e:
        logger.error("Telegram request failed: %s", e)
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python alerter.py <message>")
        print("       python alerter.py --file <path>")
        sys.exit(1)

    if sys.argv[1] == "--file":
        success = send_file_content(sys.argv[2], caption=" ".join(sys.argv[3:]))
    else:
        success = send_alert(" ".join(sys.argv[1:]))

    sys.exit(0 if success else 1)
