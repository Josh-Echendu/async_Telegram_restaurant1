from typing import Optional, Dict, Any
import uuid
from WHATSAPP_BOT_API.core.config import *
from WHATSAPP_BOT_API.core.config import _request_with_retry



async def handle_join_session(msg, session_token):
    user_id = msg.from_user.wa_id
    user_session = await get_user_session(user_id)
    restaurant_id = user_session.get("current_rid")

    idempotency_key = str(uuid.uuid4())

    payload = {
        "platform": "whatsapp",
        "user_id": user_id,
        "session_token": session_token,
        "restaurant_id": restaurant_id,
        "idempotency_key": idempotency_key,
    }

    response, success = await _request_with_retry(
        method="POST",
        url="http://web:8000/restaurants/dine-in/request-join/",
        json=payload,
        headers={"X-INTERNAL-API-KEY": INTERNAL_API_KEY},
    )

    # Network/5xx failure — recoverable
    if not success or response is None:
        return {
            "ok": False,
            "recoverable": True,
            "error": "Network error",
        }

    try:
        data = response.json()
    except Exception:
        data = {}

    # Success
    if 200 <= response.status_code < 300:
        return {
            "ok": True,
            "data": data,
        }

    # Conflict — permanent
    if response.status_code == 409:
        return {
            "ok": False,
            "recoverable": False,
            "error": data.get("error", "Conflict"),
        }

    # Bad request — permanent
    if response.status_code == 400:
        return {
            "ok": False,
            "recoverable": False,
            "error": data.get("error", "Bad request"),
        }

    # Other 4xx — permanent
    if 400 <= response.status_code < 500:
        return {
            "ok": False,
            "recoverable": False,
            "error": data.get(
                "error",
                f"API returned {response.status_code}",
            ),
        }

    # Other unexpected status — recoverable
    return {
        "ok": False,
        "recoverable": True,
        "error": f"Unexpected status {response.status_code}",
    }



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
    image = restaurant_data.get("image")  # ✅ Extract Image

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

    registration = await whatsapp_registration(
        whatsapp_id=user_id, 
        first_name=first_name,
        username=username, 
        phone_number=user_phone, 
        restaurant_id=restaurant_id
    )

    if not registration or not registration.get("ok"):
        if registration and not registration.get("recoverable"):
            logger.error("Registration failed permanently: %s", registration.get("error"))
            await msg.reply_text("❌ Network error, please try again.")
            return

        raise Exception(f"Registration temporarily failed: {registration.get('error') if registration else 'Unknown error'}")

    # =========================
    # 🔗 HANDLE JOIN PAYLOAD
    # =========================
    if msg.text and msg.text.startswith("join_"):
        session_token = msg.text[5:]
        join_result = await handle_join_session(msg, session_token)

        if not join_result.get("ok"):
            if join_result.get("recoverable"):
                raise Exception(f"Join failed: {join_result.get('error')}")

            logger.error("Join failed permanently: %s", join_result.get("error"))
            await msg.reply_text(
                "😔 We couldn't connect you to the table.\n\n"
                "The link may have expired, or the table is no longer active.\n\n"
                "👉 Please ask the host to share a fresh link, or scan the QR code again."
            )
            return

        await redis_client.set(
            f"user_session_token:{restaurant_id}:{user_id}",
            session_token,
            ex=86400,
        )
    
    # =========================
    # 🧩 BUSINESS-SPECIFIC BUTTONS
    # =========================
    buttons = None
    if business_type == "restaurant":
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

    # =========================
    # 🎨 BEAUTIFUL WELCOME MESSAGES
    # =========================
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

    message_template = messages["restaurant"] # default
    if business_type == "restaurant":
        message_template = messages["restaurant"]
    elif business_type == "vendor" and vendor_type == "goods":
        message_template = messages["vendor_goods"]
    elif business_type == "vendor" and vendor_type == "cooked_food":
        message_template = messages["vendor_cooked_food"]

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
    # 📸 1. SEND IMAGE WITH CAPTION
    # =========================
    if image:
        try:
            base_url = NGROK_DJANGO.rstrip('/')
            image_path = image.lstrip('/')
            image_url = f"{base_url}/{image_path}"

            import httpx
            logger.info(f"Downloading image: {image_url}")
            
            # 1. Download the image using httpx with the ngrok bypass header
            async with httpx.AsyncClient() as http_client:
                img_response = await http_client.get(
                    image_url, 
                    headers={"ngrok-skip-browser-warning": "true"},
                    timeout=10.0
                )
                img_response.raise_for_status()
                image_bytes = img_response.content

            # 2. Send the bytes using the PyWa client
            await client.send_image(
                to=user_id,
                image=image_bytes,
                caption=welcome_text 
            )
        except Exception as e:
            logger.error(f"Failed to send WhatsApp image: {e}")
            # ✅ Fallback: Send text with buttons if image fails
            await client.send_message(
                to=user_id, 
                text=welcome_text, 
                buttons=buttons
            )
            return
    else:
        # ✅ If no image exists, send the text with buttons
        await client.send_message(
            to=user_id, 
            text=welcome_text, 
            buttons=buttons
        )
        return 

    # =========================
    # 🔘 2. SEND BUTTONS (Only if image was sent successfully)
    # =========================
    # Since the welcome text is already sent, we send a tiny prompt with the buttons
    if image:
        await client.send_message(
            to=user_id,
            text="👇 *Select an option:*",
            buttons=buttons
        )


# ============================================
# 📝 REGISTRATION FUNCTION (Converted from telegram_registration)
# ============================================
async def whatsapp_registration(
    whatsapp_id,
    first_name,
    username,
    phone_number,
    restaurant_id,
):
    """
    Register a user from WhatsApp.

    Returns:
        {"ok": True, "data": {...}}
            -> Success

        {"ok": False, "recoverable": True, "error": "..."}
            -> Retry through ARQ

        {"ok": False, "recoverable": False, "error": "..."}
            -> Permanent failure
    """

    payload = {
        "whatsapp_id": str(whatsapp_id),
        "first_name": str(first_name),
        "username": str(username or ""),
        "phone_number": str(phone_number or ""),
        "restaurant_id": str(restaurant_id),
    }

    url = (
        "http://web:8000/"
        "userauths/register_user/restaurant/whatsapp/"
    )

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    try:
        response, success = await _request_with_retry(
            method="POST",
            url=url,
            json=payload,
            headers=headers,
            timeout=30.0,
        )

        # Network / 5xx failure — recoverable
        if not success or response is None:
            logger.warning(
                "Registration network/5xx failure for whatsapp_id=%s",
                whatsapp_id,
            )

            return {
                "ok": False,
                "recoverable": True,
                "error": "Network error",
            }

        # Parse response body
        try:
            data = response.json()
        except Exception:
            data = {}

        # 2xx — success
        if 200 <= response.status_code < 300:
            logger.info(
                "WhatsApp user registration successful: %s",
                whatsapp_id,
            )

            return {
                "ok": True,
                "data": data,
            }

        # 400 — permanent bad input
        if response.status_code == 400:
            logger.error(
                "Registration 400 for whatsapp_id=%s: %s",
                whatsapp_id,
                data,
            )

            return {
                "ok": False,
                "recoverable": False,
                "error": data.get("error", "Bad request"),
            }

        # Other 4xx — permanent failure
        if 400 <= response.status_code < 500:
            logger.error(
                "Registration %s for whatsapp_id=%s: %s",
                response.status_code,
                whatsapp_id,
                data,
            )

            return {
                "ok": False,
                "recoverable": False,
                "error": data.get(
                    "error",
                    f"API returned {response.status_code}",
                ),
            }

        # Other unexpected statuses — recoverable
        logger.warning(
            "Unexpected registration status %s for whatsapp_id=%s",
            response.status_code,
            whatsapp_id,
        )

        return {
            "ok": False,
            "recoverable": True,
            "error": f"Unexpected status {response.status_code}",
        }

    except Exception as e:
        logger.exception(
            "Registration exception for whatsapp_id=%s",
            whatsapp_id,
        )

        return {
            "ok": False,
            "recoverable": True,
            "error": str(e),
        }
