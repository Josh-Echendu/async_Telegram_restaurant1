from FACEBOOK_BOT_API.handlers.start_handler import start
from FACEBOOK_BOT_API.handlers.order_handler import order_meal
from FACEBOOK_BOT_API.core.config import logger


async def echo(event, restaurant_data):

    message = event.get("message", {})
    text = message.get("text", "")

    user_id = event["sender"]["id"]

    logger.info(f"Echoing back to {user_id}: {text}")

    await start(event, restaurant_data)

    return 
