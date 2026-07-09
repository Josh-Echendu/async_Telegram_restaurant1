# handlers/button_handler.py - EXACT COPY FROM ORIGINAL FILE
from datetime import timezone, datetime
from datetime import time
import json
import math
from TELEGRAM_BOT_API.services.restaurant_cache import get_restaurant
from TELEGRAM_BOT_API.core.config import *
from TELEGRAM_BOT_API.utils.cart_utils import *
from TELEGRAM_BOT_API.utils.image_utils import *
from TELEGRAM_BOT_API.utils.kitchen_utils import *
from .kitchen_handler import api_get_user_order_batches, handle_pos_cash_payment, update_batch_table, save_pos_and_cash_payment
from .dynamic_virtual import generate_dynamic_virtual_account
from .echo_handler import payment_keyboard
import pytz
import math
import secrets
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_dine_session_key(platform: str, user_id: str) -> str:
        return f"{platform}_dine_user_session:{user_id}"

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    logger.info("Button clicked data: %s", data)

    if data == "back_to_payment_menu":
        # await query.message.delete()

        await query.edit_message_text(
            text="💰 *Choose your payment method:*",
            reply_markup=await payment_keyboard(),
            parse_mode="Markdown"
        )


    elif data.startswith("confirm-payment_"):
        payment_key = data.split('_')[1]
        customer_user_id = data.split('_')[-1]

        query = update.callback_query
        await query.answer()

        # ✅ Fetch from Redis
        payment_data = await redis_client.get(f"payment:{payment_key}")
        logger.info("payment data: %s", payment_data)
        
        if not payment_data:
            await query.edit_message_text("❌ This payment request has expired.")
            return
        
        payment_data =  json.loads(payment_data)
        
        # Show confirmation question
        await query.edit_message_text(
            text="🤔 Are you sure the user has paid?\n\n"
                f"Table: {payment_data['table']}\n"
                f"Total: ₦{payment_data['grand_total']:,}\n"
                "⚠️ This action cannot be undone.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Yes, Confirm Payment", callback_data=f"confirm-yes_{payment_key}_{customer_user_id}"),
                    InlineKeyboardButton("❌ No, Go Back", callback_data=f"confirm-no_{payment_key}_{customer_user_id}")
                ]
            ]),
            parse_mode="HTML"
        )


    elif data.startswith("confirm-no_"):
        # payment_key = data.replace("confirm_no_", "")

        payment_key = data.split('_')[1]
        customer_user_id = data.split('_')[-1]
        
        query = update.callback_query
        await query.answer()

        # ✅ Fetch from Redis
        payment_data = await redis_client.get(f"payment:{payment_key}")
        
        if not payment_data:
            await query.edit_message_text("❌ This payment request has expired.")
            return
        
        payment_data = json.loads(payment_data)

        # 🔙 Go back to original confirm button
        waiter_message = (
            f"💳 <b>PAYMENT REQUEST</b> 💳\n\n"
            f"Table: <code>{payment_data.get('table')}</code>\n"
            f"Subtotal: <b>₦{payment_data.get('total'):,}</b>\n"
            f"VAT(7.5%): <b>₦{payment_data.get('vat_amount'):,}</b>\n\n"
            f"Grand Total: <b>₦{payment_data.get('grand_total'):,}</b>\n\n"
            f"Method: {payment_data.get('emoji')} {payment_data.get('payment_type').upper()}\n\n"
            f"👨‍💼 <i>Waiter, please proceed to Table {payment_data.get('table')}.</i>"
        )

        await query.edit_message_text(
            text=waiter_message,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm Payment", callback_data=f"confirm-payment_{payment_key}_{customer_user_id}")]
            ]),
            parse_mode="HTML"
        )

    elif data.startswith("confirm-yes_"):
        payment_key = data.split("_")[1]
        customer_user_id = data.split('_')[-1]

        query = update.callback_query
        await query.answer()

        # ✅ Fetch from Redis (WITH AWAIT)
        payment_data = await redis_client.get(f"payment:{payment_key}")
        
        if not payment_data:
            await query.edit_message_text("❌ This payment request has expired.")
            return
        
        payment_data = json.loads(payment_data)
        
        # ✅ Get session_id from Redis (WITH AWAIT + JSON parse)
        customer_platform = (payment_data.get('customer_platform') or "").lower()

        if customer_platform == 'telegram':
            redis_key = f"telegram_dine_user_session:{customer_user_id}"
        
        elif customer_platform == 'whatsapp': 
            redis_key = f"whatsapp_dine_user_session:{customer_user_id}"
        
        else:
            logger.error(
                "Unknown customer platform '%s' for payment %s",
                customer_platform,
                payment_key,
            )

        session_data_raw = await redis_client.get(redis_key)
        
        if not session_data_raw:
            await query.edit_message_text(
                "❌ No active session found.\n"
                "Please start a new order."
            )
            return
        
        session_data = json.loads(session_data_raw)
        session_id = session_data.get('session_id')

        if not session_id:
            await query.edit_message_text(
                "❌ Invalid session. Please try again."
            )
            return

        # ✅ Call the API to mark as paid
        result = await save_pos_and_cash_payment(update, payment_data.get('payment_type'), session_id)

        # ✅ Waiter that clicked the confirm payment Button
        waiter_in_charge = update.effective_user.username or update.effective_user.first_name
        
        if result:
            await query.edit_message_text(
                text="✅ <b>Payment Confirmed!</b>\n\n"
                    f"Table: {payment_data['table']}\n"
                    f"Subtotal: ₦{payment_data['total']:,}\n"
                    f"VAT: ₦{payment_data['vat_amount']:,}\n"
                    f"Grand Total: <b>₦{payment_data['grand_total']:,}</b>\n\n"
                    f"👨‍💼 Waiter: @{waiter_in_charge}\n"
                    f"✅ Status: Paid",
                reply_markup=None,
                parse_mode="HTML"
            )

            if customer_platform == 'telegram':
                    
                # ✅ Send receipt to customer
                await context.bot.send_message(
                    chat_id=customer_user_id,
                    text=(
                        f"✅ <b>Payment Confirmed!</b>\n\n"
                        f"Table: {payment_data['table']}\n"
                        f"Total: <b>₦{payment_data['grand_total']:,}</b>\n\n"
                        f"Thank you for dining with us! 🍽️"
                    ),
                    parse_mode="HTML"
                )

            elif customer_platform == 'whatsapp':

                restaurant_id = payment_data.get('restaurant_id')

                arq = await get_arq_redis()

                await arq.enqueue_job(
                    "notify_whatsapp_payment_confirmed",
                    customer_user_id=customer_user_id,
                    restaurant_id=restaurant_id,
                    table=payment_data["table"],
                    grand_total=payment_data["grand_total"],
                    _queue_name="restaurant_jobs",
                )

            
            # ✅ Delete from Redis
            await redis_client.delete(f"payment:{payment_key}")
            await redis_client.delete(redis_key)
            

    elif data.startswith("processing_"):
        status = 'processing'
        batch_id = data.split("_")[1]
        restuarant_id = data.split("_")[2]
        user_session = await get_user_session(update.effective_user.id)
        current_restaurant_id = user_session.get('current_rid')

        updated = await update_batch_table(batch_id, status, restuarant_id, query)
        if updated:
            # Show only delivered button after successful processing
            keyboard = [InlineKeyboardButton("📦✅ Delivered", callback_data=f'delivered_{batch_id}_{restuarant_id}')]
            await query.edit_message_reply_markup(InlineKeyboardMarkup([keyboard]))

    elif data.startswith("delivered_"):
        status = 'delivered'
        batch_id = data.split("_")[1]
        restuarant_id = data.split("_")[2]

        updated = await update_batch_table(batch_id, status, restuarant_id, query)
        if updated:
            # Remove buttons completely after delivered
            await query.edit_message_reply_markup(reply_markup=None)



    elif data == "order_dine_in":
        user_session = await get_user_session(update.effective_user.id)
        user_session['user_service_mode'] = 'dine_in'
        user_session.pop('table_number', None)
        await save_user_session(update.effective_user.id, user_session)

        await query.answer("🍽️ Dine-in Menu 📜🍔 coming right up! 🎉")
        await menu_keyboard(update, query)


    elif data == "order_delivery":
        user_session = await get_user_session(update.effective_user.id)
        business_type = user_session.get('business_type', '').lower()
        service_mode = (user_session.get('service_mode') or "").lower()
        
        # 🔥 Check delivery hours ONLY for restaurants that offer delivery/both and for vendors
        if service_mode in ['delivery', 'both']:
            is_available, message = await is_delivery_available(update)
            
            if not is_available:
                await query.answer("🚫 Delivery not available", show_alert=False)
                await context.bot.send_message(
                    text=message,
                    chat_id=update.effective_user.id
                )
                return  # 🔥 IMPORTANT: Stop here, don't proceed
        
        # ✅ Only reach here if:
        # - Business is HOTEL (room service), OR
        # - Restaurant/Vendor AND delivery is available
        user_session['user_service_mode'] = 'delivery'
        user_session.pop('table_number', None)
        await save_user_session(update.effective_user.id, user_session)
        
        await query.answer("🚚 Delivery Menu 📜🍔 coming right up! 🎉")
        await menu_keyboard(update, query)

    
    elif data == "bank_transfer":
        user_id = update.effective_user.id
        
        redis_key = f"telegram_dine_user_session:{user_id}"
        data = await redis_client.get(redis_key)
        
        if not data:
            await update.message.reply_text("❌ No active order found. Please start a new order.")
            return
        
        session_data = json.loads(data)
        
        session_id = session_data['session_id']
        restaurant_id = session_data['restaurant_id']
        platform = session_data['platform']
        
        PAYMENT_URL = f"{NGROK_DJANGO}/payments/{restaurant_id}/{platform}/{session_id}"
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "💳 PAY NOW",
                    web_app=WebAppInfo(url=PAYMENT_URL)
                )
            ]
        ]
        await query.edit_message_text(
            text="💳 Click below to complete your payment:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif data in ["pay_cash", "pay_pos"]:

        payment_type = "cash" if data == "pay_cash" else "pos"
        response = await handle_pos_cash_payment(update, payment_type)
        customer_user_id = update.effective_chat.id
        
        if not response:
            await query.edit_message_text(
                text="❌ Failed to process payment request. Please try again.",
                parse_mode="HTML"
            )
            return
        
        table = response.get('table_number', 'N/A')
        total = response.get('total', 0)
        vat_amount = response.get('vat')
        grand_total = response.get('grand_total')
        kitchen_chat_id = response.get('kitchen_chat_id')
        waiter_telegram_id = response.get('waiter_telegram_id')
        waiter_username = response.get('waiter_username')
        
        emoji = "💵" if payment_type == "cash" else "💳"
        method = "collect cash" if payment_type == "cash" else "with a POS machine"
        
        # Customer message
        message = (
            f"✅ <b>Payment Request Sent!</b>\n\n"
            f"📱 Please show this screen to your waiter.\n"
            f"{emoji} Your waiter has been notified and will come to your table to {method}.\n\n"
            f"Table: <code>{table}</code>\n"
            f"Subtotal: <b>₦{total:,}</b>\n\n"
            f"VAT(7.5%): <b>₦{vat_amount:,}</b>\n\n"
            f"Grand Total: <b>₦{grand_total:,}</b>\n\n"
            f"⏳ <i>Payment pending... Waiting for waiter confirmation.</i>\n\n"
            f"Thank you for dining with us! 🍽️"
        )
        
        await query.edit_message_text(
            text=message,
            parse_mode="HTML"
        )

        # Staff group notification
        max_retries = 3
        success = False

        for attempt in range(1, max_retries + 1):
            try:
                if kitchen_chat_id:

                    # Generate a short unique ID for this payment
                    payment_key = secrets.token_hex(8)  # 16 characters

                    # Store all data in Redis
                    await redis_client.setex(
                        f"payment:{payment_key}", 
                        86400,  # 24 hours expiry
                        json.dumps({
                            'table': table,
                            'total': total,
                            'vat_amount': vat_amount,
                            'grand_total': grand_total,
                            'payment_type': payment_type,
                            'emoji': emoji,
                            'waiter_telegram_id': waiter_telegram_id,
                            'waiter_username': waiter_username,
                            'kitchen_chat_id': kitchen_chat_id,
                            "customer_platform": "telegram",
                            "customer_user_id": customer_user_id,
                        })
                    )

                    # Send message with ONLY the short key in callback
                    keyboard = [[InlineKeyboardButton("✅ Confirm Payment", callback_data=f"confirm-payment_{payment_key}_{customer_user_id}")]]
                    
                    waiter_message = (
                        f"💳 <b>PAYMENT REQUEST</b> 💳\n\n"
                        f"Table: <code>{table}</code>\n"
                        f"Subtotal: <b>₦{total:,}</b>\n"
                        f"VAT(7.5%): <b>₦{vat_amount:,}</b>\n\n"
                        f"Grand Total: <b>₦{grand_total:,}</b>\n\n"
                        f"Method: {emoji} {payment_type.upper()}\n\n"
                        f"👨‍💼 <i>Waiter, please proceed to Table {table}.</i>"
                    )

                    await context.bot.send_message(
                        chat_id=kitchen_chat_id,
                        text=waiter_message,
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    success = True
                    break

            except Exception as e:
                logger.error(f"Attempt {attempt} failed to send payment notification: {e}")
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # 2, 4, 8 seconds (exponential backoff)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)

        # If all attempts failed
        if not success:
            logger.error(f"All {max_retries} attempts failed to send payment notification.")
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text="⚠️ We're having trouble notifying staff. Please inform your waiter manually."
            )
            

async def is_delivery_available(update):
    user_session = await get_user_session(update.effective_user.id)
    restaurant_id = user_session['current_rid']
    
    # ✅ ALWAYS fetch fresh restaurant data (cache TTL is 5 minutes)
    restaurant_data = await get_restaurant(restaurant_id)
    logger.info("restaurant_data: %s", restaurant_data)
    
    if not restaurant_data:
        return False, "Restaurant data unavailable. Please try again."
    
    time_zone = restaurant_data['time_zone']
    open_time_str = restaurant_data['open_time']
    close_time_str = restaurant_data['close_time']
    is_closed = restaurant_data['is_closed']

    logger.info(f"Fresh restaurant data for {restaurant_id}: open={open_time_str}, close={close_time_str}, closed={is_closed}")

    try:
        # convert string("Africa/Lagos") to timezone object using pytz class: <class 'pytz.tzfile.Africa/Lagos'>
        restaurant_tz = pytz.timezone(time_zone)
    except Exception:
        restaurant_tz = pytz.timezone('Africa/Lagos')

    # ✅ CORRECT: Use datetime with pytz
    now_utc = datetime.now(timezone.utc)  # london UTC

    # astimezone() converts UTC (London) time to whatever timezone the restaurant is in using pytz.
    now_local = now_utc.astimezone(restaurant_tz)

    # time(): Extract the time object
    current_time = now_local.time()

    # Check if restaurant is closed today
    if is_closed:
        return False, "🙏 We're closed for delivery today. See you tomorrow!"

    # Check if open_time and close_time exist
    if not open_time_str or not close_time_str:
        return False, "🙏 We're closed for delivery today. See you tomorrow!"

    # 🔥 CRITICAL: Convert string to time object
    try:
        # Always convert time strings from API/Redis to time objects before comparison!
        open_time = time.fromisoformat(open_time_str)
        close_time = time.fromisoformat(close_time_str)
    except Exception:
        return False, ""

    # Handle overnight hours (e.g., 11pm to 2am)
    if open_time <= close_time:
        # Normal hours (e.g., 09:00 to 22:00)
        is_open = open_time <= current_time <= close_time
    else:
        # Overnight hours (e.g., 22:00 to 02:00)
        is_open = current_time >= open_time or current_time <= close_time

    if not is_open:
        # Format times in 12-hour format for user
        open_12hr = open_time.strftime('%I:%M %p')
        close_12hr = close_time.strftime('%I:%M %p')
        return False, f"🚚 Delivery available from {open_12hr} to {close_12hr} ({time_zone})"

    return True, "Delivery available"



async def menu_keyboard(update, query):
    user_session = await get_user_session(update.effective_user.id)
    
    restaurant_id = user_session['current_rid']
    user_service_mode = user_session['user_service_mode']

    platform = "telegram"

    # Build URL with mode and platform
    WEB_APP_URL = f"{NGROK_DJANGO}/api/menu/{restaurant_id}/?mode={user_service_mode}&platform={platform}"

    reply_keyboard = [
        [
            InlineKeyboardButton(
                text="🍔 Open Menu",
                web_app=WebAppInfo(url=WEB_APP_URL),
            )
        ]
    ]

    markup = InlineKeyboardMarkup(reply_keyboard)

    await query.edit_message_text(
        text="📋 Please click the button below to view our menu and place your order:",
        reply_markup=markup
    )