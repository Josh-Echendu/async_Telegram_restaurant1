# handlers/payment_handler.py - EXACT COPY FROM ORIGINAL FILE
from utils.image_utils import store_message_id
from config import *
from handlers.start_handler import after_payment


async def pay_now(update, context, order_batches=None, query=None):
    # context.user_data['cart_locked'] = True

    # delete the Transfer and cancel buttons
    if query: await query.edit_message_text("🍽️ Order sent to the kitchen! 🎉")

    user = update.effective_user
    first_name = user.first_name

    lines = []
    grand_total = Decimal("0.00")

    for order in order_batches:
        lines.append(f"🆔 BATCH ID: {order['bid']}")

        for item in order["items"]:
            qty = item["quantity"]
            price = item["price"]
            title = item["product__title"]
            subtotal = qty * price
            lines.append(f"{qty}x {title} - ₦{Decimal(subtotal):,}")

        grand_total += Decimal(order["total_price"])
        lines.append("")  # blank line between batches

    account_info = "Bank: XYZ Bank\nAccount Number: 1234567890\nAccount Name: ABC Restaurant"
    summary = (
        "🧾 *Your Order Summary*\n"
        f"👤 Customer: {first_name}\n\n"
        + "\n".join(lines)
        + f"\n——————————\n*Total: ₦{Decimal(grand_total):,}*"
        + f"\n\nPlease make your payment to the following account:\n\n{account_info}\n\nThank you for your order!"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ I have paid", callback_data="confirm_payment"),

        ],
        [
            InlineKeyboardButton(f"[ ❌ Cancel ]", callback_data="cancel_order"),
        ]
    ]

    msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=summary,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    await store_message_id(update, context, msg.message_id)



    # keyboard = [
    #     [
    #         InlineKeyboardButton("✅ I have paid", callback_data="confirm_payment"),
    #     ]
    # ]