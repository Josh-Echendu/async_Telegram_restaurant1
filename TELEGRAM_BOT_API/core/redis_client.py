import os
import redis.asyncio as redis
from dotenv import load_dotenv
from pathlib import Path

# Load .env file
load_dotenv(Path(__file__).resolve().parent / ".env")

# Get REDIS_URL from environment
REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    raise ValueError("REDIS_URL is not set in environment")

print("Connecting to Redis:", REDIS_URL)

redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True
)


async def init_redis():
    await redis_client.config_set('appendonly', 'yes')
    await redis_client.config_set('appendfsync', 'everysec')



# PS C:\Windows\system32> docker exec -it acbadbab19f5 redis-cli CONFIG GET appendonly
# 1) "appendonly"
# 2) "yes"
# PS C:\Windows\system32> docker exec -it redis_cache redis-cli CONFIG GET dir
# 1) "dir"
# 2) "/data"
# PS C:\Windows\system32> docker exec -it redis_cache ls /data
# appendonlydir  dump.rdb
# PS C:\Windows\system32>
