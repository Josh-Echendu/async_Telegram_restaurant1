import httpx
import asyncio
from cachetools import TTLCache
from config import INTERNAL_API_KEY

# TTL: Time to Live, “How long something stays in memory before it disappears” i.e it last for 60 seconds
cache = TTLCache(maxsize=2000, ttl=6000)  # cache 1000+ bots, it can store up to 2000 items, e.g 2000 restaurant (or bot tokens)
# if exceeds 2000, the oldest data gets removed automatically: LRU eviction(Least Recently Used)

lock = asyncio.Lock()
DRF_URL = "http://web:8000"


async def get_restaurant(rid: str):
    if rid in cache:
        return cache[rid]

    async with lock:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                res = await client.get(
                    f"{DRF_URL}/restaurants/internal/{rid}/",
                    headers={
                        "X-INTERNAL-API-KEY": INTERNAL_API_KEY
                    }
                )

                if res.status_code != 200:
                    return None

                data = res.json()
                cache[rid] = data
                return data

            except httpx.RequestError as e:
                print(f"DRF request failed: {e}")
                return None

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