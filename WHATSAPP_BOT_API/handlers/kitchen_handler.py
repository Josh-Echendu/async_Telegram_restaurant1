from WHATSAPP_BOT_API.core.config import *
import httpx

            
async def api_get_user_order_batches(client, msg, max_retries=3):
    user_id = msg.author.phone
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
                        await client.send_message(
                            to=msg.from_user,
                            text="You have no active session. Please order some items."
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