# handlers/echo_handler.py - EXACT COPY FROM ORIGINAL FILE
from .kitchen_handler import api_get_user_order_batches
from TELEGRAM_BOT_API.core.config import *
from TELEGRAM_BOT_API.utils.cart_utils import *
from TELEGRAM_BOT_API.utils.image_utils import *
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
    
    elif text == "🛍️ Browse Products":
        await order_meal(update, context)

    elif text == "📦 Track Order":
        await update.message.reply_text("Coming soon 😊.")
    
    elif text == "📞 Contact Staff":
        first_name = update.effective_chat.first_name
        await update.message.reply_text(f"Good day {first_name} 😊, to contact us you call us on \n\n CONTACT: +234 906 393 8743.")

    elif text == "🛍️✅💳 Checkout/Pay":
        user_session = await get_user_session(update.effective_chat.id)
        business_type = user_session.get('business_type')
        
        service_mode = (user_session.get('service_mode') or "").lower()
        hotel_service_type = (user_session.get('hotel_service_type') or "").lower()  # ← FIXED: added .get()

        # ✅ Check if user is allowed to checkout (postpay only)
        if service_mode in ['dine_in', 'both']:
            lines = []
            grand_total = 0  # ← FIXED: removed int()
            vat = 100

            order_batches = await api_get_user_order_batches(update)
            
            if not order_batches:
                await update.message.reply_text("You have no active orders.")
                return
            
            restaurant_name = order_batches[0]['restaurant'] if order_batches else "Unknown"
            
            for order in order_batches:
                lines.append(f"🆔 BATCH ID: <i><b>{order['bid']}</b></i>")

                for item in order["items"]:
                    qty = item["quantity"]
                    price = item["price"]
                    title = item["product_title"]
                    subtotal = qty * price
                    lines.append(f"<i>{qty}x {title} - ₦{subtotal:,}</i>")

                grand_total += int(order["total_price"])
                lines.append("")  # blank line between batches

            summary = (
                "🧾 <b>Your Order Summary</b>\n\n"
                f"Restaurant 📜🍽️🍷: <i>{restaurant_name}</i>\n"
                f"👤 Customer: <i>{update.effective_chat.first_name}</i>\n\n"
                + "\n".join(lines)
                + f"\n\nTotal Price: ₦{grand_total:,}"
                + f"\nVAT Charges(7.5%): ₦{vat:,}"
                + f"\n——————————\n<b>Grand Total: ₦{grand_total + vat:,}</b>"
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
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ You are not allowed to use the Checkout/Pay button.\n\n"
                    "This option is only available for:\n"
                    "• Restaurant Dine-in\n"
                    "• Hotel Dine-in\n"
                    "• Both services",
                parse_mode="HTML"
            )

            
async def payment_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💵 Cash Payment", callback_data="pay_cash"),
        ],
        [
            InlineKeyboardButton("🏦💸💳 Bank/Card Transfer", callback_data="bank_transfer"),
        ],
        [
            InlineKeyboardButton("🛒💳 POS Payment", callback_data="pay_pos"),
        ]
    ]

    return InlineKeyboardMarkup(keyboard)