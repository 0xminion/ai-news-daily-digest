import sys, os, json, requests
sys.path.insert(0, '/home/linuxuser/workspaces/delta/ai-news-daily-digest')

from ai_news_digest.output.telegram import _format_digest

with open('/home/linuxuser/workspaces/delta/ai-news-daily-digest/data/daily_reports/2026-04-10/digest.txt') as f:
    raw = f.read()

messages = _format_digest(raw)

bot_token = os.environ['TELEGRAM_BOT_TOKEN']
chat_id = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('TELEGRAM_CHAT_ID', '')

for i, msg in enumerate(messages):
    resp = requests.post(
        f'https://api.telegram.org/bot{bot_token}/sendMessage',
        json={'chat_id': chat_id, 'text': msg, 'parse_mode': 'HTML', 'disable_web_page_preview': True},
        timeout=30,
    )
    print(f'Chunk {i+1}: {"OK" if resp.status_code == 200 else f"FAIL {resp.status_code} {resp.text[:200]}"}')
