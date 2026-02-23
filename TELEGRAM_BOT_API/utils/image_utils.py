# utils/image_utils.py - EXACT COPY FROM ORIGINAL FILE
from config import *
import asyncio
import httpx
import logging
from decimal import Decimal
from io import BytesIO


# NGROK_URL = "https://5877902f6c35.ngrok-free.app"  # replace with your ngrok URL
PAGE_SIZE = 3  # must match DRF max_limit


# services:
#   web:
#     build: .
#     command: python manage.py runserver 0.0.0.0:8000
#     depends_on:
#       - redis

#   redis:
#     image: redis:7-alpine
#     command: redis-server --appendonly yes
#     ports:
#       - "6379:6379"

#   celery:
#     build: .

##    This means: --concurrency=5 → each worker can handle 5 tasks at once. by default celery is --concurrency=8
#     command: celery -A restaurant_api worker -l info --concurrency=5
#     depends_on:
#       - redis


# --scale celery=5 → you now have 5 workers.
# docker-compose up --scale celery=5

# You now have 5 worker containers, each with concurrency=5 → 25 tasks can run at the same time.
# Each container gets a unique name like:
# yourproject_celery_1
# yourproject_celery_2
# yourproject_celery_3
# yourproject_celery_4
# yourproject_celery_5

NGROK_URL="https://3748-197-211-63-122.ngrok-free.app"
async def meal_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_chat.id
    
    meal_type = await redis_client.get(f"user:{telegram_id}:meal_type")
    meal_type = meal_type if meal_type else None

    page = await redis_client.get(f"user:{telegram_id}:{meal_type}_page")
    page = int(page) if page else 0

    offset = page * PAGE_SIZE

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"http://web:8000/api/products/{meal_type}/{telegram_id}/?limit={PAGE_SIZE}&offset={offset}",
                headers={"Accept": "application/json"}  # ask for JSON explicitly
            )
            response.raise_for_status()

            # Fetch the JSON response
            resp_json = response.json()
            # print("Fetched products:", resp_json)

            # Extract the list of products
            product_list = resp_json.get('products', [])
            # print("product_list:", product_list)

            # Total count for pagination
            total_count = resp_json.get('count', 0)
            print("total_count:", total_count)

        except Exception as e:
            logging.warning(f"Failed to fetch products: {e}")
            return

    # send product images
    for p in product_list:
        product_id = p.get('id')
        product_name = p.get('title')
        price_per_item = Decimal(p.get('price'))
        qty = p.get("cart_quantity")
        image_url = p.get('image').replace("http://web:8000", NGROK_URL)
        print("image_url: ", image_url)
        
        total_price = price_per_item * qty
        caption = f"{product_name} - ₦{Decimal(price_per_item):,} \nQty: {qty} | Total: ₦{Decimal(total_price):,}"
        
        keyboard = [
            [
                InlineKeyboardButton("🛒💚🛍️", callback_data=f"add_{product_id}"),
                InlineKeyboardButton(f"⚖️ {qty}", callback_data="noop"),
                InlineKeyboardButton("⛔🛍️", callback_data=f"remove_{product_id}"),
            ]
        ]
        send_msg = await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=image_url,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        # user:12345:cart
        # user:12345:session
        # user:12345:images

        # Key: user:123456
        # Value: [111, 112, 113, 114]
        await store_message_id(update, context, send_msg.message_id)


    # navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Back", callback_data="back_page"))
    if offset + PAGE_SIZE < total_count:
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data="next_page"))

    if nav_buttons:
        back_next_msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Use buttons to navigate:",
            reply_markup=InlineKeyboardMarkup([nav_buttons])
        )
        await store_message_id(update, context, back_next_msg.message_id)


async def store_message_id(update: Update, context: ContextTypes.DEFAULT_TYPE, message_id: int):
    telegram_id = update.effective_user.id
    key = f"user:{telegram_id}:messages"
    await redis_client.rpush(key, message_id)

async def Extract_message_img_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
        Give me all the message IDs stored in this Redis list.
        old_messages = redis_client.lrange(key, 0, -1)
        
        lrange = get items from a Redis list

        0 = start from first element

        -1 = go to the last element
    """
    telegram_id = update.effective_user.id

    key = f"user:{telegram_id}:messages"
    old_ids = await redis_client.lrange(key, 0, -1)
    print("old_ids: ", old_ids)

    if old_ids:
        await asyncio.gather(
            *[
                delete_image(context, telegram_id, msg_id)
                for msg_id in old_ids
            ],
            return_exceptions=True
        )

        # delete the key and value
        await redis_client.delete(key)


async def delete_image(context: ContextTypes.DEFAULT_TYPE, telegram_id, message_id):
    try:
        await context.bot.delete_message(
            chat_id=telegram_id,
            message_id=int(message_id)
        )
    except Exception as e:
        logging.error(f"Error deleting message {message_id}: {e}")
        pass




# key = f"user:{telegram_id}:image_messages"

# # Remove oldest message first
# oldest = redis_client.lpop(key)

# if oldest:
#     try:
#         await context.bot.delete_message(
#             chat_id=telegram_id,
#             message_id=int(oldest)
#         )
#     except:
#         pass

# # Now send new message
# send_msg = await context.bot.send_photo(...)

# # Store new message id
# redis_client.rpush(key, send_msg.message_id)





# async def meal_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     meal_type = context.user_data.get('meal_type', None)
#     page = context.user_data.get(f'{meal_type}_page', 0)
#     offset = page * PAGE_SIZE

#     async with httpx.AsyncClient(timeout=30.0) as client:
#         try:
#             response = await client.get(
#                 f"http://127.0.0.1:8000/api/products/{meal_type}/?limit={PAGE_SIZE}&offset={offset}",
#                 headers={"Accept": "application/json"}  # ask for JSON explicitly
#             )
#             response.raise_for_status()

#             # Fetch the JSON response
#             resp_json = response.json()
#             print("Fetched products:", resp_json)

#             # Extract the list of products
#             products_list = resp_json.get('products', [])
#             print("products_list:", products_list)

#             # Extract the product_ids mapping
#             product_ids = resp_json.get('product_ids', {})
#             context.user_data['product_ids'] = product_ids
#             print("product_ids mapping:", product_ids)
#             print("product_ids mapping:", context.user_data.get('product_ids', {}))

#             # Total count for pagination
#             total_count = resp_json.get('count', 0)
#             print("total_count:", total_count)

#         except Exception as e:
#             logging.warning(f"Failed to fetch products: {e}")
#             return

#     # send product images
#     for p in products_list:
#         product_name = p.get('title')
#         price_per_item = Decimal(p.get('price'))
#         qty = p.get("cart_quantity")
#         image_url = p.get('image').replace("http://127.0.0.1:8000", NGROK_URL)
        
#         total_price = price_per_item * qty
#         caption = f"{product_name} - ₦{Decimal(price_per_item):,} \nQty: {qty} | Total: ₦{Decimal(total_price):,}"
        
#         keyboard = [
#             [
#                 InlineKeyboardButton("🛒💚🛍️", callback_data=f"add_{product_name}"),
#                 InlineKeyboardButton(f"⚖️ {qty}", callback_data="noop"),
#                 InlineKeyboardButton("⛔🛍️", callback_data=f"remove_{product_name}"),
#             ]
#         ]

#         send_msg = await context.bot.send_photo(
#             chat_id=update.effective_chat.id,
#             photo=image_url,
#             caption=caption,
#             reply_markup=InlineKeyboardMarkup(keyboard)
#         )
#         context.user_data.setdefault(f'{meal_type}_image_messages', []).append(send_msg.message_id)