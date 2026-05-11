# webhook_server.py
from fastapi import FastAPI, Request, HTTPException
from TELEGRAM_BOT_API.services.restaurant_cache import get_restaurant
import logging
from datetime import datetime
from TELEGRAM_BOT_API.core.config import *

logger = logging.getLogger(__name__)

app = FastAPI()


@app.post("/telegram-webhook/{rid}")
async def webhook(rid: str, request: Request):

    print(f"Received webhook for RID from restaurant group : {rid} at {datetime.now()}")

    # 1. Extract raw JSON from Telegram
    data = await request.json()

    # 🔐 GET RESTAURANT DATA
    # This should return a dict with rid, bot_token, secret, name, etc.
    restaurant = await get_restaurant(rid)

    if not restaurant:
        logger.error(f"Restaurant {rid} not found in database/cache.")
        raise HTTPException(status_code=404, detail="Restaurant not found")

    print("...............restaurant_josh: ", restaurant)

    # 🔐 VALIDATE SECRET HEADER (The Handshake)
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != restaurant["webhook_secret_token"]:
        logger.error(f"Unauthorized access attempt for RID: {rid}")
        raise HTTPException(status_code=403, detail="Invalid secret token")

    # 🚫 CHECK BOT STATUS
    if not restaurant.get("is_bot_active", True):
        logger.warning(f"Bot for {restaurant['name']} is currently disabled.")
        return {"status": "bot disabled"}
    
    
    arq = await get_arq_redis()
    await arq.enqueue_job(
        'handle_telegram_update',
        update_data=data,
        restaurant=restaurant,
        _queue_name="restaurant_jobs"   # 🔥 THIS FIXES EVERYTHING

    ) 
    return {"ok": True}