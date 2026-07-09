# handlers/start_handler.py - EXACT COPY FROM ORIGINAL FILE
from TELEGRAM_BOT_API.core.config import *
from TELEGRAM_BOT_API.utils.cart_utils import *
from TELEGRAM_BOT_API.utils.kitchen_utils import *


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
    await telegram_registration(telegram_id=user_id, first_name=first_name, username=username, restaurant_id=restaurant_id)

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
        "hotel": {
            "icon": "🏨",
            # "role": "Your personal hotel concierge",
            "role": "Your personal restaurant assistant",
            "features": "🍽 Order room service\n📦 Track orders\n🛎️ Request assistance\n🛒 View your bill"
        }
    }

    # Select the right message template
    if business_type == "restaurant":
        msg = messages["restaurant"]
    elif business_type == "vendor" and vendor_type == "goods":
        msg = messages["vendor_goods"]
    elif business_type == "vendor" and vendor_type == "cooked_food":
        msg = messages["vendor_cooked_food"]
    elif business_type == "hotel":
        msg = messages["hotel"]
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
    
async def telegram_registration(telegram_id, first_name, username, restaurant_id, max_retries=5):
    payload = {
        "telegram_id": int(telegram_id),
        "first_name": str(first_name),
        "username": str(username),
        "restaurant_id": str(restaurant_id)
    }

    for attempt in range(1, int(max_retries + 1)):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"http://web:8000/userauths/register_user/restaurant/telegram/",
                    headers={"Accept": "application/json"},  # ask for JSON explicitly
                    json=payload
                )
                response.raise_for_status()
                logger.info("user data: %s", response.json())
                return response.json()

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            data = e.response.json()
            logger.exception(f"Attempt {attempt} failed to submit user data: {e}")
            
            if attempt == max_retries:
                logger.error(f"All {max_retries} attempts failed to submit user data: {e}")
                return None
            
            # optional: wait before retrying
            await asyncio.sleep(1)