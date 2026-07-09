from TELEGRAM_BOT_API.core.config import *
from TELEGRAM_BOT_API.core.config import get_user_session, save_user_session
import json
from typing import Optional, Dict, Any



async def waiter_generate_code(update: Update, context: ContextTypes.DEFAULT_TYPE):

    """
    Waiter command: /gencode 5
    Generates OTP for table 5
    """
    # ✅ FIX: Allow only in private chats
    if update.effective_chat.type not in ['private']:
        await update.message.reply_text("❌ This command only works in Private chats with the bot.")
        return

    waiter = update.effective_user
    args = context.args

    waiter_id = waiter.id
    
    user_session = await get_user_session(waiter_id)
    business_type = user_session.get('business_type')    
    logger.info("business_type: %s", business_type)

    if business_type and business_type.lower() != 'restaurant':
        await update.message.reply_text("❌ This command is only for restaurants.")
        return

    # ✅ FIX: Get restaurant_id from session
    restaurant_id = user_session.get('current_rid')
    if not restaurant_id:
        await update.message.reply_text("❌ Restaurant not found. Please contact support.")
        return

    # ✅ FIX: Get kitchen_chat_id properly
    # Option 1: From user session
    kitchen_chat_id = user_session.get('kitchen_chat_id')
    
    # Option 2: Fetch from database if not in session
    if not kitchen_chat_id:
        # You might need to fetch restaurant data from DB
        # For now, we'll use a default or fail gracefully
        await update.message.reply_text("❌ Kitchen group not found. Please contact support.")
        return

    try:
        member = await context.bot.get_chat_member(kitchen_chat_id, waiter_id)
        is_authorized = member.status in ['creator', 'administrator', 'member']
    except Exception as e:
        logger.exception(f"Error occurred while fetching chat member: {e}")
        is_authorized = False

    if not is_authorized:
        await update.message.reply_text(
            "❌ You are not authorized to generate OTP.\n"
            "Please contact the restaurant owner to be added to the staff group."
        )
        return

    if not args:
        await update.message.reply_text("❌ Usage: /gencode <table_number>\nExample: /gencode 5")
        return
    
    table_number = args[0]

    if not table_number.isdigit():
        await update.message.reply_text("❌ Table number must be a number.")
        return 
    
    chat_id = update.effective_chat.id

    payload_kitchen = {
        "waiter_telegram_id": waiter.id,
        "waiter_username": waiter.username or waiter.first_name,
        "restaurant_id": restaurant_id,
        "table_number": int(table_number),
    }
    logger.info("payload_kitchen: %s", payload_kitchen)
    
    max_retries = 3
    async with httpx.AsyncClient(timeout=20.0) as client:
        for attempt in range(1, max_retries + 1):        
            try:    
                response = await client.post(
                    "http://web:8000/restaurants/dine-in/generate-otp/",
                    json=payload_kitchen,
                )

                if response.status_code == 201:
                    data = response.json()
                    otp_code = data.get('otp_code')
                    formatted_otp = f"{otp_code[:2]}-{otp_code[2:4]}-{otp_code[4:6]}"
                    expires_in = data.get('expires_in', 60)

                    await update.message.reply_text(
                        f"✅ OTP generated for Table {table_number}\n\n"
                        f"Code: `{formatted_otp}`\n"
                        f"Valid for {expires_in} seconds\n\n"
                        f"Tell this code to the customer.",
                        parse_mode='Markdown'
                    )
                    return

            except httpx.HTTPStatusError as e:
                logger.exception(f"HTTP error on attempt {attempt}: {e.response.status_code} - {e.response.text}")
                if attempt == max_retries:
                    await update.message.reply_text(f"❌ Failed to generate OTP after {max_retries} attempts.")
                else:
                    await asyncio.sleep(1)
                    
            except (httpx.RequestError, ValueError) as e:
                logger.exception(f"Request error on attempt {attempt}: {e}")
                if attempt == max_retries:
                    await update.message.reply_text("❌ Network error. Please try again.")
                else:
                    await asyncio.sleep(1)


async def update_batch_table(batch_id, status, restaurant_id, query=None, max_retries=3):
    
    payload = {"batch_id": batch_id, "status": status, "restaurant_id": restaurant_id}

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.patch(
                    "http://web:8000/api/update_batch_status/restaurant/",
                    headers={"Accept": "application/json"},
                    json=payload
                )

                # ✅ Blocked duplicate
                if response.status_code == 409:
                    logger.warning(f"Blocked duplicate transition for batch: {batch_id}")
                    if query:
                        await query.message.delete()
                    # Mark in Redis to prevent repeated UI clicks
                    await redis_client.set(f"batch:{batch_id}:duplicate_click", 1, ex=60)
                    return None

                response.raise_for_status()
                logger.info(f"Batch {batch_id} updated successfully: {response.json()}")
                return response.json()

        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
            logger.exception(f"Attempt {attempt}/{max_retries} failed for batch {batch_id}: {e}")
            if attempt == max_retries:
                logger.error(f"All retries failed for batch {batch_id}")
                return None
            await asyncio.sleep(1)
            
            
async def api_get_user_order_batches(update, max_retries=3):
    platform = "telegram"

    # 🔍 Get session_id from Redis
    try:
        user_id = update.effective_user.id

        session_data = json.loads(
            await redis_client.get(f"telegram_dine_user_session:{user_id}")
        )
        session_id = session_data.get("session_id")
        restaurant_id = session_data.get("restaurant_id")

    except Exception:
        session_id = None

    if not session_id:
        await update.message.reply_text(
            "❌ <b>No Active Session Found</b>\n\n"
            "🛒 You don't have an active order session.\n"
            "🍽️ Please add some items to your cart first.",
            parse_mode="HTML",
        )
        return None

    url = f"http://web:8000/api/user_batch_list/{session_id}/{restaurant_id}/{platform}/"

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers={"Content-Type": "application/json", "X-INTERNAL-API-KEY": INTERNAL_API_KEY})

                resp.raise_for_status()

                data = resp.json()
                if resp.status_code in (200, 201):
                    return data

                logger.warning(f"Unexpected response {resp.status_code} → {data}")
                return None

        except httpx.HTTPStatusError as e:

            # Handle 404 separately
            if e.response.status_code == 404:
                try:
                    data = e.response.json()
                    if data.get("error", "").lower() == "session not found":
                        await update.message.reply_text(
                            "You have no active session. Please order some items."
                        )
                        return None
                except ValueError:
                    logger.exception("Invalid JSON returned for 404 response")
                    return None
            logger.warning(f"Attempt {attempt} failed: {e}")

        except (httpx.RequestError, ValueError, Exception) as e:
            logger.exception(f"Attempt {attempt} failed: {e}")

        if attempt < max_retries:
            await asyncio.sleep(1)

    logger.error(f"All {max_retries} attempts failed to get order batches from DB.")
    return None



async def handle_pos_cash_payment(update, payment_type, max_retries=3):
    """
    Handles POS or Cash payment selection by the customer.
    """
    user_id = update.effective_user.id
    user_session = await get_user_session(user_id)
    restaurant_id = user_session.get('current_rid')
    
    logger.info(f"🏪 Restaurant ID: {restaurant_id}")
    logger.info(f"💳 Payment Type: {payment_type}")

    # 🔍 Get session_id from Redis
    try:
        session_data = json.loads(await redis_client.get(f"telegram_dine_user_session:{user_id}"))
        logger.info("handle session data: %s", session_data)
        session_id = session_data.get('session_id')
    except:
        session_id = None
    
    if not session_id:
        # ✅ FIX: Use the correct method based on update type
        if update.message:
            await update.message.reply_text(
                "❌ <b>No Active Session Found</b>\n\n"
                "🛒 You don't have an active order session.\n"
                "🍽️ Please add some items to your cart first.",
                parse_mode="HTML"
            )
        else:
            await update.callback_query.answer("No active session found.", show_alert=True)
        return None

    payload = {
        "session_id": session_id,
        "payment_type": payment_type
    }

    url = f"http://web:8000/payments/api/handle-payment-selection/"
    
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers={"Content-Type": "application/json"}, json=payload)
                resp.raise_for_status()
                
                data = resp.json()                
                return data.get('data')
                
        except Exception as e:
            logger.exception(f"⚠️ Attempt {attempt} failed: {e}")
            if attempt == max_retries:
                if update.message:
                    await update.message.reply_text(
                        "❌ <b>Payment Request Failed</b>\n\n"
                        "We couldn't process your payment request.\n"
                        "🔄 Please try again or contact support.",
                        parse_mode="HTML"
                    )
                else:
                    await update.callback_query.answer("Payment request failed. Please try again.", show_alert=True)
                return None
                
        if attempt < max_retries:
            await asyncio.sleep(1)
    
    return None




async def save_pos_and_cash_payment(update, payment_method, session_id: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
    """
    Sends a request to mark a session as paid (POS or Cash).
    
    Args:
        update: Telegram update object
        session_id: The session ID to mark as paid
        max_retries: Number of retry attempts
    
    Returns:
        Response data from the backend or None if failed
    """
    
    if not session_id:
        logger.error("❌ Invalid session_id: None or empty")
        return None

    payload = {
        "session_id": session_id,
        "waiter_in_charge": update.effective_user.id,
        "payment_method": payment_method
    }
    
    url = "http://web:8000/payments/api/save-pos-cash/"
    
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    url, 
                    headers={"Content-Type": "application/json"}, 
                    json=payload
                )
                resp.raise_for_status()
                
                data = resp.json()
                logger.info(f"✅ Payment confirmed: {data}")
                
                return data.get('data')
                
        except Exception as e:
            logger.error(f"❌ Attempt {attempt} failed: {e}")
            
            if attempt == max_retries:
                return None
                
            await asyncio.sleep(2 ** attempt)
    
    return None