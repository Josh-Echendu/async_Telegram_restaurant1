import redis
from django.conf import settings

redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True
)
print("redis_client: ", redis_client)

# Enable AOF from Python (optional)
redis_client.config_set('appendonly', 'yes')
redis_client.config_set('appendfsync', 'everysec')  # safe enough for ephemeral data
