from TELEGRAM_BOT_API.core.config import *
from TELEGRAM_BOT_API.core.config import get_user_session, save_user_session




async def waiter_generate_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Jesusssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss")
    """
    Waiter command: /gencode 5
    Generates OTP for table 5
    """
    # Only allow in groups, not private chats
    if update.effective_chat.type == 'private':
        await update.message.reply_text("This command only works in group chats.")
        return

    waiter = update.effective_user
    args = context.args
    print("waiter: ", waiter)

    if not args:
        await update.message.reply_text("Usage: /gencode <table_number>")
        return
    
    table_number = args[0]
    max_retries=3

    # ✅ FIXED: isdigit() not isdit()
    if not table_number.isdigit():
        await update.message.reply_text("Table number must be a number.")
        return 
    
    # ✅ FIXED: effective_chat.id not effect_chat.id
    chat_id = update.effective_chat.id
    print(f"Chat ID: {chat_id}")
    waiter_id = waiter.id
    print("waiter_id: ", waiter_id)
    
    # ✅ FIXED: Add await and use correct function name
    # You need to implement get_restaurant_id_from_chat() or store in context.chat_data
    user_session = await get_user_session(waiter_id)  # Or use a different key for groups
    print("user_session kichen handler: ", user_session)
    
    restaurant_id = user_session.get('current_rid')

    payload_kitchen = {
        "waiter_telegram_id": waiter.id,
        "waiter_username": waiter.username or waiter.first_name,
        "restaurant_id": restaurant_id,
        "table_number": int(table_number),
    }
    print("payload_kitchen: ", payload_kitchen)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(1, max_retries + 1):        
            try:    
                response = await client.post(
                    "http://web:8000/restaurants/dine-in/generate-otp/",
                    json=payload_kitchen,
                )

                print(f"Response status: {response.status_code}")
                print(f"Response body: {response.text}")

                if response.status_code == 201:

                    data = response.json()
                    otp_code = data.get('otp_code')
                    formatted_otp = f"{otp_code[:2]}-{otp_code[2:4]}-{otp_code[4:6]}"  # "12-34-56"

                    # Send confirmation to group
                    await update.message.reply_text(
                        f"✅ OTP generated for Table {table_number}\n\n"
                        f"Code: `{formatted_otp}`\n"
                        f"Valid for 1 minutes\n\n"
                        f"Tell this code to the customer.",
                        parse_mode='Markdown'
                    )
                    return  # Success, exit function
                    

            except httpx.HTTPStatusError as e:
                print(f"HTTP error on attempt {attempt}: {e.response.status_code} - {e.response.text}")
                if attempt == max_retries:
                    await update.message.reply_text(f"❌ Failed to generate OTP after {max_retries} attempts.")
                else:
                    await asyncio.sleep(1)
                    
            except (httpx.RequestError, ValueError) as e:
                print(f"Request error on attempt {attempt}: {e}")
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
                    logging.warning(f"Blocked duplicate transition for batch {batch_id}")
                    if query:
                        await query.message.delete()
                    # Mark in Redis to prevent repeated UI clicks
                    await redis_client.set(f"batch:{batch_id}:duplicate_click", 1, ex=60)
                    return None

                response.raise_for_status()
                logging.info(f"Batch {batch_id} updated successfully: {response.json()}")
                return response.json()

        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
            logging.warning(f"Attempt {attempt}/{max_retries} failed for batch {batch_id}: {e}")
            if attempt == max_retries:
                logging.error(f"All retries failed for batch {batch_id}")
                return None
            await asyncio.sleep(1)
            
async def api_get_user_order_batches(update, max_retries=3):
    user_id = update.effective_user.id
    user_session = await get_user_session(user_id)
    restaurant_id = user_session['current_rid']
    print("restuarant 123: ", restaurant_id)

    url = f"http://web:8000/api/user_batch_list/{user_id}/{restaurant_id}/"

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers={"Content-Type": "application/json"})
                resp.raise_for_status()

                data = resp.json()
                # print("data: ", data)
                if resp.status_code in (200, 201):
                    return data

                logging.warning(f"Unexpected response {resp.status_code} → {data}")
                return None

        except httpx.HTTPStatusError as e:
            # Handle 404 separately
            if e.response.status_code == 404:
                try:
                    data = e.response.json()
                    print("datawe: ", data)
                    if data.get("error", "").lower() == "session not found":
                        await update.message.reply_text(
                            "You have no active session. Please order some items."
                        )
                        return None
                except ValueError:
                    logging.error("Invalid JSON returned for 404 response")
                    return None
            logging.warning(f"Attempt {attempt} failed: {e}")

        except (httpx.RequestError, ValueError, Exception) as e:
            logging.warning(f"Attempt {attempt} failed: {e}")

        if attempt < max_retries:
            await asyncio.sleep(1)

    logging.error(f"All {max_retries} attempts failed to get order batches from DB.")
    return None