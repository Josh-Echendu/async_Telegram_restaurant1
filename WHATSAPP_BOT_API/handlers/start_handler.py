from typing import Optional, Dict, Any
from WHATSAPP_BOT_API.core.config import *




# =========================
# 📊 LOGGER
# =========================
async def logger_whatsapp(client: WhatsApp, msg: Message):
    user_name = msg.from_user.name or "Unknown"
    whatsapp_id = msg.from_user.wa_id
    message_text = msg.text or "[Non-text message]"

    logger.info(f"""
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

    user_id = msg.from_user.wa_id

    restaurant_data = await get_user_session(user_id)
    restaurant_id = restaurant_data.get("current_rid")
    restaurant_name = restaurant_data.get("restaurant_name")

    business_type = (restaurant_data.get('business_type') or "").lower()
    vendor_type = (restaurant_data.get('vendor_type') or "").lower()
    service_mode = (restaurant_data.get('service_mode') or "").lower()


    first_name = msg.from_user.name or "Customer"
    user_phone = msg.from_user.wa_id

    logger.info(f"🏪 Restaurant ID: {restaurant_id}")
    logger.info(f"🏪 Restaurant Name: {restaurant_name}")
    logger.info(f"👤 User: {first_name} ({user_phone})")


    # =========================
    # 🧾 USER REGISTRATION
    # =========================
    username = first_name or f"user_{user_id[-4:]}"

    registration = await whatsapp_registration(whatsapp_id=user_id, first_name=first_name,
        username=username, phone_number=user_phone, restaurant_id=restaurant_id)

    if not registration:
        return 

    # --- BUSINESS-SPECIFIC BUTTONS ---

        # =========================
        # 🧩 WhatsApp Interactive Buttons (CORRECT FORMAT)
        # =========================
        
    buttons=None
    if business_type == "restaurant":

        service_mode = (restaurant_data.get("service_mode") or "").lower()

        if service_mode == "delivery":
            buttons = [
                Button(title="🍽 Order Food", callback_data="order_food"),
                Button(title="📦 Track Order", callback_data="track_order"),
                Button(title="📞 Contact Staff", callback_data="contact_staff"),
            ]

        elif service_mode in ["dine_in", "both"]:
            buttons = [
                Button(title="🍽 Order Food", callback_data="order_food"),
                Button(title="📦 Track Order", callback_data="track_order"),
                # Button(title="📞 Contact Staff", callback_data="contact_staff"),
                Button(title="🛍️✅💳 Checkout/Pay", callback_data="checkout"),
            ]

    elif business_type == "vendor":

        if vendor_type == "goods":
            buttons = [
                Button(title="🛍️ Browse Products", callback_data="browse_products"),
                Button(title="📦 Track Order", callback_data="track_order"),
                Button(title="📞 Contact Staff", callback_data="contact_staff"),
            ]

        elif vendor_type == "cooked_food":
            buttons = [
                Button(title="🍽 Order Food", callback_data="order_food"),
                Button(title="📦 Track Order", callback_data="track_order"),
                Button(title="📞 Contact Staff", callback_data="contact_staff"),
            ]

        else:
            buttons = [
                Button(title="🛍️ Browse Products", callback_data="browse_products"),
                Button(title="📦 Track Order", callback_data="track_order"),
                Button(title="📞 Contact Staff", callback_data="contact_staff"),
            ]

    else:
        buttons = [
            Button(title="🍽 Order Food", callback_data="order_food"),
            Button(title="📦 Track Order", callback_data="track_order"),
            Button(title="📞 Contact Staff", callback_data="contact_staff"),
        ]

    # --- BEAUTIFUL WELCOME MESSAGES ---
    messages = {
        "restaurant": {
            "icon": "🍽️",
            "role": "Your personal restaurant assistant",
            "features": "🛍 Browse meals\n🛒 View cart\n📦 Track orders\n⚡ Enjoy fast and easy ordering"
        },
        "vendor_goods": {
            "icon": "🛍️",
            "role": "Your personal store assistant",
            "features": "🛍️ Browse products\n🛒 Add to cart\n📦 Track orders\n💰 Quick and secure checkout"
        },
        "vendor_cooked_food": {
            "icon": "🍲",
            "role": "Your personal food vendor assistant",
            "features": "🍽 Browse meals\n🛒 Place orders\n📦 Track deliveries\n⚡ Fresh and fast service"
        }
    }

    # Select the right message template
    message_template=None

    if business_type == "restaurant":
        message_template = messages["restaurant"]
    elif business_type == "vendor" and vendor_type == "goods":
        message_template = messages["vendor_goods"]
    elif business_type == "vendor" and vendor_type == "cooked_food":
        message_template = messages["vendor_cooked_food"]
    else:
        message_template = messages["restaurant"]

    welcome_text = (
        f"*{message_template['icon']} Welcome to {restaurant_name}, _{first_name}_!* \n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 {message_template['role']}\n\n"
        "✨ *What you can do:*\n\n"
        f"{message_template['features']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "_👇 Choose an option below_"
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
    
    logger.info(f"📝 Registering user: {payload}")
    
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"http://web:8000/userauths/register_user/restaurant/whatsapp/",  # Changed endpoint
                    headers={"Accept": "application/json"},
                    json=payload
                )
                response.raise_for_status()
                logger.info(f"✅ User registration successful: {response.json()}")
                return response.json()
                
        except httpx.HTTPStatusError as e:
            # Try to get error details
            try:
                error_data = e.response.json()
                logger.info(f"❌ User registration error: {error_data}")
            except:
                logger.info(f"❌ HTTP error {e.response.status_code}: {e.response.text}")
                
            logger.warning(f"Attempt {attempt}/{max_retries} failed: {e}")
            
            if attempt == max_retries:
                logger.error(f"All {max_retries} attempts failed")
                return None
                
            await asyncio.sleep(2 ** attempt)  # Exponential backoff: 2, 4, 8 seconds
            
        except httpx.RequestError as e:
            logger.warning(f"🌐 Network error on attempt {attempt}: {e}")
            logger.warning(f"Attempt {attempt} failed: {e}")
            
            if attempt == max_retries:
                logger.error(f"All {max_retries} attempts failed")
                return None
                
            await asyncio.sleep(2 ** attempt)
    
    return None