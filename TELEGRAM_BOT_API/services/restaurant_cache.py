import pytz
from datetime import datetime, timezone
from cachetools import TTLCache
from TELEGRAM_BOT_API.core.config import *
from TELEGRAM_BOT_API.core.config import _request_with_retry



# TTL: Time to Live, “How long something stays in memory before it disappears” i.e it last for 300 seconds (5 minutes)
cache = TTLCache(maxsize=2000, ttl=300)  # cache 2000 restaurants
lock = asyncio.Lock()
DRF_URL = "http://web:8000"


async def get_restaurant(rid: str):
    # 🔥 Check if cached data is from a different day
    if rid in cache:
        cached_data = cache[rid]
        cached_time = cache.get(f"{rid}_timestamp")
        
        if cached_time:
            try:
                # Step 1: Convert timezone string to pytz object
                restaurant_tz = pytz.timezone(cached_data.get('time_zone', 'Africa/Lagos'))
                
                # Step 2: Get current UTC time (London time)
                now_utc = datetime.now(timezone.utc)
                
                # Step 3: Convert UTC to restaurant's local time
                now_local = now_utc.astimezone(restaurant_tz)
                
                # Step 4: Get the day number from local time
                now_day = now_local.day
                
                # Step 5: Convert cached UTC timestamp to restaurant's local time
                cached_local = cached_time.astimezone(restaurant_tz)
                
                # Step 6: Get the day number from cached time
                cached_day = cached_local.day
                
                # If day changed, delete cache and fetch fresh
                if now_day != cached_day:
                    logger.info(f"Day changed for restaurant {rid}. Refreshing cache...")
                    del cache[rid]
                    del cache[f"{rid}_timestamp"]
                    
                    # Recursively fetch fresh data
                    return await get_restaurant(rid)
                
            except Exception as e:
                logger.exception(f"Error checking day change: {e}")
                # If error, assume cache is stale and delete it
                del cache[rid]
                if f"{rid}_timestamp" in cache:
                    del cache[f"{rid}_timestamp"]
                return await get_restaurant(rid)
        
        # Cache is valid (same day), return it
        return cached_data

    # 🔥 Not in cache or cache was cleared - fetch from DRF
    async with lock:
        response, success = await _request_with_retry(
            method="GET",
            url=f"{DRF_URL}/restaurants/internal/telegram/{rid}/",
            headers={"X-INTERNAL-API-KEY": INTERNAL_API_KEY}
        )

        # Network / 5xx failure
        if not success or response is None:
            logger.error(f"Failed to fetch restaurant {rid} — network/server error")
            return None

        # Parse response body
        try:
            data = response.json()
        except Exception:
            logger.exception(f"Failed to parse JSON for restaurant {rid}")
            return None

        # Success
        if response.status_code == 200:
            # Store in cache with timestamp (UTC time)
            cache[rid] = data
            cache[f"{rid}_timestamp"] = datetime.now(timezone.utc)

            logger.info(
                f"Fetched fresh data for restaurant {rid}: "
                f"open_time={data.get('open_time')}, "
                f"close_time={data.get('close_time')}, "
                f"is_closed={data.get('is_closed')}"
            )
            return data

        # 404 = restaurant not found
        if response.status_code == 404:
            logger.info(f"Restaurant {rid} not found in DRF")
            return None

        # Other 4xx — log and return
        logger.warning(
            f"DRF returned {response.status_code} for restaurant {rid}: "
            f"{data.get('error', 'unknown error')}"
        )
        return None
                


        