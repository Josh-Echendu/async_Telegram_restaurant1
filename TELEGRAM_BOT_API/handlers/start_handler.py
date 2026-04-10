# handlers/start_handler.py - EXACT COPY FROM ORIGINAL FILE
from core.config import *
from utils.cart_utils import *
from utils.kitchen_utils import *
import json


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await logger(update, context)

    restaurant_data = await get_restaurant_data(update)
    restaurant_id = restaurant_data.get('current_rid')
    restaurant_name = restaurant_data.get('restaurant_name')
    print("resturant ID: ", restaurant_id)
    
    web_app_url = f"{NGROK_DJANGO}/userauths/admin_login/restaurant/{restaurant_id}/"

    ADMIN_WEB_APP_URL = web_app_url

    # ID of the user you want to make admin
    ADMIN_USER_ID = ADMIN_ID

    # chat_id = update.effective_chat.id → get the current chat ID.
    chat_id = update.effective_chat.id

    # user_id = update.effective_user.id → get the ID of the person sending the command.
    user_id = update.effective_user.id

    first_name = update.effective_chat.first_name

    # Detect admin: "If user_id equals ADMIN_USER_ID, then user_is_admin becomes True, otherwise False."
    user_is_admin = user_id == ADMIN_USER_ID

    # ✅ Set WebApp button in input bar (ONLY for admin)
    if user_is_admin:
        await context.bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=MenuButtonWebApp(
                text="🔐 Admin",
                web_app=WebAppInfo(url=ADMIN_WEB_APP_URL)
            )
        )

    # Normal welcome UI
    keyboard = [
        ["🍽 Order Food", "📦 Track Order"],
        ["📞 Contact Staff", "🛍️✅💳 Checkout/Pay"]
    ]

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"<b>👋 Welcome to {restaurant_name}, <i>{first_name}</i>!</b>\n\n"
            "━━━━━━━━━━━━━━\n\n"    
            "🍽 I'm your personal restaurant assistant\n\n"
            "What you can do:\n\n"
            "🛍 Browse meals\n"
            "🛒 View cart\n"
            "📦 Track orders\n"
            "⚡ Enjoy fast and easy ordering\n\n"
            "━━━━━━━━━━━━━━\n"
            "<i>👇 Choose an option below</i>"
        ),
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        parse_mode="HTML"
    )
    
    user = update.effective_user
    first_name = user.first_name
    username = user.username

    await telegram_registration(telegram_id=user_id, first_name=first_name, username=username, restaurant_id=restaurant_id)

    
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
                    f"http://web:8000/userauths/register_user/restaurant/",
                    headers={"Accept": "application/json"},  # ask for JSON explicitly
                    json=payload
                )
                response.raise_for_status()
                print("user data:", response.json())
                return response.json()

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            data = e.response.json()
            print("user data error: ", data)
            logging.warning(f"Attempt {attempt} failed to submit user data: {e}")
            
            if attempt == max_retries:
                logging.error(f"All {max_retries} attempts failed to submit user data: {e}")
                return None
            
            # optional: wait before retrying
            await asyncio.sleep(1)


async def after_payment(chat_id, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["🍽 Order Food", "📦 Track Order"],
        ["📞 Contact Staff", "ℹ️ Help"]
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text="What would you like to do next?",
        reply_markup=reply_markup
    )