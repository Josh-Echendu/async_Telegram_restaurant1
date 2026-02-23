# utils/kitchen_utils.py - EXACT COPY FROM ORIGINAL FILE
from handlers.order_handler import order_meal
from config import *
from decimal import Decimal
from utils.cart_utils import *
import shortuuid

async def send_to_kitchen(update: Update, context: ContextTypes.DEFAULT_TYPE, query):
    active_cart = await get_cart_items(update)     

    if not active_cart:
        await query.answer("Cart is empty", show_alert=True)
        await query.message.delete()
        return order_meal(update, context)

    copy_cart = active_cart.copy()
    key = shortuuid.uuid()
    await order_batches(update, context, copy_cart, query, key)
    
    # if batch_id is None:
    #     batch_id, safe_items = await order_batches(update, context, copy_cart, query, key)
    #     if not batch_id:
    #         print("second batch......")
    #         await context.bot.send_message(chat_id=query.message.chat.id, text="😔 Sorry your order couldn't be sent to the kitchen.\n\n Please click 🛍️✅💳 Checkout/Pay menu below 👇👇!!")
    #         return

    # user = update.effective_user
    # safe_items_copy = safe_items.copy()
    # lines = [f"{int(item.get('quantity'))}X - {item.get('product_title')} - ₦{Decimal(item.get('total_price'))}" for item in safe_items_copy]
    # total = sum(int(item.get('quantity')) * Decimal(item.get('product_price')) for item in safe_items_copy)

    # kitchen_text = (
    #     "🔥 NEW ORDER RECEIVED\n\n"
    #     f"👤 Customer: {user.first_name}\n"
    #     f"🆔 User ID: {user.id}\n\n"
    #     "📦 Items:\n" + "\n".join(lines)+
    #     f"\n\n——————————\n*Total: ₦{total}*\n\n"
    #     "⏳ Status: Pending"
    # )

    # kitchen_keyboard = [[
    #     InlineKeyboardButton("⏳🔄 Processing", callback_data=f"processing_{batch_id}"),
    #     InlineKeyboardButton("📦✅ Delivered", callback_data=f"delivered_{batch_id}"),
    # ]]

    # await context.bot.send_message(
    #     chat_id=KITCHEN_CHAT_ID,
    #     text=kitchen_text,
    #     reply_markup=InlineKeyboardMarkup(kitchen_keyboard))

    # context.user_data.pop("checkout_message_id", None)

    # keyboard = [
    #     [
    #         InlineKeyboardButton("➕ Add More Items", callback_data="order_more_items"),
    #         InlineKeyboardButton("💳 Pay Now", callback_data="pay_now"),
    #     ],
    #     [
    #         InlineKeyboardButton("📉📈📶📦 Track Orders", callback_data="track_orders"),
    #     ]
    # ]

    # msg = await context.bot.send_message(
    #     chat_id=update.effective_chat.id,
    #     text="🍽️ Order sent to the kitchen! 🎉🎉🎉\n\nWhat would you like to do next?",
    #     reply_markup=InlineKeyboardMarkup(keyboard)
    # )
    # context.user_data['send_to_kitchen_id'] = msg.message_id


async def order_batches(update, context, cart_items, query, idempotency_key, max_retries=3):
    user = update.effective_user
    telegram_id = user.id

    payload = {
        "idempotency_key": idempotency_key,
        "cart_items": cart_items,
        "telegram_id": telegram_id
    }

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "http://web:8000/api/order_batches/",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                # ✅ Safely parse JSON only if possible
                data = resp.json()

                # ✅ Handle removed items gracefully
                removed_items = data.get("removed_items") 
                safe_cart_items = data.get('safe_cart_items')

                if removed_items and safe_cart_items:
                    item_list = "\n".join(removed_items)
                    sorry_message = (
                        "😔 Sorry! The following item(s) are out of stock and were removed from your cart:\n\n"
                        f"{item_list}\n\n"
                        "Sorry for the inconvenience 😔"
                    )
                    lines = []
                    total_price = sum(Decimal(item.get('total_price')) for item in safe_cart_items)

                    for item in safe_cart_items:
                        subtotal = item.get('total_price')
                        qty = item.get('quantity')
                        product_name = item.get('product_title')
                        lines.append(f"{qty}X - {product_name} - ₦{Decimal(subtotal):,}")

                    summary = (
                        "🧾 *Your New Order Summary*\n\n"
                        + "\n".join(lines)
                        + f"\n\n——————————\n*Total: ₦{total_price:,}*"
                    )

                    await context.bot.send_message(chat_id=query.message.chat.id, text=sorry_message)
                    await context.bot.send_message(chat_id=query.message.chat.id, text=summary)
                    return (data.get("batch_id"), safe_cart_items)

                if resp.status_code in (200, 201):
                    print("order batches:", data)
                    return (data.get("batch_id"), safe_cart_items)

                # Optional fallback
                logging.warning(f"Unexpected response: {resp.status_code} → {data}")
                return None

        except (httpx.RequestError, httpx.HTTPStatusError, ValueError, Exception) as e:

            logging.warning(f"Attempt {attempt} failed to submit cart items to kitchen: {e}")

            if attempt == max_retries:
                logging.error(f"All {max_retries} attempts failed to submit cart items to kitchen.")
                return None

            await asyncio.sleep(1)
