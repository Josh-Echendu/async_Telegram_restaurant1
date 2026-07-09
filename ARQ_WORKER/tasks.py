from TELEGRAM_BOT_API.manager.bot_manager import get_bot
from TELEGRAM_BOT_API.core.config import get_user_session, save_user_session
from TELEGRAM_BOT_API.services.restaurant_cache import get_restaurant
from pywa_async import WhatsApp
import httpx
from TELEGRAM_BOT_API.PYOGRAM.main import setup_restaurant_telegram
from WHATSAPP_BOT_API.manager.wa_manager import get_wa_client
# from UNOFFICIAL_WHATSAPP_API.manager.wa_manager import get_wa_client
# from UNOFFICIAL_WHATSAPP_API.services.restaurant_cache import get_restaurant
import json
from COMMON.redis import redis_client
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot, Update
from COMMON.config import *
from COMMON.logger_config import *



async def handle_telegram_update(ctx, update_data: dict, restaurant: dict):
    logger.info(f"ctx:  {ctx}")
    
    # 🤖 1. Get the Bot Instance (Ideally from worker context 'ctx')
    bot_app = await get_bot(restaurant['bot_token'])
    logger.info(f"group bot app: {bot_app}")
    
    # 🔁 2. Reconstruct the Update Object
    # We pass the bot instance so the update knows how to 'reply'
    update = Update.de_json(update_data, bot_app.bot)

    # 🔥 ADD THIS DEBUG
    if update.message and update.message.text:
        logger.info(f"📨 Processing message: {update.message.text}")
        if update.message.text.startswith('/gencode'):
            logger.info("🔥 /gencode command detected!")

    # 🧠 3. Session Logic (Moved from FastAPI to Worker)
    if update.effective_user:
        user_id = update.effective_user.id
        logger.info(f"user_id group: {user_id}")
        user_session = await get_user_session(user_id)

        user_session.update({
            "current_rid": restaurant["rid"],
            "restaurant_name": restaurant["bot_name"],
            "business_type": restaurant["business_type"],
            "service_mode": restaurant["service_mode"],
            "max_tables": restaurant["max_tables"],
            "vendor_type": restaurant['vendor_type'],
            "time_zone": restaurant["time_zone"],
            "kitchen_chat_id": restaurant.get("kitchen_chat_id"),
        })


        await save_user_session(user_id, user_session)

    # ⚡ 4. Process the Handlers (start, echo, payment, etc.)
    await bot_app.process_update(update)



# ARQ_WORKER/tasks.py - Add this function
async def process_telegram_setup(ctx):
    """
    ARQ task that continuously processes telegram setup requests
    """    
    while True:
        _, data = await redis_client.brpop('telegram:setup')
        task = json.loads(data)
        
        restaurant_id = task['restaurant_id']
        restaurant_name = task['restaurant_name']
        bot_username = task['bot_username']
        owner_telegram_id = task['owner_telegram_id']
        service_mode = (task['service_mode'] or "").lower()
        owner_name = task.get('owner_name', 'Restaurant Owner')
        
        logger.info(f"📦 Processing Telegram setup for {restaurant_name}")
        
        # Check if already processed
        lock_key = f"telegram:setup:lock:{restaurant_id}"

        # acquire lock if it does not exist: setnx = "set if not exists"
        lock_acquired = await redis_client.setnx(lock_key, "processing")
        
        if not lock_acquired:
            logger.info(f"Setup for {restaurant_id} already in progress")
            continue

        # Set expiry to prevent deadlock
        await redis_client.expire(lock_key, 300)  # 5 minutes

        for attempt in range(3):
            try:
                result = await setup_restaurant_telegram(
                    restaurant_name=restaurant_name,
                    bot_username=bot_username,
                    owner_telegram_id=owner_telegram_id,
                    owner_name=owner_name,
                    service_mode=service_mode
                )
                
                # ✅ Success
                await redis_client.lpush(
                    "telegram:setup:results",
                    json.dumps({
                        "restaurant_id": restaurant_id,
                        "service_mode": service_mode,
                        "result": result,
                        "status": "success"
                    })
                )
                
                logger.info(f"✅ Setup complete for {restaurant_name}")
                await redis_client.delete(lock_key)
                break  # ← EXIT on success
                
            except Exception as e:
                logger.exception(f"❌ Setup attempt {attempt + 1} failed for {restaurant_name}: {e}")
                
                if attempt == 2:
                    # ❌ Failed after 3 attempts
                    await redis_client.lpush(
                        "telegram:setup:results",
                        json.dumps({
                            "restaurant_id": restaurant_id,
                            "status": "failed",
                            "error": str(e)
                        })
                    )

async def handle_whatsapp_update(ctx, update_data: dict, raw_payload: bytes, signature: str, restaurant: dict):
    """
    ARQ Task for handling WhatsApp updates.
    """
    logger.info(f"🚀 Processing WhatsApp update for RID: {restaurant['rid']}")

    # 🤖 1. Get the Pywa Client Instance
    # The client already has all handlers (message, buttons, etc.) attached
    wa_client = await get_wa_client(
        phone_id=restaurant["wa_phone_id"],
        token=restaurant["wa_token"],
    )

    # 🧠 2. Session Logic (Extract WAID from parsed JSON)
    try:
        # Webhook -> entry -> changes -> value
        value = update_data["entry"][0]["changes"][0]["value"]

        # Only process actual user messages
        if "messages" in value:
            user_info = value["messages"][0]
            wa_id = user_info["from"]  # e.g. 2349063938743

            logger.info(f"👤 User WAID: {wa_id}")

            # Fetch and update session
            user_session = await get_user_session(wa_id)
            user_session.update({
                "current_rid": restaurant["rid"],
                "phone_id": restaurant["wa_phone_id"],
                "restaurant_name": restaurant["bot_name"],
                "business_type": restaurant["business_type"],
                "service_mode": restaurant["service_mode"],
                "max_tables": restaurant["max_tables"],
                "time_zone": restaurant["time_zone"],
                "kitchen_chat_id": restaurant.get("kitchen_chat_id"),
            })

            await save_user_session(wa_id, user_session)

    except (KeyError, IndexError, Exception):
        # Status updates (sent, delivered, read) do not contain message data
        pass

    # ⚡ 3. Process the Webhook Through pywa_async
    # Since you created the client with server=None, use webhook_update_handler()
    try:
        await wa_client.webhook_update_handler(
            update=raw_payload,
            hmac_header=signature,
        )
        logger.info("✅ WhatsApp handlers executed successfully")
    except Exception:
        logger.exception("❌ Error in Pywa handler")




async def notify_telegram_payment_request(ctx,
    payment_key, customer_user_id, table, total,
    vat_amount, grand_total, payment_type, emoji,
    waiter_telegram_id, waiter_username, kitchen_chat_id,
    restaurant_id,
):
    """
    Sends a payment request notification to the restaurant's Telegram staff group.

    Multi-tenant safe:
        - Each restaurant gets its own cached Bot instance.
        - Bot cache key is unique per restaurant.
        - No Bot is recreated unless necessary.
    """

    try:
        restaurant = await get_restaurant(restaurant_id)

        if not restaurant:
            logger.error("Restaurant %s not found.", restaurant_id)
            return

        bot_token = restaurant.get("bot_token")

        if not bot_token:
            logger.error("Restaurant %s has no Telegram bot token.", restaurant_id)
            return

        bot = Bot(token=bot_token)
        await bot.initialize()


        logger.info("Using Telegram bot for restaurant %s", restaurant_id)

        keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton(
                    "✅ Confirm Payment",
                    callback_data=f"confirm-payment_{payment_key}_{customer_user_id}",
                )
            ]]
        )

        waiter_message = (
            f"💳 <b>PAYMENT REQUEST</b> 💳\n\n"
            f"Table: <code>{table}</code>\n"
            f"Subtotal: <b>₦{total:,}</b>\n"
            f"VAT(7.5%): <b>₦{vat_amount:,}</b>\n\n"
            f"Grand Total: <b>₦{grand_total:,}</b>\n\n"
            f"Method: {emoji} {payment_type.upper()}\n\n"
            f"👨‍💼 <i>Waiter, please proceed to Table {table}.</i>"
        )

        await bot.send_message(
            chat_id=kitchen_chat_id,
            text=waiter_message,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

        logger.info(
            "Payment notification sent | "
            "Restaurant=%s | Table=%s | Method=%s | Customer=%s",
            restaurant_id,
            table,
            payment_type,
            customer_user_id,
        )

    except Exception:
        logger.exception(
            "Failed to send Telegram payment notification "
            "for restaurant %s",
            restaurant_id,
        )
        raise

    finally:
        await bot.shutdown()

async def notify_whatsapp_payment_confirmed(
    ctx,
    customer_user_id: str,
    table: str,
    grand_total: int,
    restaurant_id: int,
):
    """
    ARQ task.

    Sends a payment confirmation message to a WhatsApp customer
    using the restaurant's own WhatsApp Business credentials.
    """

    try:
        # Get restaurant credentials
        restaurant = await get_restaurant(restaurant_id)

        if not restaurant:
            logger.error(
                "Restaurant not found. restaurant_id=%s",
                restaurant_id,
            )
            return

        wa_token = restaurant.get("wa_token")
        wa_phone_id = restaurant.get("wa_phone_id")

        if not wa_token or not wa_phone_id:
            logger.error(
                "Missing WhatsApp credentials for restaurant_id=%s",
                restaurant_id,
            )
            return

        session = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=30.0,
                read=30.0,
                write=30.0,
                pool=30.0,
            )
        )

        # Create a WhatsApp client for this restaurant
        client = WhatsApp(
            phone_id=wa_phone_id,
            token=wa_token,
            session=session
        )

        # Customer message
        message = (
            "✅ *Payment Confirmed!*\n\n"
            f"Table: *{table}*\n"
            f"Total: *₦{grand_total:,}*\n\n"
            "Thank you for dining with us! 🍽️"
        )

        # Send message
        await client.send_message(
            to=customer_user_id,
            text=message,
        )

        logger.info(
            "WhatsApp payment confirmation sent successfully | "
            "Restaurant=%s | Customer=%s | Table=%s",
            restaurant_id,
            customer_user_id,
            table,
        )

    except Exception:
        logger.exception(
            "Failed sending WhatsApp payment confirmation | "
            "Restaurant=%s | Customer=%s",
            restaurant_id,
            customer_user_id,
        )
        raise


# # ARQ_WORKER/tasks.py

# import json
# from COMMON.redis import redis_client
# from UNOFFICIAL_WHATSAPP_API.services.restaurant_cache import get_restaurant
# from UNOFFICIAL_WHATSAPP_API.handlers.echo_handler import echo
# from UNOFFICIAL_WHATSAPP_API.handlers.button_handler import handle_order_buttons

# async def process_whatsapp_messages(ctx):
#     print("🔥 process_whatsapp_messages started — waiting for messages...")
    
#     while True:
#         _, data = await redis_client.brpop('whatsapp:incoming')
#         msg = json.loads(data)

#         rid = msg['rid']
#         wa_id = msg['wa_id']
#         text = msg['text']
#         push_name = msg.get('push_name', '')
#         msg_type = msg.get('message_type', 'conversation')

#         print(f"📩 [{rid}] {wa_id} ({push_name}): {text[:100]}")

#         restaurant = await get_restaurant(rid)
#         if not restaurant:
#             print(f"❌ Restaurant not found: {rid}")
#             continue

#         result = None
#         if msg_type == 'buttons_response':
#             callback_data = msg.get('callback_data', '')
#             result = await handle_order_buttons(wa_id, callback_data, restaurant)
#         else:
#             result = await echo(wa_id, text, push_name, restaurant)

#         if result:
#             key = f'whatsapp:outbound:{rid}'
#             payload = json.dumps({
#                 'wa_id': wa_id,
#                 'text': result.get('text'),
#                 'buttons': result.get('buttons'),
#             })
#             print(f"📤 Pushing to {key}: {payload[:100]}")
#             await redis_client.lpush(key, payload)
#             print(f"📤 Push complete")



# from contextlib import asynccontextmanager
# BOTFATHER_LOCK_KEY = "lock:botfather"


# @asynccontextmanager # 👉 “This function is used like a controlled block (enter + exit safely)”
# async def botfather_lock(redis): # redis → your Redis client connection
    
#     # This creates a redis lock object i.e “A digital padlock stored inside Redis”
#     lock = redis.lock(
#         BOTFATHER_LOCK_KEY, # the key that all workers share/use, “Everyone who wants BotFather must request THIS SAME KEY”
#         timeout=300, # auto-release if worker using the lock dies
#         blocking_timeout=120  # wait max 2 min if busy
#     )

#     # 👉 “Did I successfully get the lock?” True → you got the lock (you can proceed), False → someone else i.e another worker already has it (you are blocked or rejected)
#     acquired  = await lock.acquire()

#     # is acquired is false
#     if not acquired:
#         raise Exception("Bot is busy")
    
#     try:
#         yield
#     finally:
#         await lock.release()


# async def create_telegram_bot(ctx, rid):

#     while True:
#         _, data = await redis_client.brpop('telegram:incoming')
#         task = json.loads(data)
#         print('task_msg: ', task)

#         async with botfather_lock(ctx["redis"]):
#             await process_telegram_task(ctx, task)


