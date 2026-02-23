from config import *
    

async def update_batch_table(batch_id, status, query=None, max_retries=3):
    payload = {"batch_id": batch_id, "status": status}

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.patch(
                    "http://web:8000/api/update_batch_status/",
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
    user = update.effective_user
    telegram_id = user.id

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                
                resp = await client.get(
                    f"http://web:8000/api/user_batch_list/{telegram_id}/",
                    headers={"Content-Type": "application/json"},
                )
                # ✅ Safely parse JSON only if possible
                data = resp.json()

                if resp.status_code in (200, 201):
                    return data

                # Optional fallback
                logging.warning(f"Unexpected response: {resp.status_code} → {data}")
                return None

        except (httpx.RequestError, httpx.HTTPStatusError, ValueError, Exception) as e:

            logging.warning(f"Attempt {attempt} failed to get order batches from DB: {e}")

            if attempt == max_retries:
                logging.error(f"All {max_retries} attempts failed to get order batches from DB.")
                return None

            await asyncio.sleep(1)
