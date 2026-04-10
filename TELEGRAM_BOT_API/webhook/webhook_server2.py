# Use getattr to prevent the bot from crashing if the attribute is missing
# res = getattr(update, 'restaurant_context', None)

# if not res:
#     return # Or handle the error


# webhook_server.py
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from bot_manager import get_bot
from services.restaurant_cache import get_restaurant
import logging
from datetime import datetime
from core.config import *

logger = logging.getLogger(__name__)

app = FastAPI()

import redis
import json


@app.post("/webhook/{rid}")
async def webhook(rid: str, request: Request):

    # 1. Extract raw JSON from Telegram
    data = await request.json()

    # 🔐 GET RESTAURANT DATA
    # This should return a dict with rid, bot_token, secret, name, etc.
    restaurant = await get_restaurant(rid)

    if not restaurant:
        logger.error(f"Restaurant {rid} not found in database/cache.")
        raise HTTPException(status_code=404, detail="Restaurant not found")

    # 🔐 VALIDATE SECRET HEADER (The Handshake)
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != restaurant["webhook_secret_token"]:
        logger.error(f"Unauthorized access attempt for RID: {rid}")
        raise HTTPException(status_code=403, detail="Invalid secret token")

    # 🚫 CHECK BOT STATUS
    if not restaurant.get("is_bot_active", True):
        logger.warning(f"Bot for {restaurant['name']} is currently disabled.")
        return {"status": "bot disabled"}

    # 🤖 GET DYNAMIC BOT INSTANCE
    # This fetches the PTB Application mapped to this specific token
    bot_app = await get_bot(restaurant['bot_token'])

    # 🔁 CONVERT JSON TO TELEGRAM UPDATE OBJECT
    update = Update.de_json(data, bot_app.bot)

    # 🧠 OPTION 2: PERSISTENCE INJECTION (Save to Redis/Long-term memory)
    user_id = None
    table_number = None

    if update.effective_user:
        user_id = update.effective_user.id
        user_session = await get_user_session(user_id)

        # always set context
        user_session["current_rid"] = rid
        user_session["restaurant_name"] = restaurant["bot_name"]

        # callback handling (PTB way)
        if update.callback_query:
            callback_data = update.callback_query.data

            if callback_data.startswith("table_"):
                table_number = callback_data.replace("table_", "")
                user_session["table_number"] = table_number
                print("Selected table:", table_number)

        await save_user_session(user_id, user_session)     

    # ⚡ PROCESS
    # This triggers your handlers (start, echo, etc.)
    await bot_app.process_update(update)

    return {"ok": True}

# 1. User sends message

# 2. Telegram sends POST:
#    → /webhook/<token>

# 3. FastAPI receives

# 4. Validate:
#    - token exists in DB
#    - secret header matches
#    - bot is active

# 5. Load bot:
#    get_bot(token)

# 6. Convert update:
#    Update.de_json(...)

# 7. Process:
#    app.process_update(update)

# 8. Handler runs:
#    start / echo / button

# 9. Handler calls DRF API if needed

