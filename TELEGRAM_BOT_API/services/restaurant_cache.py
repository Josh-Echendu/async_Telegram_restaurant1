import httpx
import asyncio
import pytz
from datetime import datetime, timezone
from cachetools import TTLCache
from core.config import INTERNAL_API_KEY

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
                    print(f"Day changed for restaurant {rid}. Refreshing cache...")
                    del cache[rid]
                    del cache[f"{rid}_timestamp"]
                    
                    # Recursively fetch fresh data
                    return await get_restaurant(rid)
                
            except Exception as e:
                print(f"Error checking day change: {e}")
                # If error, assume cache is stale and delete it
                del cache[rid]
                if f"{rid}_timestamp" in cache:
                    del cache[f"{rid}_timestamp"]
                return await get_restaurant(rid)
        
        # Cache is valid (same day), return it
        return cached_data

    # 🔥 Not in cache or cache was cleared - fetch from DRF
    async with lock:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                res = await client.get(
                    f"{DRF_URL}/restaurants/internal/{rid}/",
                    headers={"X-INTERNAL-API-KEY": INTERNAL_API_KEY}
                )

                if res.status_code != 200:
                    print(f"DRF returned {res.status_code} for restaurant {rid}")
                    return None

                data = res.json()
                
                # Store in cache with timestamp (UTC time)
                cache[rid] = data
                
                # Get current UTC time (London time) for timestamp
                now_utc = datetime.now(timezone.utc)
                cache[f"{rid}_timestamp"] = now_utc
                
                print(f"Fetched fresh data for restaurant {rid}: open_time={data.get('open_time')}, close_time={data.get('close_time')}, is_closed={data.get('is_closed')}")
                
                return data

            except httpx.RequestError as e:
                print(f"DRF request failed for {rid}: {e}")
                return None
                


# import httpx
# import asyncio
# from cachetools import TTLCache
# from core.config import INTERNAL_API_KEY

# # TTL: Time to Live, “How long something stays in memory before it disappears” i.e it last for 60 seconds
# cache = TTLCache(maxsize=2000, ttl=300)  # cache 1000+ bots, it can store up to 2000 items, e.g 2000 restaurant (or bot tokens)
# # if exceeds 2000, the oldest data gets removed automatically: LRU eviction(Least Recently Used)

# lock = asyncio.Lock()
# DRF_URL = "http://web:8000"


# async def get_restaurant(rid: str):
#     if rid in cache:
#         return cache[rid]

#     async with lock:
#         async with httpx.AsyncClient(timeout=10.0) as client:
#             try:
#                 res = await client.get(
#                     f"{DRF_URL}/restaurants/internal/{rid}/",
#                     headers={
#                         "X-INTERNAL-API-KEY": INTERNAL_API_KEY
#                     }
#                 )

#                 if res.status_code != 200:
#                     return None

#                 data = res.json()
#                 cache[rid] = data
#                 return data

#             except httpx.RequestError as e:
#                 print(f"DRF request failed: {e}")
#                 return None

# 🧠 Meaning:

# Each cached item lives for 60 seconds

# After 60 seconds:

# it is automatically deleted
# next request will re-fetch from DRF
# 💡 Why this matters:

# Because restaurant data can change:

# bot enabled/disabled
# accepting orders ON/OFF
# secret token changes

# So we don’t want stale data forever.