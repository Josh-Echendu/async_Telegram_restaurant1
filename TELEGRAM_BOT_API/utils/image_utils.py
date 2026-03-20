# utils/image_utils.py - EXACT COPY FROM ORIGINAL FILE
from config import *
import asyncio
import httpx
import logging
from decimal import Decimal
from io import BytesIO


# services:
#   web:
#     build: .
#     command: python manage.py runserver 0.0.0.0:8000
#     depends_on:
#       - redis

#   redis:
#     image: redis:7-alpine
#     command: redis-server --appendonly yes
#     ports:
#       - "6379:6379"

#   celery:
#     build: .

##    This means: --concurrency=5 → each worker can handle 5 tasks at once. by default celery is --concurrency=8
#     command: celery -A restaurant_api worker -l info --concurrency=5
#     depends_on:
#       - redis


# --scale celery=5 → you now have 5 workers.
# docker-compose up --scale celery=5

# You now have 5 worker containers, each with concurrency=5 → 25 tasks can run at the same time.
# Each container gets a unique name like:
# yourproject_celery_1
# yourproject_celery_2
# yourproject_celery_3
# yourproject_celery_4
# yourproject_celery_5


async def store_message_id(update: Update, context: ContextTypes.DEFAULT_TYPE, message_id: int):
    telegram_id = update.effective_user.id
    key = f"user:{telegram_id}:messages"
    await redis_client.rpush(key, message_id)

async def Extract_message_img_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
        Give me all the message IDs stored in this Redis list.
        old_messages = redis_client.lrange(key, 0, -1)
        
        lrange = get items from a Redis list

        0 = start from first element

        -1 = go to the last element
    """
    telegram_id = update.effective_user.id

    key = f"user:{telegram_id}:messages"
    old_ids = await redis_client.lrange(key, 0, -1)
    print("old_ids: ", old_ids)

    if old_ids:
        await asyncio.gather(
            *[
                delete_image(context, telegram_id, msg_id)
                for msg_id in old_ids
            ],
            return_exceptions=True
        )

        # delete the key and value
        await redis_client.delete(key)


async def delete_image(context: ContextTypes.DEFAULT_TYPE, telegram_id, message_id):
    try:
        await context.bot.delete_message(
            chat_id=telegram_id,
            message_id=int(message_id)
        )
    except Exception as e:
        logging.error(f"Error deleting message {message_id}: {e}")
        pass
