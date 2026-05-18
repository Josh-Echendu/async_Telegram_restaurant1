import logging
import httpx
import asyncio
import pytz
from datetime import datetime, timezone
from cachetools import TTLCache
from WHATSAPP_BOT_API.core.config import INTERNAL_API_KEY


# TTL: Time to Live, “How long something stays in memory before it disappears” i.e it last for 300 seconds (5 minutes)
cache = TTLCache(maxsize=2000, ttl=300)  # cache 2000 restaurants
lock = asyncio.Lock()
DRF_URL = "http://web:8000"

logger = logging.getLogger(__name__)

async def get_restaurant(phone_id: str, max_retries = 3):
    # 🔥 Check if cached data is from a different day
    if phone_id in cache:
        cached_data = cache[f"res_{phone_id}"]
        cached_time = cache.get(f"{phone_id}_timestamp")
        
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
                    print(f"Day changed for restaurant {phone_id}. Refreshing cache...")
                    del cache[f"res_{phone_id}"]
                    del cache[f"{phone_id}_timestamp"]
                    
                    # Recursively fetch fresh data
                    return await get_restaurant(phone_id)
                
            except Exception as e:
                print(f"Error checking day change: {e}")
                # If error, assume cache is stale and delete it
                del cache[f"res_{phone_id}"]
                if f"{phone_id}_timestamp" in cache:
                    del cache[f"{phone_id}_timestamp"]
                return await get_restaurant(phone_id)
        
        # Cache is valid (same day), return it
        return cached_data

    # 🔥 Not in cache or cache was cleared - fetch from DRF
    async with lock:
        async with httpx.AsyncClient(timeout=10.0) as client:
            
            for attempt in range(max_retries + 1):  # Retry up to 3 times
                try:
                    res = await client.get(
                        f"{DRF_URL}/restaurants/internal/whatsapp/",
                        headers={"X-INTERNAL-API-KEY": INTERNAL_API_KEY, "X-PHONE-ID": phone_id}
                    )

                    if res.status_code != 200:
                        print(f"DRF returned {res.status_code} for restaurant {phone_id}")
                        return None

                    data = res.json()
                    
                    # Store in cache with timestamp (UTC time)
                    cache[f"res_{phone_id}"] = data
                    
                    # Get current UTC time (London time) for timestamp
                    now_utc = datetime.now(timezone.utc)
                    cache[f"{phone_id}_timestamp"] = now_utc
                    
                    print(f"Fetched fresh data for restaurant {phone_id}: open_time={data.get('open_time')}, close_time={data.get('close_time')}, is_closed={data.get('is_closed')}")
                    
                    return data

                except httpx.HTTPStatusError as e:
                    # Try to get error details
                    try:
                        error_data = e.response.json()
                        print(f"❌ User registration error: {error_data}")
                    except:
                        print(f"❌ HTTP error {e.response.status_code}: {e.response.text}")
                        logger.warning(f"❌ HTTP error {e.response.status_code}: {e.response.text}")
                    logging.warning(f"Attempt {attempt}/{max_retries} failed: {e}")
                    
                    if attempt == max_retries:
                        logging.error(f"All {max_retries} attempts failed")
                        return None
                        
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff: 2, 4, 8 seconds
                
                except httpx.RequestError as e:
                    print(f"🌐 Network error on attempt {attempt}: {e}")
                    logging.warning(f"Attempt {attempt} failed: {e}")
                    
                    if attempt == max_retries:
                        logging.error(f"All {max_retries} attempts failed")
                        return None
                        
                    await asyncio.sleep(2 ** attempt)

            return None
        
        
        
        
        
# import logging
# import httpx
# import asyncio
# import pytz
# from datetime import datetime, timezone
# from cachetools import TTLCache
# from WHATSAPP_BOT_API.core.config import INTERNAL_API_KEY


# # TTL: Time to Live, “How long something stays in memory before it disappears” i.e it last for 300 seconds (5 minutes)
# cache = TTLCache(maxsize=2000, ttl=300)  # cache 2000 restaurants
# lock = asyncio.Lock()
# DRF_URL = "http://web:8000"

# logger = logging.getLogger(__name__)

# async def get_restaurant(phone_id: str, max_retries = 3):
#     # 🔥 Check if cached data is from a different day
#     if phone_id in cache:
#         cached_data = cache[f"res_{phone_id}"]
#         cached_time = cache.get(f"{phone_id}_timestamp")
        
#         if cached_time:
#             try:
#                 # Step 1: Convert timezone string to pytz object
#                 restaurant_tz = pytz.timezone(cached_data.get('time_zone', 'Africa/Lagos'))
                
#                 # Step 2: Get current UTC time (London time)
#                 now_utc = datetime.now(timezone.utc)
                
#                 # Step 3: Convert UTC to restaurant's local time
#                 now_local = now_utc.astimezone(restaurant_tz)
                
#                 # Step 4: Get the day number from local time
#                 now_day = now_local.day
                
#                 # Step 5: Convert cached UTC timestamp to restaurant's local time
#                 cached_local = cached_time.astimezone(restaurant_tz)
                
#                 # Step 6: Get the day number from cached time
#                 cached_day = cached_local.day
                
#                 # If day changed, delete cache and fetch fresh
#                 if now_day != cached_day:
#                     print(f"Day changed for restaurant {phone_id}. Refreshing cache...")
#                     del cache[f"res_{phone_id}"]
#                     del cache[f"{phone_id}_timestamp"]
                    
#                     # Recursively fetch fresh data
#                     return await get_restaurant(phone_id)
                
#             except Exception as e:
#                 print(f"Error checking day change: {e}")
#                 # If error, assume cache is stale and delete it
#                 del cache[f"res_{phone_id}"]
#                 if f"{phone_id}_timestamp" in cache:
#                     del cache[f"{phone_id}_timestamp"]
#                 return await get_restaurant(phone_id)
        
#         # Cache is valid (same day), return it
#         return cached_data

#     # 🔥 Not in cache or cache was cleared - fetch from DRF
#     async with lock:
#         async with httpx.AsyncClient(timeout=10.0) as client:
            
#             for attempt in range(max_retries + 1):  # Retry up to 3 times
#                 try:
#                     res = await client.get(
#                         f"{DRF_URL}/restaurants/internal/whatsapp/",
#                         headers={"X-INTERNAL-API-KEY": INTERNAL_API_KEY, "X-PHONE-ID": phone_id}
#                     )

#                     if res.status_code != 200:
#                         print(f"DRF returned {res.status_code} for restaurant {phone_id}")
#                         return None

#                     data = res.json()
                    
#                     # Store in cache with timestamp (UTC time)
#                     cache[f"res_{phone_id}"] = data
                    
#                     # Get current UTC time (London time) for timestamp
#                     now_utc = datetime.now(timezone.utc)
#                     cache[f"{phone_id}_timestamp"] = now_utc
                    
#                     print(f"Fetched fresh data for restaurant {phone_id}: open_time={data.get('open_time')}, close_time={data.get('close_time')}, is_closed={data.get('is_closed')}")
                    
#                     return data

#                 except httpx.HTTPStatusError as e:
#                     # Try to get error details
#                     try:
#                         error_data = e.response.json()
#                         print(f"❌ User registration error: {error_data}")
#                     except:
#                         print(f"❌ HTTP error {e.response.status_code}: {e.response.text}")
#                         logger.warning(f"❌ HTTP error {e.response.status_code}: {e.response.text}")
#                     logging.warning(f"Attempt {attempt}/{max_retries} failed: {e}")
                    
#                     if attempt == max_retries:
#                         logging.error(f"All {max_retries} attempts failed")
#                         return None
                        
#                     await asyncio.sleep(2 ** attempt)  # Exponential backoff: 2, 4, 8 seconds
                
#                 except httpx.RequestError as e:
#                     print(f"🌐 Network error on attempt {attempt}: {e}")
#                     logging.warning(f"Attempt {attempt} failed: {e}")
                    
#                     if attempt == max_retries:
#                         logging.error(f"All {max_retries} attempts failed")
#                         return None
                        
#                     await asyncio.sleep(2 ** attempt)

#             return None