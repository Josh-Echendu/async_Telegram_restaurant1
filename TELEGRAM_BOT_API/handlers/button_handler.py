# handlers/button_handler.py - EXACT COPY FROM ORIGINAL FILE
from config import *
import telegram
from utils.cart_utils import *
from utils.image_utils import *
from utils.kitchen_utils import *
from .payment_handler import pay_now
from .start_handler import after_payment, start
from .order_handler import order_meal_by_chat_id
from .kitchen_handler import api_get_user_order_batches, update_batch_table
from .dynamic_virtual import generate_dynamic_virtual_account
from .echo_handler import payment_keyboard



async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    print("Button clicked data:", data)

    if data == 'pay_now':
        await redis_client.delete(f"user:{user_id}:send_to_kitchen_id")

        # Get us the orders ther customer has made
        order_batches_data = await api_get_user_order_batches(update)

        # if no orders made by the user
        if order_batches_data == []:
            await query.answer("You have not made any order Today 😊.", show_alert=True)
            await query.message.delete()
            return
        
        await redis_client.delete(f"user:{user_id}:send_to_kitchen_id")

        copy_order_batches_data = order_batches_data.copy()
        await pay_now(update, context, copy_order_batches_data, query)

    elif data == 'cancel_order':
        await query.answer("❌ Order cancelled")
        await redis_client.delete(f"user:{user_id}:checkout_message_id")

        # Unlock cart
        # context.user_data['cart_locked'] = False
        print("query message: ", query)
        await query.message.reply_text("Your order has been cancelled. You can continue ordering.")
        try: await query.message.delete()
        except Exception as e:
            logging.error(f"Error deleting message: {e}")
            pass  # message may already be deleted

        finally:

            # Extract message chat.id bcos update.message for a callback_query is None
            await order_meal_by_chat_id(query.message.chat.id, context)

    elif data == 'confirm_payment':
        await query.answer("✅ Payment confirmed. Thank you!")

        await query.edit_message_reply_markup(reply_markup=None)

        photo_url = r'C:\Users\Admin\Music\async_Telegram_restaurant\photo_2026-01-09 14.59.50.jpeg'

        input_file = InputFile(open(photo_url, 'rb'))

        await context.bot.send_photo(
            chat_id=query.message.chat.id,
            caption="🎉 Your payment has been received! Thank you for choosing our service! 🍽️😊",
            photo=input_file
        )

        # Clear cart and unlock cart
        context.user_data['cart_locked'] = False
        await after_payment(query.message.chat.id, context)

    elif data == "order_more_items":
        await redis_client.delete(f"user:{user_id}:send_to_kitchen_id")
        await query.edit_message_text("🍽️ Order sent to the kitchen! 🎉")

        # Extract message chat.id bcos update.message for a callback_query is None
        await order_meal_by_chat_id(query.message.chat.id, context)

    elif data == "track_orders":
        await redis_client.delete(f"user:{user_id}:send_to_kitchen_id")

        # Get us the orders ther customer has made
        order_batches_data = await api_get_user_order_batches(update)

        # if no orders made by the user
        if order_batches_data is None:
            query.answer("You have not made any order Today 😊.", show_alert=True)
            return
        
        await query.edit_message_text("🍽️ Order sent to the kitchen! 🎉")
        await start(update, context, Track_orders=True)

    elif data == 'bank_transfer':

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
        print("processing restuarant_id: ", restuarant_id)

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

        restaurant_data = await get_restaurant_data(update)
        restaurant_id = restaurant_data['current_rid']
        WEB_APP_URL = f"{NGROK_DJANGO}/api/restaurant/{restaurant_id}/menu/"

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

    elif data == "no":

        await query.edit_message_text(
            text="Please select your correct table.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("1️⃣", callback_data="table_1"),
                    InlineKeyboardButton("2️⃣", callback_data="table_2"),
                ],
                [
                    InlineKeyboardButton("3️⃣", callback_data="table_3"),
                    InlineKeyboardButton("4️⃣", callback_data="table_4"),
                ],
            ])
        )
    elif data == "pay_cash":
        orders_batches = await api_get_user_order_batches(update)
        pass
    elif data == "pay_transfer":
        orders_batches = await api_get_user_order_batches(update)
        pass
    elif data == "pay_cash":
        orders_batches = await api_get_user_order_batches(update)

        pass

async def add_to_cart_api(query, update, product_id, max_retries=3):
    """
        Adds a product to the cart using an async HTTP POST request.
        Retries up to `max_retries` times if there are network errors.
    """
    if not product_id:
        logging.warning(f"Product ID not found for '{product_id}'")
        return None

    user = update.effective_user
    telegram_id = user.id
    payload = {"id": int(product_id), "telegram_id": telegram_id}

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"http://web:8000/api/add-to-cart/", 
                    json=payload,
                    headers={"Accept": "application/json"}  # ask for JSON explicitly
                )
                if response.status_code in [404, 409] and response.json().get("error") == "Product not found":
                    await query.answer("Product not found or out of stock 😊.", show_alert=True)
                    await query.message.delete()
                    return None
                if response.status_code in [200, 201]:
                    print("post response: ", response.json())
                    return (response.json(), response.status_code)  # successful response
                
                response.raise_for_status()  # raises exception if status >=400

        except (httpx.RequestError, httpx.HTTPStatusError, ValueError, Exception) as e:
            logging.warning(f"Attempt {attempt} failed for '{product_id}': {e}")                
            
            if attempt == max_retries:
                logging.error(f"All {max_retries} attempts failed for '{product_id}'")
                return None
            
            # optional: wait before retrying
            await asyncio.sleep(1)

async def remove_cart_api(query, update, product_id, max_retries=3):
    """
        remove a product to the cart using an async HTTP POST request.
        Retries up to `max_retries` times if there are network errors.
    """
    if not product_id:
        logging.warning(f"Product ID not found for '{product_id}'")
        # print(f"user_data now {context.user_data.get('product_ids', {})}")
        return None

    user = update.effective_user
    telegram_id = user.id
    payload = {"id": int(product_id), "telegram_id": telegram_id}

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "http://web:8000/api/remove-cart/",
                    json=payload,
                    headers={"Accept": "application/json"}  # ask for JSON explicitly
                )
                
                if response.status_code == 404 and response.json().get("error") == "Product not found":
                    await query.answer("Product not found or out of stock 😊.", show_alert=True)
                    await query.message.delete()
                    return None
                
                if response.status_code == 200 and response.json().get("error") == "Cart item not found":
                    print("item is already zero", response.json())
                    await query.answer("Cart item not found 😊.", show_alert=True)
                    # await query.message.delete()
                    return None # item has quantity of zero(0)
                
                if response.status_code == 200:
                    print("post response: ", response.json())
                    return response.json()  # successful response

                response.raise_for_status()  # raises exception if status >=400

        except (httpx.RequestError, httpx.HTTPStatusError, ValueError, Exception) as e:
            logging.warning(f"Attempt {attempt} failed for '{product_id}': {e}")
            
            if attempt == max_retries:
                logging.error(f"All {max_retries} attempts failed for '{product_id}'")
                return None
            
            # optional: wait before retrying
            await asyncio.sleep(1)


            # # This checks if all product IDs from the cart actually exist in the database.
            # if len(product_map) != len(product_ids):
            #     return Response(
            #         {
            #             "error": "One or more products not found", 
            #             "remove_items": removed_cart_items,
            #          },
            #         status=status.HTTP_400_BAD_REQUEST
            #     )