# utils/cart_utils.py - EXACT COPY FROM ORIGINAL FILE
from core.config import *
import telegram
from utils.image_utils import Extract_message_img_ids
from decimal import Decimal


async def checkout_pay(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id=None, show_buttons=True):
    telegram_id = update.effective_user.id

    meal_type = await redis_client.get(f"user:{telegram_id}:meal_type")
    if not meal_type:
        return
    
    active_cart = await get_cart_items(update)
    if not active_cart:

        await Extract_message_img_ids(update, context)
        await update.message.reply_text(
            "🛒 Your cart is empty.\nPlease add items before paying."
        )
        return

    # Delete all previous meal messages ids concurrently
    await Extract_message_img_ids(update, context)

    # Build checkout summary dynamically
    lines = []

    # Calculate total price
    total_price = sum(Decimal(item.get('total_price')) for item in active_cart)

    for item in active_cart:
        subtotal = item.get('total_price')
        qty = item.get('quantity')
        product_name = item.get('product_title')
        lines.append(f"{qty}X - {product_name} - ₦{Decimal(subtotal):,}")

    summary = (
        "🧾 *Your Order Summary*\n\n"
        + "\n".join(lines)
        + f"\n\n——————————\n*Total: ₦{total_price:,}*"
    )

    if show_buttons:
        keyboard = [
            [
                InlineKeyboardButton("✅ Send to Kitchen", callback_data=f"order_to_kitchen"),
                InlineKeyboardButton(f"[ ❌ Cancel ]", callback_data="cancel_order"),
            ]
        ]
        msg = await update.message.reply_text(text=summary, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        if chat_id and not show_buttons:
            # Only send text summary, no buttons
            await context.bot.send_message(chat_id=chat_id, text=summary)
            return 

    # Extract checkout_message_id
    await redis_client.set(f"user:{telegram_id}:checkout_message_id", msg.message_id)
