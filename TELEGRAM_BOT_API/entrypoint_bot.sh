#!/bin/sh
# Ensure Redis/other services are reachable first (optional)
sleep 5

echo running migrations
python manage.py makemigrations --noinput
python manage.py migrate --noinput

# Start the bot
uvicorn webhook_server:app --reload --host 0.0.0.0 --port 8080