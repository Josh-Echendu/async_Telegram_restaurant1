import os
import redis.asyncio as redis
from arq import create_pool
from arq.connections import RedisSettings
from dotenv import load_dotenv
from pathlib import Path


load_dotenv(Path(__file__).resolve().parent.parent / ".env")


REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    raise ValueError("REDIS_URL missing")

# 🔹 normal redis (sessions, cache)
redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True
)

# 🔹 ARQ pool (background jobs)
redis_settings = RedisSettings.from_dsn(REDIS_URL)

_arq_pool = None

async def get_arq_redis():
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_pool(redis_settings)
    return _arq_pool