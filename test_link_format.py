from ai_news_digest.output.telegram import _format_digest

summary = (
    'Brief Rundown:\nShort summary.\n\n'
    'Trend Watch:\nMain News Trend Watch:\nHeating Up:\n- OpenAI — more launches\n\n'
    'Highlights:\n1. Headline\nDetails here.\nSource: Test Source (https://example.com)\n\n'
    'Also Worth Knowing:\n- Side item | Side Source (https://example.com/also)'
)
msgs = _format_digest(summary)
for m in msgs:
    print(m)
    print('---')
