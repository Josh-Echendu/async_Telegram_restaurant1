import httpx
import asyncio
import logging
from typing import Optional, Dict, Any

from pywa.types import Message
from pywa import WhatsApp
from pywa.types import Message, Button
from WHATSAPP_BOT_API.core.config import get_user_session


# =========================
# 📊 LOGGER
# =========================
async def logger_whatsapp(client: WhatsApp, msg: Message):
    user_name = msg.from_user.name or "Unknown"
    whatsapp_id = msg.from_user.wa_id
    message_text = msg.text or "[Non-text message]"

    print(f"""
📱 WhatsApp Interaction Log
━━━━━━━━━━━━━━━━━━━━━━━
User: {user_name}
WhatsApp ID: {whatsapp_id}
Message: {message_text}
Timestamp: {msg.timestamp}
━━━━━━━━━━━━━━━━━━━━━━━
""")


# =========================
# 🚀 START HANDLER
# =========================
async def start_handler(client: WhatsApp, msg: Message):
    await logger_whatsapp(client, msg)

    user_id = msg.from_user.wa_id

    restaurant_data = await get_user_session(user_id)
    restaurant_id = restaurant_data.get("current_rid")
    restaurant_name = restaurant_data.get("restaurant_name")

    first_name = msg.from_user.name or "Customer"
    user_phone = msg.from_user.wa_id

    print(f"🏪 Restaurant ID: {restaurant_id}")
    print(f"🏪 Restaurant Name: {restaurant_name}")
    print(f"👤 User: {first_name} ({user_phone})")

    # =========================
    # 🧩 WhatsApp Interactive Buttons (CORRECT FORMAT)
    # =========================
    # ✅ SIMPLE TEXT BUTTONS (THIS WORKS WITH PYWA)
    buttons = [
        Button(title="🍽 Order Food", callback_data="order_food"),
        Button(title="📦 Track Order", callback_data="track_order"),
        Button(title="🛍️ Checkout/Pay", callback_data="checkout"),
    ]


    # =========================
    # 💬 Welcome Message
    # =========================
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

    # =========================
    # 📤 SEND MESSAGE + BUTTONS
    # =========================
    # ✅ SEND MESSAGE WITH BUTTONS (NO RAW GRAPH PAYLOADS)
    await client.send_message(
        to=user_id,
        text=welcome_text,
        buttons=buttons
    )

    # =========================
    # 🧾 USER REGISTRATION
    # =========================
    username = first_name or f"user_{user_id[-4:]}"

    await whatsapp_registration(
        whatsapp_id=user_id,
        first_name=first_name,
        username=username,
        phone_number=user_phone,
        restaurant_id=restaurant_id
    )



# ============================================
# 📝 REGISTRATION FUNCTION (Converted from telegram_registration)
# ============================================
async def whatsapp_registration(
    whatsapp_id: str,      # Changed from telegram_id
    first_name: str,
    username: str,
    phone_number: str,     # Added this field
    restaurant_id: str,
    max_retries: int = 5
):
    """
    Converts your telegram_registration function
    Same logic, just adapted for WhatsApp user data
    """
    
    payload = {
        "whatsapp_id": str(whatsapp_id),      # Changed field name
        "first_name": str(first_name),
        "username": str(username),
        "phone_number": str(phone_number),    # Added this field
        "restaurant_id": str(restaurant_id)
    }
    
    print(f"📝 Registering user: {payload}")
    
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"http://web:8000/userauths/register_user/restaurant/whatsapp/",  # Changed endpoint
                    headers={"Accept": "application/json"},
                    json=payload
                )
                response.raise_for_status()
                print("✅ User registration successful:", response.json())
                return response.json()
                
        except httpx.HTTPStatusError as e:
            # Try to get error details
            try:
                error_data = e.response.json()
                print(f"❌ User registration error: {error_data}")
            except:
                print(f"❌ HTTP error {e.response.status_code}: {e.response.text}")
                
            logging.warning(f"Attempt {attempt}/{max_retries} failed: {e}")
            
            if attempt == max_retries:
                logging.error(f"All {max_retries} attempts failed")
                return None
                
            await asyncio.sleep(2 ** attempt)  # Exponential backoff: 2, 4, 8 seconds
            
        except httpx.RequestError as e:
            print(f"🌐 Network error on attempt {attempt}: {e}")
            logging.warning(f"Attempt {attempt} failed: {e}")
            
            if attempt == max_retries:
                logging.error(f"All {max_retries} attempts failed")
                return None
                
            await asyncio.sleep(2 ** attempt)
    
    return None