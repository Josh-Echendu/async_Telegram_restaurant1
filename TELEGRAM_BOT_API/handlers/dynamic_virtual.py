from core.config import *


async def generate_dynamic_virtual_account(update, max_retries=3):
    user_id = update.effective_user.id
    user_session = await get_user_session(user_id)
    restaurant_id = user_session['current_rid']

    if not restaurant_id or not user_id:
        await update.message.reply_text("Restaurant not found for your account.")
        return None

    url = f"http://web:8000/api/dva/"
    payload = {
        "restaurant_id": restaurant_id,
        "user_id": user_id 
    }

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers={"Content-Type": "application/json"}, json=payload)
                resp.raise_for_status()

                data = resp.json()
                print("data: ", data)

                if resp.status_code in (200, 201):
                    return data['data']

                logging.warning(f"Unexpected response {resp.status_code} → {data}")
                return None

        except httpx.HTTPStatusError as e:
            data = e.response.json()
            print("e-error: ", data)

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