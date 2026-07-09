# handlers/order_handler.py - EXACT COPY FROM ORIGINAL FILE
from TELEGRAM_BOT_API.core.config import *
from TELEGRAM_BOT_API.utils.cart_utils import *
from TELEGRAM_BOT_API.utils.image_utils import *
from telegram import InlineKeyboardButton, InlineKeyboardMarkup



async def order_meal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_session = await get_user_session(update.effective_user.id)
    service_mode = user_session.get('service_mode') or ''
    service_mode = service_mode.lower()
    business_type = (user_session.get('business_type') or "").lower()
    
    keyboard = []

    # 🟢 Vendor → always delivery only
    if business_type == "vendor":
        
        keyboard.append([
            InlineKeyboardButton("🚚 Delivery", callback_data="order_delivery")
        ])


    # 🟡 Restaurant → depends on service_mode
    elif business_type == "restaurant":
        
        row = []
        if service_mode in ["dine_in", "both"]:
            row.append(InlineKeyboardButton("🍽️ Dine-in", callback_data="order_dine_in"))
        
        if service_mode in ["delivery", "both"]:
            row.append(InlineKeyboardButton("🚚 Delivery", callback_data="order_delivery"))
        
        if row:
            keyboard.append(row)


    # ❌ No options available
    if not keyboard:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Ordering is not available for your business type. Please contact support."
        )
        return

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="How would you like to order?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )