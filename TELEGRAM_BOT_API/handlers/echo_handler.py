# handlers/echo_handler.py - EXACT COPY FROM ORIGINAL FILE
from .kitchen_handler import api_get_user_order_batches
from core.config import *
from utils.cart_utils import *
from utils.image_utils import *
from .payment_handler import pay_now
from .start_handler import start
from .order_handler import order_meal
from decimal import Decimal


async def debug_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass
    # always turn off privacy with /setprivacy so bot can receive all messages sent to group
    print("CHAT ID:", update.effective_chat.id)
    print("CHAT data structure:", type(update.effective_chat.id))
    print("CHAT TYPE:", update.effective_chat.type)
    print("CHAT:", update)    

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "🍽 Order Food":
        await order_meal(update, context)

    elif text == "📦 Track Order":
        await update.message.reply_text("Coming soon 😊.")
    
    elif text == "📞 Contact Staff":
        first_name = update.effective_chat.first_name
        await update.message.reply_text(f"Good day {first_name} 😊, to contact us you call us on \n\n CONTACT: +234 906 393 8743.")

    elif text == "ℹ️ Help":
        await update.message.reply_text("You have chosen to get help.")
        
    elif text == "🛍️✅💳 Checkout/Pay":
        lines = []
        grand_total = int(0)  # ← initialize here
        vat = int(100)

        order_batches = await api_get_user_order_batches(update)
        # print("batches......", order_batches)

        if not order_batches:
            await update.message.reply_text("You have no active orders.")
            return
        
        for order in order_batches:
            lines.append(f"🆔 BATCH ID: <i><b>{order['bid']}</b></i>")

            for item in order["items"]:
                qty = item["quantity"]
                price = item["price"]
                title = item["product_title"]
                subtotal = qty * price
                lines.append(f"<i>{qty}x {title} - ₦{subtotal:,}</i>")

            grand_total += int(order["total_price"])  # now this works
            lines.append("")  # blank line between batches

        summary = (
            "🧾 <b>Your Order Summary</b>\n\n"
            f"Restaurant 📜🍽️🍷: <i>{order['restaurant']}</i>\n"
            f"👤 Customer: <i>{update.effective_chat.first_name}</i>\n\n"
            + "\n".join(lines)
            + f"\n\nTotal Price: ₦{grand_total:,}"
            + f"\nVAT Charges: ₦{vat:,}"
            + f"\n——————————\n<b>Grand Total: ₦{int(grand_total + vat):,}</b>"
        )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=summary,
            parse_mode="HTML"
        )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="💰 *Choose your payment method:*",
            reply_markup=await payment_keyboard(),
            parse_mode="Markdown"
        )
        
async def payment_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💵 Cash Payment", callback_data="pay_cash"),
        ],
        [
            InlineKeyboardButton("🏦💸 Bank Transfer", callback_data="bank_transfer"),
        ],
        [
            InlineKeyboardButton("🛒💳 POS Payment", callback_data="pay_pos"),
        ],
        [
            InlineKeyboardButton("❌ Cancel Order", callback_data="cancel_order")
        ]
    ]

    return InlineKeyboardMarkup(keyboard)