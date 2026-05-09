import json
from COMMON.redis import redis_client

async def get_user_session(user_id):
    data = await redis_client.get(f"user:{user_id}")
    return json.loads(data) if data else {}

async def save_user_session(user_id, session):
    await redis_client.set(
        f"user:{user_id}",
        json.dumps(session)
    )
    return session