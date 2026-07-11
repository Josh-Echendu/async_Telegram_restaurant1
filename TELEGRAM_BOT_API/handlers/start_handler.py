# handlers/start_handler.py - EXACT COPY FROM ORIGINAL FILE
from TELEGRAM_BOT_API.core.config import *
from TELEGRAM_BOT_API.utils.cart_utils import *
from TELEGRAM_BOT_API.utils.kitchen_utils import *
from core.config import _request_with_retry


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

    if not registration:
        return 
    
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
    

async def telegram_registration(telegram_id, first_name, username, restaurant_id, max_retries=5):
    """
    Register a user from Telegram in the system.
    
    Args:
        telegram_id: User's Telegram ID
        first_name: User's first name
        username: User's username
        restaurant_id: Restaurant ID
        max_retries: Maximum number of retry attempts (used by _request_with_retry)
    
    Returns:
        dict: Response data from the API, or None if all attempts fail
    """
    
    # Prepare the payload
    payload = {
        "telegram_id": int(telegram_id),
        "first_name": str(first_name),
        "username": str(username),
        "restaurant_id": str(restaurant_id)
    }
    
    # Override the default retry settings for this specific call
    # You can either modify the global config or pass custom settings
    # Here we'll use the global config but you can also set it per call
    
    url = "http://web:8000/userauths/register_user/restaurant/telegram/"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        # Use _request_with_retry with POST method
        response, success = await _request_with_retry(
            method="POST",
            url=url,
            json=payload,
            headers=headers,
            timeout=30.0  # You can pass additional kwargs
        )
        
        if not success:
            return None
        
        # _request_with_retry already raises_for_status, so we can parse JSON
        response_data = response.json()
        logger.info("User registration successful: %s", response_data)
        return response_data
        
    except Exception as e:
        logger.exception("Failed to register user after all retry attempts: %s", e)
        return None