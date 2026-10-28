# handlers/start_handler.py - EXACT COPY FROM ORIGINAL FILE
import uuid

from TELEGRAM_BOT_API.core.config import *
from TELEGRAM_BOT_API.utils.cart_utils import *
from TELEGRAM_BOT_API.utils.kitchen_utils import *
from TELEGRAM_BOT_API.core.config import _request_with_retry



tg_user_data = {}



async def handle_join_session(update, context, session_token):
    user_session = await get_user_session(update.effective_chat.id)
    restaurant_id = user_session.get('current_rid')
    idempotency_key = str(uuid.uuid4())

    payload = {
        "platform": "telegram",
        "user_id": update.effective_user.id,
        "session_token": session_token,
        "restaurant_id": restaurant_id,
        "idempotency_key": idempotency_key
    }

    response, success = await _request_with_retry(
        method="POST",
        url="http://web:8000/restaurants/dine-in/request-join/",
        json=payload,
        headers={"X-INTERNAL-API-KEY": INTERNAL_API_KEY}
    )

    # Network/5xx failure — recoverable
    if not success or response is None:
        return {"ok": False, "recoverable": True, "error": "Network error"}

    try:
        data = response.json()
    except Exception:
        data = {}

    # Success
    if 200 <= response.status_code < 300:
        return {"ok": True, "data": data}

    # 409 conflict (already requested/declined) — recoverable? Usually NOT
    if response.status_code == 409:
        return {"ok": False, "recoverable": False, "error": data.get("error", "Conflict")}

    # 400 bad request — permanent
    if response.status_code == 400:
        return {"ok": False, "recoverable": False, "error": data.get("error", "Bad request")}

    # Other 4xx — permanent
    if 400 <= response.status_code < 500:
        return {"ok": False, "recoverable": False, "error": data.get("error", f"API returned {response.status_code}")}

    # Fallback
    return {"ok": False, "recoverable": True, "error": f"Unexpected status {response.status_code}"}



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    restaurant_data = await get_user_session(update.effective_chat.id)
    restaurant_id = restaurant_data.get('current_rid')
    restaurant_name = restaurant_data.get('restaurant_name')
    image = restaurant_data.get('image') # Ensure your session has the image URL
    print(f"Restaurant Data image: {image}")  # Debugging line
    business_type = (restaurant_data.get('business_type') or "").lower()
    vendor_type = (restaurant_data.get('vendor_type') or "").lower()
    service_mode = (restaurant_data.get('service_mode') or "").lower()
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    first_name = update.effective_chat.first_name
    username = update.effective_user.username
    
    # --- REGISTER USER ---
    registration = await telegram_registration(telegram_id=user_id, first_name=first_name, username=username, restaurant_id=restaurant_id)
    
    if not registration or not registration.get("ok"):
        if registration and not registration.get("recoverable"):
            logger.error(f"Registration failed permanently: {registration.get('error')}")
            await update.message.reply_text(
                f"❌ Network error, please Try again."
            )
            return
        raise Exception("Registration temporarily failed, will retry")

    # Get the payload after "start="
    payload = context.args[0] if context.args else None
        
    if payload and payload.startswith("join_"):
        session_token = payload.replace("join_", "")
        join_result = await handle_join_session(update, context, session_token)
        
        if not join_result.get("ok"):
            if join_result.get("recoverable"):
                raise Exception(f"Join failed: {join_result.get('error')}")
            else:
                logger.error(f"Join failed permanently: {join_result.get('error')}")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "😔 <b>We couldn't connect you to the table.</b>\n\n"
                        "The link may have expired, or the table is no longer active.\n\n"
                        "👉 Please ask the host to share a fresh link, or scan the QR code again."
                    ),
                    parse_mode='HTML'
                )
                return
        
        await redis_client.set(
            f"user_session_token:{restaurant_id}:{user_id}",
            session_token,
            ex=86400
        )

    # --- BUSINESS-SPECIFIC KEYBOARD ---
    if business_type == "restaurant":
        if service_mode == "delivery":
            keyboard = [
                ["🍽 Order Food", "📦 Track Order"],
                ["📞 Contact Staff"]
            ]
        elif service_mode in ["dine_in", 'both']:
            keyboard = [
                ["🍽 Order Food", "📦 Track Order"],
                ["📞 Contact Staff", "🛍️ Checkout/Pay"]
            ]
        else:
            keyboard = [
                ["🍽 Order Food", "📦 Track Order"],
                ["📞 Contact Staff"]
            ]

    elif business_type == "vendor":
        if vendor_type == "goods":
            keyboard = [
                ["🛍️ Browse Products", "📦 Track Order"],
                ["📞 Contact Staff"]
            ]
        elif vendor_type == "cooked_food":
            keyboard = [
                ["🍽 Order Food", "📦 Track Order"],
                ["📞 Contact Staff"]
            ]
        else:
            keyboard = [
                ["🛍️ Browse Products", "📦 Track Order"],
                ["📞 Contact Staff"]
            ]
    else:
        keyboard = [
            ["🍽 Order Food", "📦 Track Order"],
            ["📞 Contact Staff"]
        ]

    # --- BEAUTIFUL WELCOME MESSAGES ---
    messages = {
        "restaurant": {
            "icon": "🍽️",
            "role": "Your personal dining assistant",
            "features": "🛍 Browse delicious meals\n🛒 View your cart\n📦 Track your orders\n⚡ Fast & easy ordering"
        },
        "vendor_goods": {
            "icon": "🛍️",
            "role": "Your personal shopping assistant",
            "features": "🛍️ Browse products\n🛒 Add to cart\n📦 Track orders\n💰 Quick checkout"
        },
        "vendor_cooked_food": {
            "icon": "🍲",
            "role": "Your personal food vendor",
            "features": "🍽 Browse fresh meals\n🛒 Place orders\n📦 Track deliveries\n⚡ Fresh & fast"
        },
    }

    if business_type == "restaurant":
        msg = messages["restaurant"]
    elif business_type == "vendor" and vendor_type == "goods":
        msg = messages["vendor_goods"]
    elif business_type == "vendor" and vendor_type == "cooked_food":
        msg = messages["vendor_cooked_food"]
    else:
        msg = messages["restaurant"]

    # ✅ BEAUTIFUL CAPTION DESIGN
    welcome_text = (
        f"👋 <b>Hey {first_name}!</b>\n\n"
        f"Welcome to <b>{restaurant_name}</b> {msg['icon']}\n"
        f"<i>{msg['role']}</i>\n\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"✨ <b>What you can do:</b>\n"
        f"{msg['features']}\n"
        "➖➖➖➖➖➖➖➖➖➖\n\n"
        "👇 <b>Choose an option below to get started:</b>"
    )

    # ✅ FALLBACK IMAGE (If restaurant has no image)
    default_image = "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?q=80&w=1000&auto=format&fit=crop"

    if image:
        
        # ✅ Strip the trailing slash from NGROK and the leading slash from image
        base_url = NGROK_DJANGO.rstrip('/')
        image_path = image.lstrip('/')
        image_url = f"{base_url}/{image_path}"

    else:
        image_url = default_image

    # ✅ SEND PHOTO WITH CAPTION
    try:

        import httpx
        logger.info(f"Downloading image: {image_url}")
        
        # 1. Download the image using httpx with the ngrok bypass header
        async with httpx.AsyncClient() as client:
            img_response = await client.get(
                image_url, 
                headers={"ngrok-skip-browser-warning": "true"},
                timeout=10.0
            )
            img_response.raise_for_status()
            image_bytes = img_response.content

        logger.info(f"Image downloaded successfully. Size: {len(image_bytes)} bytes")

        await context.bot.send_photo(
            chat_id=chat_id,
            photo=image_bytes,
            caption=welcome_text,
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
    except Exception as e:
        logger.error(f"Failed to send photo, falling back to text: {e}")
        # Fallback to text message if image URL fails
        await context.bot.send_message(
            chat_id=chat_id,
            text=welcome_text,
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )



async def telegram_registration(telegram_id, first_name, username, restaurant_id):
    """
    Register a user from Telegram.
    Returns:
        {"ok": True, "data": {...}}                       → success
        {"ok": False, "recoverable": True, "error": ...}  → retry
        {"ok": False, "recoverable": False, "error": ...} → fail immediately
    """
    payload = {
        "telegram_id": int(telegram_id),
        "first_name": str(first_name),
        "username": str(username),
        "restaurant_id": str(restaurant_id)
    }
    
    url = "http://web:8000/userauths/register_user/restaurant/telegram/"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        response, success = await _request_with_retry(
            method="POST",
            url=url,
            json=payload,
            headers=headers,
            timeout=30.0
        )
        
        # Network / 5xx failure — retry is reasonable
        if not success or response is None:
            logger.warning("Registration network/5xx failure for telegram_id=%s", telegram_id)
            return {"ok": False, "recoverable": True, "error": "Network error"}
        
        # Parse response body
        try:
            data = response.json()
        except Exception:
            data = {}
        
        # 400 = bad input — retry is pointless
        if response.status_code == 400:
            logger.error(
                "Registration 400 (bad data) for telegram_id=%s: %s",
                telegram_id, data
            )
            return {"ok": False, "recoverable": False, "error": data.get("error", "Bad request")}
        
        # 2xx = success
        if 200 <= response.status_code < 300:
            logger.info("User registration successful: %s", data)
            return {"ok": True, "data": data}
        
        # Other 4xx — treat as permanent
        logger.error(
            "Registration %d for telegram_id=%s: %s",
            response.status_code, telegram_id, data
        )
        return {
            "ok": False,
            "recoverable": False,
            "error": data.get("error", f"API returned {response.status_code}")
        }
    
    except Exception as e:
        logger.exception("Registration exception for telegram_id=%s", telegram_id)
        return {"ok": False, "recoverable": True, "error": str(e)}