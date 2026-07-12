# webhook_server.py

from fastapi import FastAPI, Request, HTTPException, Query
from typing import Optional
from datetime import datetime
import json
import hmac
import hashlib

from FACEBOOK_BOT_API.core.config import *
from FACEBOOK_BOT_API.services.restaurant_cache import get_restaurant

app = FastAPI()


# 🔐 SIGNATURE VALIDATION
def verify_signature(app_secret: str, payload: bytes, signature: str) -> bool:

    if not signature:
        return False

    expected = hmac.new(
        app_secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)


# 🔑 META WEBHOOK VERIFICATION
@app.get("/facebook-webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):

    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        logger.info("✅ Facebook Webhook Verified")
        return int(hub_challenge)

    logger.error("❌ Facebook Verification Failed")
    raise HTTPException(status_code=403, detail="Verification failed")


# 📩 FACEBOOK WEBHOOK
@app.post("/facebook-webhook")
async def facebook_webhook(request: Request):

    try:
        logger.info(f"Received Facebook webhook at {datetime.now()}")

        # Read raw body
        body = await request.body()

        # Signature header
        signature = request.headers.get("X-Hub-Signature-256")

        # Verify request really came from Meta
        if not verify_signature(APP_SECRET, body, signature):
            raise HTTPException(status_code=403, detail="Invalid signature")

        # Parse JSON
        data = json.loads(body)
        print("facebook data: ", data)

        # Ignore anything that's not a page webhook
        if data.get("object") != "page":
            return {"status": "ignored"}

        try:
            print("facebook_webhook data: ", data)
            entry = data["entry"][0]

            # Restaurant identifier
            page_id = entry["id"]

            # Ignore non-message events
            if "messaging" not in entry:
                return {"status": "ignored"}

        except (KeyError, IndexError):
            return {"status": "ignored"}

        # Load restaurant
        restaurant = await get_restaurant(page_id)

        if not restaurant:
            raise HTTPException(status_code=404, detail="Restaurant not found")

        # Bot enabled?
        if not restaurant.get("is_fb_active"):
            return {"status": "facebook disabled"}

        # Queue worker
        arq = await get_arq_redis()
        
        entry = data["entry"][0]
        event = entry["messaging"][0]

        await arq.enqueue_job(
            "handle_facebook_update",
            event=event,
            restaurant=restaurant,
            _queue_name="restaurant_jobs"
        )

        logger.info("Facebook job queued successfully.")

        return {"ok": True}

    except Exception as e:
        logger.exception(e)
        return {"ok": False, "error": str(e)}




# {
#   "object": "page",
#   "entry": [
#     {
#       "id": "987654321098765",
#       "messaging": [
#         {
#           "sender": {
#             "id": "1234567890123456"
#           },
#           "recipient": {
#             "id": "987654321098765"
#           }
#         }
#       ]
#     }
#   ]
# }