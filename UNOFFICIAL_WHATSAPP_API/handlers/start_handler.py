import httpx
import asyncio
import logging


# =========================
# 📊 LOGGER
# =========================
def logger_whatsapp(wa_id, text, push_name):
    user_name = push_name or "Unknown"
    print(f"""
📱 WhatsApp Interaction Log
━━━━━━━━━━━━━━━━━━━━━━━
User: {user_name}
WhatsApp ID: {wa_id}
Message: {text}
━━━━━━━━━━━━━━━━━━━━━━━
""")


# =========================
# 🚀 START HANDLER
# =========================
async def start_handler(wa_id, text, push_name, restaurant):
    """Returns welcome message dict with buttons."""

    logger_whatsapp(wa_id, text, push_name)

    restaurant_id = restaurant.get("rid", "unknown")
    restaurant_name = restaurant.get("name", "Restaurant")
    first_name = push_name or "Customer"
    user_phone = wa_id

    print(f"🏪 Restaurant ID: {restaurant_id}")
    print(f"🏪 Restaurant Name: {restaurant_name}")
    print(f"👤 User: {first_name} ({user_phone})")

    # Register user
    username = first_name or f"user_{wa_id[-4:]}"

    await whatsapp_registration(
        whatsapp_id=wa_id,
        first_name=first_name,
        username=username,
        phone_number=user_phone,
        restaurant_id=restaurant_id,
    )

    welcome_text = (
        f"👋 *Welcome to {restaurant_name}, {first_name}!*\n\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🍽 I'm your personal restaurant assistant\n\n"
        f"What you can do:\n\n"
        f"🛍 Browse meals\n"
        f"🛒 View cart\n"
        f"📦 Track orders\n"
        f"⚡ Fast ordering experience\n\n"
        f"━━━━━━━━━━━━━━"
    )

    return {
        "text": welcome_text,
        "buttons": [
            {"id": "order_food", "text": "🍽 Order Food"},
            {"id": "track_order", "text": "📦 Track Order"},
            {"id": "checkout", "text": "🛍️ Checkout/Pay"},
        ],
    }


# ============================================
# 📝 REGISTRATION FUNCTION
# ============================================
async def whatsapp_registration(
    whatsapp_id,
    first_name,
    username,
    phone_number,
    restaurant_id,
    max_retries=5,
):
    """Registers a WhatsApp user via Django endpoint."""

    payload = {
        "first_name": str(first_name),
        "username": str(username),
        "phone_number": str(phone_number),
        "restaurant_id": str(restaurant_id),
        'platform': 'whatsapp2'
    }

    print(f"📝 Registering user: {payload}")

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "http://web:8000/userauths/register_user/restaurant/whatsapp/",
                    headers={"Accept": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                print("✅ User registration successful:", response.json())
                return response.json()

        except httpx.HTTPStatusError as e:
            try:
                error_data = e.response.json()
                print(f"❌ User registration error: {error_data}")
            except Exception:
                print(f"❌ HTTP error {e.response.status_code}: {e.response.text}")

            logging.warning(f"Attempt {attempt}/{max_retries} failed: {e}")

            if attempt == max_retries:
                logging.error(f"All {max_retries} attempts failed")
                return None

            await asyncio.sleep(2 ** attempt)

        except httpx.RequestError as e:
            print(f"🌐 Network error on attempt {attempt}: {e}")
            logging.warning(f"Attempt {attempt} failed: {e}")

            if attempt == max_retries:
                logging.error(f"All {max_retries} attempts failed")
                return None

            await asyncio.sleep(2 ** attempt)

    return None