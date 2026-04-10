#!/bin/sh
# Ensure Redis/other services are reachable first (optional)
sleep 5


# Start the bot
exec uvicorn webhook.webhook_server:app \
    --host 0.0.0.0 \
    --port 8080 \
    --reload \
    --log-level info