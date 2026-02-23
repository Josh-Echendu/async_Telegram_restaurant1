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

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    telegram_id = update.effective_user.id
    print("Button clicked data:", data)

    checkout_msg_id = await redis_client.get(f"user:{telegram_id}:checkout_message_id")
    send_to_kitchen_id = await redis_client.get(f"user:{telegram_id}:send_to_kitchen_id")

    # 🔥 If checkout is active and user clicks ANY inline button except allowed ones
    if checkout_msg_id and data not in ("order_to_kitchen", "cancel_order"):
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=query.message.chat.id,
                message_id=checkout_msg_id,
                reply_markup=None
            )
        except: pass
        finally: await redis_client.delete(f"user:{telegram_id}:checkout_message_id")

    if send_to_kitchen_id and data not in ("order_more_items", "pay_now", 'track_orders'):
        try:
            await context.bot.edit_message_text(
                text='🍽️ Order sent to the kitchen! 🎉',
                chat_id=query.message.chat.id,
                message_id=send_to_kitchen_id,
                reply_markup=None
            )
        except: pass
        finally: await redis_client.delete(f"user:{telegram_id}:send_to_kitchen_id")

    # if next page button is clicked
    if data == 'next_page':

        # show meal images for previous page
        meal_type = await redis_client.get(f"user:{telegram_id}:meal_type")
        if not meal_type:
            return 

        # appending data to a dict : increment 'rice_page' key by 1
        key = f"user:{telegram_id}:{meal_type}_page"
        page = int(await redis_client.get(key) or 0) + 1
        print("next page: ", page)
        await redis_client.set(key, page)

        # Delete previous buttons
        await query.message.delete()

        await Extract_message_img_ids(update, context)

        await meal_images(update, context)

    # if back page button is clicked
    elif data == 'back_page':

        # show meal images for previous page
        meal_type = await redis_client.get(f"user:{telegram_id}:meal_type")
        
        if not meal_type:
            return 

        # decrement 'rice_page' key by 1 but not below 0        
        key = f"user:{telegram_id}:{meal_type}_page"
        page = max(int(await redis_client.get(key) or 0) - 1, 0)
        await redis_client.set(key, page)
        print("back page: ", page)


        # Delete previous buttons
        await query.message.delete()
        await Extract_message_img_ids(update, context)

        await meal_images(update, context)

    # if add button is clicked
    elif data.startswith('add_'):

        # Extract product name
        product_id = int(data.replace('add_', ''))

        # increment cart by 1
        response, code = await add_to_cart_api(query, update, product_id)
        print("response data: ", response)
        print("response code: ", code)
        if not response:
            return 
        
        # provide alert feedback
        await query.answer("Added 🛒💚", show_alert=False)

        qty = response.get("quantity", 0)
        product_name = response.get("product_name")
        price_per_item = response.get("price", 0)
        total_price = response.get("total_price", 0)

        await update_qty_button(context, query, product_name, qty, price_per_item, total_price)

    # if remove button is clicked
    elif data.startswith('remove_'):

        # Extract product name
        product_id = int(data.replace('remove_', ''))

        # decrement cart by 1
        response = await remove_cart_api(query, update, product_id)
        if not response:
            return
        
        # provide alert feedback
        await query.answer("Removed 🛍️➖", show_alert=False)

        qty = response.get("quantity", 0)
        product_name = response.get("product_name")
        price_per_item = response.get("price", 0)
        total_price = response.get("total_price", 0)

        await update_qty_button(context, query, product_name, qty, price_per_item, total_price)
        print("Remove button clicked: ", context.user_data)

    elif data == 'pay_now':
        await redis_client.delete(f"user:{telegram_id}:send_to_kitchen_id")

        # Get us the orders ther customer has made
        order_batches_data = await api_get_user_order_batches(update)

        # if no orders made by the user
        if order_batches_data == []:
            await query.answer("You have not made any order Today 😊.", show_alert=True)
            await query.message.delete()
            return
        
        await redis_client.delete(f"user:{telegram_id}:send_to_kitchen_id")

        copy_order_batches_data = order_batches_data.copy()
        await pay_now(update, context, copy_order_batches_data, query)

    elif data == 'cancel_order':
        await query.answer("❌ Order cancelled")
        await redis_client.delete(f"user:{telegram_id}:checkout_message_id")

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
    
    elif data == "order_to_kitchen":
        await query.edit_message_reply_markup(reply_markup=None)
        await send_to_kitchen(update, context, query)

    elif data == "order_more_items":
        await redis_client.delete(f"user:{telegram_id}:send_to_kitchen_id")
        await query.edit_message_text("🍽️ Order sent to the kitchen! 🎉")

        # Extract message chat.id bcos update.message for a callback_query is None
        await order_meal_by_chat_id(query.message.chat.id, context)

    elif data == "track_orders":
        await redis_client.delete(f"user:{telegram_id}:send_to_kitchen_id")

        # Get us the orders ther customer has made
        order_batches_data = await api_get_user_order_batches(update)

        # if no orders made by the user
        if order_batches_data is None:
            query.answer("You have not made any order Today 😊.", show_alert=True)
            return
        
        await query.edit_message_text("🍽️ Order sent to the kitchen! 🎉")
        await start(update, context, Track_orders=True)

    elif data == 'bank_transfer':
        # Define the new buttons you want to show
        keyboard = [
            [InlineKeyboardButton("Back ⬅️", callback_data='back_to_payment_menu')]
        ]
        # Apply the change
        await query.edit_message_reply_markup(reply_markup=None)
        
        account_info = "Bank: XYZ Bank\nAccount Number: 1234567890\nAccount Name: ABC Restaurant"
        await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"📝 Account Details \n\n Please make your payment to the following account:\n\n{account_info}\n\nThank you for your order!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
        
    elif data == "back_to_payment_menu":
        await query.message.delete()
        main_keyboard = [
            [
                InlineKeyboardButton("🛒💳 Card Transfer", callback_data="card_payment"),
                InlineKeyboardButton("🏦💸 Bank Transfer", callback_data="bank_transfer"),
            ],
            [
                InlineKeyboardButton(f"[ ❌ Cancel ]", callback_data="cancel_order"),
            ]
        ]
        await query.edit_message_reply_markup(InlineKeyboardMarkup(main_keyboard))

    elif data.startswith("processing_"):
        status = 'processing'
        batch_id = data.replace("processing_", "")
        updated = await update_batch_table(batch_id, status, query)
        if updated:
            # Show only delivered button after successful processing
            keyboard = [InlineKeyboardButton("📦✅ Delivered", callback_data=f'delivered_{batch_id}')]
            await query.edit_message_reply_markup(InlineKeyboardMarkup([keyboard]))

    elif data.startswith("delivered_"):
        status = 'delivered'
        batch_id = data.replace("delivered_", "")
        updated = await update_batch_table(batch_id, status, query)
        if updated:
            # Remove buttons completely after delivered
            await query.edit_message_reply_markup(reply_markup=None)


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