# handlers/order_handler.py - EXACT COPY FROM ORIGINAL FILE
from TELEGRAM_BOT_API.core.config import *
from TELEGRAM_BOT_API.utils.cart_utils import *
from TELEGRAM_BOT_API.utils.image_utils import *
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


EMOJI_NUMBERS = {
    1: "1️⃣", 2: "2️⃣", 3: "3️⃣",
    4: "4️⃣", 5: "5️⃣", 6: "6️⃣",
    7: "7️⃣", 8: "8️⃣", 9: "9️⃣",
    10: "🔟",
    11: "1️⃣1️⃣",
    12: "1️⃣2️⃣",
    13: "1️⃣3️⃣",
    14: "1️⃣4️⃣",
    15: "1️⃣5️⃣",
    16: "1️⃣6️⃣",
    17: "1️⃣7️⃣",
    18: "1️⃣8️⃣",
    19: "1️⃣9️⃣",
    20: "2️⃣0️⃣"
}

async def choose_table(update, query):

    user_session = await get_user_session(update.effective_user.id)
    max_tables = user_session['max_tables']

    keyboard = []
    row = []

    for i in range(1, max_tables + 1):
        emoji = EMOJI_NUMBERS.get(i, str(i))  # fallback to normal number

        button = InlineKeyboardButton(
            text=emoji,
            callback_data=f"table_{i}"
        )

        row.append(button)

        if len(row) == 3:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="Select a table:",
        reply_markup=reply_markup
    )

async def order_meal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_session = await get_user_session(update.effective_user.id)
    service_mode = user_session['service_mode'].lower()
    business_type = user_session['business_type'].lower()
    keyboard = []

    # 🟢 Vendor → always delivery only
    if business_type == "vendor":
        keyboard.append([
            InlineKeyboardButton("🚚 Delivery", callback_data="order_delivery")
        ])

    # 🟡 Restaurant
    else:
        row = []

        if service_mode.lower() in ["dine_in", "both"]:
            row.append(InlineKeyboardButton("🍽️ Dine-in", callback_data="order_dine_in"))

        if service_mode.lower() in ["delivery", "both"]:
            row.append(InlineKeyboardButton("🚚 Delivery", callback_data="order_delivery"))

        keyboard.append(row)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="How would you like to order?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )