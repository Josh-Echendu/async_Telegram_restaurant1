# handlers/start_handler.py - EXACT COPY FROM ORIGINAL FILE
import uuid

from TELEGRAM_BOT_API.core.config import *
from TELEGRAM_BOT_API.utils.cart_utils import *
from TELEGRAM_BOT_API.utils.kitchen_utils import *
from FACEBOOK_BOT_API.core.config import _request_with_retry


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
        url=f"http://web:8000/restaurants/dine-in/request-join/",  # ✅ Full URL
        json=payload, 
        headers={"X-INTERNAL-API-KEY": INTERNAL_API_KEY}
    )
    
    if not success:
        raise Exception(f"Failed to join session: {response}") from None
    
    return response, success


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    restaurant_data = await get_user_session(update.effective_chat.id)
    restaurant_id = restaurant_data.get('current_rid')
    restaurant_name = restaurant_data.get('restaurant_name')
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
            
            # Permanent failure — don't retry, notify user
            logger.error(f"Registration failed permanently: {registration.get('error')}")
            await update.message.reply_text(
                f"❌ Network error, please Try again."
            )
            return
        
        # Recoverable — raise to trigger ARQ retry
        raise Exception("Registration temporarily failed, will retry")


    # Get the payload after "start="
    payload = context.args[0] if context.args else None
    print("start payload: ", payload)
        
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
        
        # Save session token to Redis
        await redis_client.set(
            f"user_session_token:{restaurant_id}:{user_id}",
            session_token,
            ex=86400
        )

    
    # --- BUSINESS-SPECIFIC KEYBOARD ---
    if business_type == "restaurant":
        service_mode = (restaurant_data.get('service_mode') or "").lower()
        
        if service_mode == "delivery":
            keyboard = [
                ["🍽 Order Food", "📦 Track Order"],
                ["📞 Contact Staff"]
            ]
        elif service_mode in ["dine_in", 'both']:
            keyboard = [
                ["🍽 Order Food", "📦 Track Order"],
                ["📞 Contact Staff", "🛍️✅💳 Checkout/Pay"]
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
        },
    }

    # Select the right message template
    if business_type == "restaurant":
        msg = messages["restaurant"]
    elif business_type == "vendor" and vendor_type == "goods":
        msg = messages["vendor_goods"]
    elif business_type == "vendor" and vendor_type == "cooked_food":
        msg = messages["vendor_cooked_food"]
    else:
        msg = messages["restaurant"]  # fallback

    welcome_text = (
        f"<b>{msg['icon']} Welcome to {restaurant_name}, <i>{first_name}</i>!</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 {msg['role']}\n\n"
        "✨ <b>What you can do:</b>\n\n"
        f"{msg['features']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>👇 Choose an option below</i>"
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=welcome_text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        parse_mode="HTML"
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