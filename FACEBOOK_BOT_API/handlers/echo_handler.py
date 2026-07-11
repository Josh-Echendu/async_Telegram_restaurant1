from handlers.start_handler import start_handler
from handlers.order_handler import order_meal
from core.config import logger


async def echo(event, restaurant_data):

    message = event.get("message", {})
    text = message.get("text", "")

    user_id = event["sender"]["id"]

    logger.info(f"Echoing back to {user_id}: {text}")

    if text == "🍽 Order Food":
        await order_meal(event, restaurant_data)

    else:
        await start_handler(event, restaurant_data)
        return