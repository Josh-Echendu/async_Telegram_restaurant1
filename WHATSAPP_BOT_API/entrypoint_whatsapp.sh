#!/bin/sh
# Ensure Redis/other services are reachable first
sleep 5

# ✅ Navigate into the WhatsApp folder
cd /app/WHATSAPP_BOT_API

# ✅ Run uvicorn and watch the current directory
exec uvicorn webhook.webhook_server:app \
    --host 0.0.0.0 \
    --port 8080 \
    --reload \
    --reload-dir /app/WHATSAPP_BOT_API \
    --log-level info