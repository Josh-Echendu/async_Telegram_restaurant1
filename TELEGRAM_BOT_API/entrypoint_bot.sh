#!/bin/sh
sleep 5

# ✅ Navigate into the bot directory
cd /app/TELEGRAM_BOT_API

# ✅ Run uvicorn and watch the current directory (.)
exec uvicorn webhook.webhook_server:app \
    --host 0.0.0.0 \
    --port 8080 \
    --reload \
    --reload-dir /app/TELEGRAM_BOT_API \
    --log-level info