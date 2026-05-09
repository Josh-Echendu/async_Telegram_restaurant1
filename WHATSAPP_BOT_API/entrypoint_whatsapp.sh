#!/bin/sh
# Ensure Redis/other services are reachable first (optional)
sleep 5


# Start the bot
exec uvicorn webhook.webhook_server:app \
    --host 0.0.0.0 \
    --port 8080 \
    --reload \
    --log-level info


    # The ONLY fields you actually need:Once you switch to "WhatsApp Business Account," the list will change. You only need to care about these:FieldWhat it doesWhy you need itmessagesTriggers when a customer sends you a text, image, or location.CRITICAL. This is the main one for your bot.message_deliveriesTells you when your bot's message reached the user's phone.Good for tracking if your bot is working.message_echoesTriggers when you (or another agent) sends a message from the phone.Useful if you want the bot to "see" what a human agent is typing.