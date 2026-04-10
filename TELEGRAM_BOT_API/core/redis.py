import os
from fastapi import Path
import redis.asyncio as redis
from arq import create_pool # for ARQ worker pool (async), 
from arq.connections import RedisSettings
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / ".env")

REDIS_URL = os.getenv("REDIS_URL")

# 🔥 ADD THIS LINE (THIS IS YOUR FIX)
_arq_pool = None

# redis_client: Used for sessions, caching, user data
# async def get_arq_redis(): Used for enqueueing jobs, background processing


# 🔹 Main Redis client (sessions, cache)
redis_client = redis.Redis.from_url( # 👉 This creates a Redis connection using REDIS_URL.
    REDIS_URL,
    decode_responses=True
)

# 🔹 ARQ settings (shared config): 👉 means “connect to Redis using the DNS name (redis) provided by Docker”
redis_settings = RedisSettings.from_dsn(REDIS_URL) # “How should ARQ connect to Redis?”

# 🔹 ARQ pool (for enqueueing jobs)
async def get_arq_redis():
    global _arq_pool
    if _arq_pool is None:

        # 👉 create_pool: Creates a connection pool to Redis, Used specifically for background jobs
        _arq_pool = await create_pool(redis_settings)


    return _arq_pool

# 👉 how to pass your existing redis_client into ARQ jobs (ctx)
# 👉 or how to reuse sessions inside workers (very powerful for PTB bots)
# 👉 how ctx works inside ARQ (very powerful)
# 👉 or how to run multiple workers per restaurant (enterprise scaling)