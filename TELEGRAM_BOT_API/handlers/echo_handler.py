# handlers/echo_handler.py - EXACT COPY FROM ORIGINAL FILE
from .kitchen_handler import api_get_user_order_batches
from TELEGRAM_BOT_API.core.config import *
from TELEGRAM_BOT_API.utils.cart_utils import *
from TELEGRAM_BOT_API.utils.image_utils import *
from .start_handler import start
from .order_handler import order_meal
from decimal import Decimal
import math



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
        user_session = await get_user_session(update.effective_user.id)
        business_type = (user_session.get('business_type') or "").lower()
        service_mode = (user_session.get('service_mode') or "").lower()

        # ✅ Gate: checkout only allowed for postpay modes
        if service_mode not in ['dine_in', 'both']:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    "❌ <b>Checkout Not Available</b>\n\n"
                    "This option is only available for:\n"
                    "• Restaurant Dine-in\n"
                    "• Hotel Dine-in\n"
                    "• Both services"
                ),
                parse_mode="HTML",
            )
            logger.warning(f"User {update.effective_user.id} tried Checkout/Pay in mode: {service_mode}")
            return

        # ✅ Fetch batches via API
        result = await api_get_user_order_batches(update)

        if not result or not result.get("ok"):

            if result and result.get("recoverable"):
                raise Exception("fetching order batches Failed. will retry.")
            
            error_msg = result.get("error", "Unable to load your orders") if result else "Unable to load your orders"

            if result and result.get("session_id") is None:
                await update.message.reply_text(
                    "❌ <b>No Active Session Found</b>\n\n"
                    "🛒 You don't have an active order session.\n"
                    "🍽️ Please add some items to your cart first.",
                    parse_mode="HTML",
                )
                return
            
            await update.message.reply_text(
                f"⚠️ <b>Could Not Load Your Bill, Please Try again Thank you.</b>",
                parse_mode="HTML",
            )
            return


        data = result["data"]
        batches = data.get("batches", [])

        if not batches:
            await update.message.reply_text(
                "🛒 <b>No Active Orders</b>\n\nYou haven't placed any orders yet.",
                parse_mode="HTML",
            )
            return

        # ========== BUILD BILL SUMMARY ==========
        dine_session = data.get("dine_session") or {}
        host = data.get("host") or {}
        participants = data.get("participants", [])
        declined_participants = data.get("declined_participants", [])

        table_number = dine_session.get("table_number", "—")
        restaurant_name = user_session.get("restaurant_name") or "Restaurant"
        customer_name = update.effective_chat.first_name or "Guest"

        # Totals from API
        subtotal = float(data.get("subtotal", 0))

        vat_amount = math.ceil(subtotal * 0.075)   # Integer
        grand_total = math.ceil(subtotal + vat_amount)    # Integer

        # ========== FORMAT EACH BATCH ==========
        batch_lines = []
        for batch in batches:
            is_host = batch.get("is_host", False)
            user_label = batch.get("user_first_name", "Guest")
            host_marker = "👑" if is_host else "👤"

            batch_lines.append(
                f"{host_marker} <b>{user_label}</b>  ·  "
                f"<i>Batch: #{batch['bid']}</i>"
            )

            for item in batch.get("items", []):
                qty = item["quantity"]
                price = item["price"]
                title = item["product_title"]
                line_total = item.get(
                    "multiply_price",
                    float(item["quantity"]) * float(item["price"]),
                )

                batch_lines.append(
                    f"    • {qty}× {title} — ₦{line_total:,.0f}"
                )

            batch_lines.append(
                f"    <b>Subtotal:</b> ₦{batch['total_price']:,.0f}"
            )
            batch_lines.append("")  # spacer between batches

        # ========== PARTICIPANTS SUMMARY ==========
        people_count = 1 + len(participants)  # host + accepted participants
        people_line = f"👥 <b>{people_count}</b> at table"

        if declined_participants:
            people_line += f" · ⚠️ {len(declined_participants)} declined"

        # ========== FINAL MESSAGE ==========
        summary = (
            f"🧾 <b>BILL — TABLE {table_number}</b>\n"
            f"<i>{restaurant_name}</i>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"

            f"👤 Customer: <i>{customer_name}</i>\n"
            f"{people_line}\n"
            f"🍽️ Batches: <b>{len(batches)}</b>\n\n"

            "━━━━━━━━━━━━━━━━━━━━\n"
            "<b>ORDER BREAKDOWN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"

            + "\n".join(batch_lines) +

            "\n━━━━━━━━━━━━━━━━━━━━\n"
            "<b>BILL SUMMARY</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"Subtotal:          ₦{subtotal:,.0f}\n"
            f"VAT (7.5%):        ₦{vat_amount:,.0f}\n"
            # f"Bank Fee:          ₦{bank_fee:,.0f}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>GRAND TOTAL:      ₦{grand_total:,.0f}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )

        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=summary,
            parse_mode="HTML",
        )

        # ========== PAYMENT PROMPT ==========
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="💰 <b>Choose your payment method</b>",
            reply_markup=await payment_keyboard(),
            parse_mode="HTML",
        )



    else:
        await start(update, context)      
        
          
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