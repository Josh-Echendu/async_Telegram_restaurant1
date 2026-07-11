import logging
import httpx
import asyncio
import pytz
from datetime import datetime, timezone
from cachetools import TTLCache
from core.config import *
from core.config import _request_with_retry



# TTL: Time to Live, "How long something stays in memory before it disappears" 
# i.e it lasts for 300 seconds (5 minutes)
cache = TTLCache(maxsize=2000, ttl=300)  # cache 2000 restaurants
lock = asyncio.Lock()
DRF_URL = "http://web:8000"


async def get_restaurant(page_id: str):
    cache_key = f"res_{page_id}"
    timestamp_key = f"{page_id}_timestamp"
    
    # 🔥 Check if cached data is from a different day
    if cache_key in cache:
        cached_data = cache[cache_key]
        cached_time = cache.get(timestamp_key)
        
        if cached_time:
            try:
                # Ensure cached_time is timezone-aware
                if cached_time.tzinfo is None:
                    cached_time = pytz.UTC.localize(cached_time)
                
                # Step 1: Convert timezone string to pytz object
                restaurant_tz = pytz.timezone(cached_data.get('time_zone', 'Africa/Lagos'))
                
                # Step 2: Get current UTC time
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
                    logger.info(f"Day changed for restaurant {page_id}. Refreshing cache...")
                    del cache[cache_key]
                    if timestamp_key in cache:
                        del cache[timestamp_key]
                    
                    # Recursively fetch fresh data
                    return await get_restaurant(page_id)
                
            except Exception as e:
                logger.exception(f"Error checking day change: {e}")
                
                # If error, assume cache is stale and delete it
                if cache_key in cache:
                    del cache[cache_key]
                if timestamp_key in cache:
                    del cache[timestamp_key]
                return await get_restaurant(page_id)
        
        # Cache is valid (same day), return it
        return cached_data
    
    # 🔥 Not in cache or cache was cleared - fetch from DRF
    async with lock:
        try:
            url = f"{DRF_URL}/restaurants/internal/facebook/"
            headers = {
                "X-INTERNAL-API-KEY": INTERNAL_API_KEY, 
                "X-PAGE-ID": page_id
            }
            res, success = await _request_with_retry(
                method="GET",
                url=url,
                headers=headers
            )
            
            if not success:
                logger.info(f"DRF returned {res.status_code} for restaurant with a pageID of {page_id}")
                return None
            
            data = res.json().get('data')
            
            # Store in cache with timestamp (UTC time)
            cache[cache_key] = data
            
            # Get current UTC time (London time) for timestamp
            now_utc = datetime.now(timezone.utc)
            cache[timestamp_key] = now_utc
            
            logger.info(
                f"Fetched fresh data for restaurant {page_id}: "
                f"open_time={data.get('open_time')}, "
                f"close_time={data.get('close_time')}, "
                f"is_closed={data.get('is_closed')}"
            )
            return data
        
        except Exception as e:
            logger.exception(f"Failed to get restaurant data for page={page_id}")
            return None