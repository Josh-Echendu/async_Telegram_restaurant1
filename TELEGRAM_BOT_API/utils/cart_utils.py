# utils/cart_utils.py - EXACT COPY FROM ORIGINAL FILE
from config import *
import telegram
from utils.image_utils import Extract_message_img_ids
from decimal import Decimal

async def update_qty_button(context, query, product_name, qty, price_per_item, total_price):
    
    # Extract the inline keyboard list from the message
    keyboard = query.message.reply_markup.inline_keyboard
    print("keyboard type:", keyboard)
    print('First row of keyboard:', keyboard[0][1])
    print("query:", query)
    print("query message caption:", query.message.caption)
    print("Existing keyboard:", keyboard)

    new_keyboard = []
    changed = False

    for row in keyboard:
        new_row = []
        for button in row:
            if button.callback_data == f"add_{product_name}":
                new_row.append(button)

            elif button.callback_data == f"remove_{product_name}":
                new_row.append(button)

            elif button.callback_data == "noop":

                # extract old qty from text
                old_qty = int(button.text.replace("⚖️ ", "").strip())
                if old_qty != qty:
                    changed = True

                # replace qty button
                new_row.append(
                    InlineKeyboardButton(f"⚖️ {qty}", callback_data="noop")
                )
            else:
                new_row.append(button)
                
        new_keyboard.append(new_row)

    # Calculate total price
    new_caption = f"{product_name} - ₦{price_per_item:,} \nQty: {qty} | Total: ₦{total_price:,}"
    # 🚫 If nothing changed, DO NOTHING (avoid Telegram error)
    if not changed and query.message.caption == new_caption:
        return

    # Edit message caption and keyboard in one go
    try:
        await query.edit_message_caption(
        caption=new_caption,
        reply_markup=InlineKeyboardMarkup(new_keyboard)
    )
    except telegram.error.BadRequest:
        pass


async def cart_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["🛒💚 View Cart", "🛍️✅💳 Checkout/Pay"],
        ["⬅️ Back"]
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    await update.message.reply_text("Select an item from the menu below:", reply_markup=reply_markup)

    # await update.message.reply_text("Here are the options for Today 🍟🍟🍟:", reply_markup=reply_markup)

async def more_menu_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ['🥤🍾🍷 Drinks / Beverages'],
        ["🛒💚 View Cart", "🛍️✅💳 Checkout/Pay"],
        ["⬅️ Back"]
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    await update.message.reply_text("Select an item from the menu below:", reply_markup=reply_markup)

    # await update.message.reply_text("Here are the options for Today 🍟🍟🍟:", reply_markup=reply_markup)


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
