# handlers/button_handler.py - EXACT COPY FROM ORIGINAL FILE
from datetime import timezone, datetime
from datetime import time
from services.restaurant_cache import get_restaurant
from .order_handler import choose_table
from core.config import *
from utils.cart_utils import *
from utils.image_utils import *
from utils.kitchen_utils import *
from .kitchen_handler import api_get_user_order_batches, update_batch_table
from .dynamic_virtual import generate_dynamic_virtual_account
from .echo_handler import payment_keyboard
import pytz



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


async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    print("Button clicked data:", data)

    if data == 'bank_transfer':

        await query.answer("Processing payment...")
        await query.message.reply_text("⏳ Generating account...")
        
        virtual_account = await generate_dynamic_virtual_account(update, context)
        if not virtual_account:
            return None

        # Define the new buttons you want to show
        keyboard = [
            [InlineKeyboardButton("Back ⬅️", callback_data='back_to_payment_menu')]
        ]

        bank = virtual_account.get('bank')
        bank_account_name = virtual_account.get('account_name') or "FORKCO"
        bank_account_number = virtual_account.get('account_number')

        account_info = (
            f"🏦 Bank: <b>{bank}</b>\n\n"
            f"🔢 Account Number: <code>{bank_account_number}</code>\n\n"
            f"👤 Account Name: <b>{bank_account_name}</b>"
        )

        await query.edit_message_text(
            # chat_id=update.effective_chat.id,
            text=f"📝 <b>Account Details</b>\n\n"
                f"Please make your payment to the following account:\n\n"
                f"{account_info}\n\n"
                f"💡 Tap and hold the account number to copy.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        
    elif data == "back_to_payment_menu":
        # await query.message.delete()

        await query.edit_message_text(
            text="💰 *Choose your payment method:*",
            reply_markup=await payment_keyboard(),
            parse_mode="Markdown"
        )

    elif data.startswith("processing_"):
        status = 'processing'
        batch_id = data.split("_")[1]
        restuarant_id = data.split("_")[2]
        user_session = await get_user_session(update.effective_user.id)
        current_restaurant_id = user_session.get('current_rid')
        print("processing restuarant_id: ", restuarant_id)
        print("current_rid restuarant_id ptb: ", current_restaurant_id)

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

    elif data.startswith("table_"):
        user_id = update.effective_chat.id

        user_session = await get_user_session(user_id)
        table_number = user_session['table_number']
        table_number_emoji = EMOJI_NUMBERS.get(table_number)

        print("table_number emoji: ", table_number)

        keyboard = [
            [
                InlineKeyboardButton("YES", callback_data="yes"),
                InlineKeyboardButton("NO", callback_data="no"),
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text=f"Are you sure you are on Table {table_number}? Please cross check your Table",
            reply_markup=reply_markup
        )

    elif data == "yes":
        await menu_keyboard(update, query)

    elif data == "no":

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
            text="Please select your correct table.",
            reply_markup=reply_markup
        )

    elif data == "order_dine_in":
        user_session = await get_user_session(update.effective_user.id)
        user_session['user_service_mode'] = 'dine_in'
        await save_user_session(update.effective_user.id, user_session)

        await query.answer("🍽️ Dine-in Menu 📜🍔 coming right up! 🎉")
        await choose_table(update, query)

    elif data == "order_delivery":
        restaurant_data = await get_user_session(update.effective_user.id)
        business_type = restaurant_data['business_type']
        service_mode = restaurant_data['service_mode']
        
        # 🔥 Check delivery hours ONLY for restaurants that offer delivery
        if service_mode.lower() in ['delivery', 'both']:
            is_available, message = await is_delivery_available(update)
            
            if not is_available:
                await context.bot.send_message(
                    text=message,
                    chat_id=update.effective_user.id
                )
                return  # 🔥 IMPORTANT: Stop here, don't proceed
        
        # ✅ Only reach here if:
        # - Business is VENDOR, OR
        # - Restaurant AND delivery is available
        user_session = await get_user_session(update.effective_user.id)
        user_session['user_service_mode'] = 'delivery'
        user_session.pop('table_number', None)
        
        await save_user_session(update.effective_user.id, user_session)
        
        await query.answer("🚚 Delivery Menu 📜🍔 coming right up! 🎉")
        await menu_keyboard(update, query)


    elif data == "pay_cash":
        orders_batches = await api_get_user_order_batches(update)
        pass
    elif data == "pay_transfer":
        orders_batches = await api_get_user_order_batches(update)
        pass
    elif data == "pay_cash":
        orders_batches = await api_get_user_order_batches(update)

        pass

async def is_delivery_available(update):
    user_session = await get_user_session(update.effective_user.id)
    restaurant_id = user_session['current_rid']
    
    # ✅ ALWAYS fetch fresh restaurant data (cache TTL is 5 minutes)
    restaurant_data = await get_restaurant(restaurant_id)
    print("restaurant_data: ", restaurant_data)
    print(f"Fetching fresh restaurant data for {restaurant_id}")
    
    if not restaurant_data:
        return False, "Restaurant data unavailable. Please try again."
    
    time_zone = restaurant_data['time_zone']
    open_time_str = restaurant_data['open_time']
    close_time_str = restaurant_data['close_time']
    is_closed = restaurant_data['is_closed']

    print(f"Fresh restaurant data for {restaurant_id}: open={open_time_str}, close={close_time_str}, closed={is_closed}")

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
    table_number = user_session.get('table_number')

    platform = "telegram"  # or "whatsapp", depending on the platform
    if user_service_mode == 'dine_in':
        WEB_APP_URL = f"{NGROK_DJANGO}/api/menu/{restaurant_id}/?mode=dine_in&table={table_number}&platform={platform}"

    elif user_service_mode == 'delivery':
        WEB_APP_URL = f"{NGROK_DJANGO}/api/menu/{restaurant_id}/?mode=delivery&platform={platform}"
    else:
        WEB_APP_URL = f"{NGROK_DJANGO}/api/menu/{restaurant_id}/?platform={platform}"
    reply_keyboard = [
        [
            InlineKeyboardButton(
                text="Open Mini Restaurant App (🍔🍟🌭🍕)",
                web_app=WebAppInfo(url=WEB_APP_URL),
            )
        ]
    ]

    markup = InlineKeyboardMarkup(reply_keyboard)

    await query.edit_message_text(
        text="Please click the menu button to see our meals :",
        reply_markup=markup
    )

