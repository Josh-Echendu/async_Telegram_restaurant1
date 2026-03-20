from config import *
    

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
    key = f"restaurant_id:{user_id}"
    restaurant_id = await redis_client.get(key)

    if not restaurant_id:
        await update.message.reply_text("Restaurant ID not found for your account.")
        return None

    url = f"http://web:8000/api/user_batch_list/{user_id}/{restaurant_id}/"

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers={"Content-Type": "application/json"})
                resp.raise_for_status()

                data = resp.json()
                print("data: ", data)
                if resp.status_code in (200, 201):
                    return data

                logging.warning(f"Unexpected response {resp.status_code} → {data}")
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
                    logging.error("Invalid JSON returned for 404 response")
                    return None
            logging.warning(f"Attempt {attempt} failed: {e}")

        except (httpx.RequestError, ValueError, Exception) as e:
            logging.warning(f"Attempt {attempt} failed: {e}")

        if attempt < max_retries:
            await asyncio.sleep(1)

    logging.error(f"All {max_retries} attempts failed to get order batches from DB.")
    return None