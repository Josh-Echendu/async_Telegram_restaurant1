# webhook_server.py
from fastapi import FastAPI, Request, HTTPException, Query
from typing import Optional
from datetime import datetime
import hmac
import hashlib

from WHATSAPP_BOT_API.core.config import *
from WHATSAPP_BOT_API.services.restaurant_cache import get_restaurant

app = FastAPI()


# 🔐 SIGNATURE VALIDATION
def verify_signature(app_secret: str, payload: bytes, signature: str) -> bool:
    print("whatsapp signature request: ", signature)
    print("whatsapp app_secret request: ", app_secret)
    print("whatsapp payload request: ", payload)

    if not signature:
        return False

    expected = hmac.new(
        app_secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    print("whatsapp expected digest: ", expected)

    return hmac.compare_digest(f"sha256={expected}", signature)


# 🔑 WEBHOOK VERIFICATION (Meta setup)
@app.get("/whatsapp-webhook")
async def verify_webhook(
    request: Request,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    rid: Optional[str] = None,
):
    print(f"Verification attempt for RID: {rid}")
    print(f"Verification attempt for hub_challenge: {hub_challenge}")
    print(f"Verification attempt for hub_verify_token: {hub_verify_token}")
    print(f"Verification attempt for hub_mode: {hub_mode}")

    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        print("✅ Meta Verification Successful!")
        return int(hub_challenge)

    print("❌ Verification Failed: Token mismatch")
    raise HTTPException(status_code=403, detail="Verification failed")


# 📩 INCOMING EVENTS
@app.post("/whatsapp-webhook")
async def whatsapp_webhook(request: Request):
    print("whatsapp verification request: ", request)

    # Read raw bytes once
    body = await request.body()

    # Signature header from Meta
    signature = request.headers.get("X-Hub-Signature-256")

    # 🔐 1. SECURITY CHECK
    if not verify_signature(APP_SECRET, body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Parse JSON from the raw bytes already read
    import json
    data = json.loads(body)

    # 2. Extract phone_number_id
    try:
        value = data["entry"][0]["changes"][0]["value"]
        phone_id = value["metadata"]["phone_number_id"]
    except (KeyError, IndexError):
        return {"status": "not a message event"}

    # 🧠 3. MULTI-TENANT LOAD
    restaurant = await get_restaurant(phone_id)
    print("restaurant: ", restaurant)

    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    # 🚫 4. STATUS CHECK
    if not restaurant.get("is_wa_active"):
        return {"status": "whatsapp disabled"}

    # ⚙️ 5. ENQUEUE BACKGROUND JOB
    arq = await get_arq_redis()

    job = await arq.enqueue_job(
        "handle_whatsapp_update",
        update_data=data,          # parsed dict for session logic
        raw_payload=body,          # raw bytes for pywa_async.webhook_update_handler()
        signature=signature,       # X-Hub-Signature-256 header
        restaurant=restaurant,
        _queue_name="restaurant_jobs",
    )

    print("arq done.......................")
    print("Enqueued job:", job)

    return {"ok": True}