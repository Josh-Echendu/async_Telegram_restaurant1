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
import asyncio
import socket



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
STREAM_NAME = "telegram:setup"
GROUP_NAME = "telegram_workers"
MAX_ATTEMPTS = 2

# ------------------------------------------------------------------
# Process one stream message
# ------------------------------------------------------------------

async def process_stream_message(message_id: str, task: dict):

    restaurant_id = task["restaurant_id"]
    restaurant_name = task["restaurant_name"]
    bot_username = task["bot_username"]
    owner_telegram_id = task["owner_telegram_id"]
    owner_name = task.get("owner_name", "Restaurant Owner")
    service_mode = (task.get("service_mode") or "").lower()

    lock_key = f"telegram:setup:lock:{restaurant_id}"
    
    # FIRST: Check if lock exists
    lock_exists = await redis_client.exists(lock_key)

    if lock_exists:
        logger.warning("Lock exists for %s, checking if it's stale", restaurant_id)
        
        # Delete stale lock
        await redis_client.delete(lock_key)
        logger.info("Deleted stale lock for %s", restaurant_id)
        # Continue processing - DON'T increment attempt count yet!

    # Track attempts for this specific message
    attempt_key = f"telegram:setup:attempts:{message_id}"
    attempt_count = await redis_client.get(attempt_key)
    
    if attempt_count is None:
        attempt_count = 1
    else:
        attempt_count = int(attempt_count) + 1
    
    # Store attempt count with 1 hour expiry
    await redis_client.setex(attempt_key, 3600, attempt_count)

    # If exceeded max attempts, give up and cleanup
    if attempt_count > MAX_ATTEMPTS:
        logger.warning(
            "Task exceeded max attempts (%s) for restaurant %s, giving up",
            MAX_ATTEMPTS,
            restaurant_name
        )
        
        # XACK to remove from pending list
        # await redis_client.xack(STREAM_NAME, GROUP_NAME, message_id)
        await redis_client.xdel(STREAM_NAME, message_id)  # Delete from Redis entirely

        
        # Push failure result
        await redis_client.lpush(
            "telegram:setup:results",
            json.dumps({
                "restaurant_id": restaurant_id,
                "status": "failed",
                "error": f"Max retries exceeded ({MAX_ATTEMPTS} attempts)",
                "attempts": attempt_count,
                "restaurant_name": restaurant_name
            })
        )
        
        # Clean up attempt counter
        await redis_client.delete(attempt_key)
        
        logger.info(
            "Cleaned up task after %s failures for restaurant %s",
            MAX_ATTEMPTS,
            restaurant_name
        )
        return

    logger.info(
        "Processing Telegram setup | Restaurant=%s | Attempt=%s/%s",
        restaurant_name,
        attempt_count,
        MAX_ATTEMPTS
    )

    lock_key = f"telegram:setup:lock:{restaurant_id}"

    lock_acquired = await redis_client.setnx(lock_key, "processing")

    if not lock_acquired:
        logger.info(
            "Setup already running for restaurant %s",
            restaurant_id,
        )
        return

    await redis_client.expire(lock_key, 20)

    try:

        # Internal retry loop (3 attempts per worker pickup)
        for retry_attempt in range(3):

            try:

                logger.info(
                    "Processing Telegram setup | Restaurant=%s | Retry=%s/3",
                    restaurant_name,
                    retry_attempt + 1,
                )

                result = await setup_restaurant_telegram(
                    restaurant_name=restaurant_name,
                    bot_username=bot_username,
                    owner_telegram_id=owner_telegram_id,
                    owner_name=owner_name,
                    service_mode=service_mode,
                )

                # --------------------------------------------------
                # SUCCESS
                # --------------------------------------------------

                # XACK = "I finished this job."
                await redis_client.xack(STREAM_NAME, GROUP_NAME, message_id)

                # Push success result
                await redis_client.lpush(
                    "telegram:setup:results",
                    json.dumps(
                        {
                            "restaurant_id": restaurant_id,
                            "status": "success",
                            "service_mode": service_mode,
                            "result": result,
                            "attempts": attempt_count,
                        }
                    ),
                )

                # Clean up attempt counter on success
                await redis_client.delete(attempt_key)

                logger.info(
                    "Telegram setup completed | Restaurant=%s",
                    restaurant_name,
                )

                return

            except Exception as exc:

                logger.exception(
                    "Retry %s/3 failed for %s",
                    retry_attempt + 1,
                    restaurant_name,
                )

                if retry_attempt == 2:
                    # All 3 internal retries failed
                    # Update attempt count for next worker pickup
                    await redis_client.setex(attempt_key, 3600, attempt_count)
                    
                    logger.warning(
                        "All 3 retries exhausted for restaurant %s, will be picked up by another worker",
                        restaurant_name
                    )
                    
                    # DO NOT XACK.
                    # Leave it pending so XAUTOCLAIM can recover it.

    finally:

        await redis_client.delete(lock_key)


# ------------------------------------------------------------------
# Main Worker
# ------------------------------------------------------------------

async def process_telegram_setup(ctx):

    consumer_name = socket.gethostname()

    logger.info("Starting Telegram Setup Worker: %s", consumer_name)

    while True:

        try:

            # =====================================================
            # STEP 1
            # Recover abandoned jobs first
            # =====================================================

            recovered_data = await redis_client.xautoclaim(
                STREAM_NAME,
                GROUP_NAME,  # This is the team of workers
                consumer_name,  # Which worker is taking ownership?
                min_idle_time=60000,  # Redis will only recover jobs that have been idle for at least 60 seconds.
                start_id="0-0",  # "Start scanning from the beginning of the pending list."
                count=1,  # Recover at most 1 abandoned job at a time.
            )
            
            next_start = recovered_data[0]
            recovered_messages = recovered_data[1]  # List of (message_id, fields_dict) tuples
            deleted = recovered_data[2]

            if recovered_messages:

                logger.info(
                    "Recovered %s abandoned Telegram setup jobs",
                    len(recovered_messages),
                )

                for message_id, task in recovered_messages:

                    logger.info("Processing recovered message: %s", message_id)

                    await process_stream_message(message_id, task)
                    await asyncio.sleep(1)  # Small gap between recovered jobs

                continue

            # =====================================================
            # STEP 2
            # Wait for NEW jobs
            # =====================================================

            messages = await redis_client.xreadgroup(
                groupname=GROUP_NAME,
                consumername=consumer_name,
                streams={STREAM_NAME: ">"},  # ">" means: Give me messages that have NEVER been delivered to ANY worker.
                count=1,  # one task per worker
                block=5000,  # wait for 5 seconds
            )
            print("messages from xreadgroup: ", messages)

            if not messages:
                continue

            # Process each message
            for stream_name, stream_messages in messages:

                for message_id, task in stream_messages:

                    logger.info("Processing new message: %s", message_id)
                    await process_stream_message(message_id, task)

        except Exception as e:

            logger.exception(
                "Telegram Stream Worker crashed: %s",
                str(e)
            )

            await asyncio.sleep(5)



# ✅ Success → XACK
# ❌ Temporary failure (network timeout, Telegram API down, worker crash) → leave it pending so it can be retried or reclaimed.
# ❌ Permanent failure (bad data that will never succeed) → either move it to a dead-letter stream and XACK, or record it as permanently failed, depending on your system's design.

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
            raise

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
            raise

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


