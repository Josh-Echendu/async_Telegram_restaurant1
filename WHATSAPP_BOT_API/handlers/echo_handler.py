from .order_handler import order_meal
from .start_handler import start_handler
from WHATSAPP_BOT_API.core.config import *




async def echo(client: WhatsApp, msg: Message):
    text = msg.text or "No text content"

    user_id = msg.from_user.wa_id
    logger.info(f"Echoing back to {user_id}: {text}")

    if text == "🍽 Order Food":
        await order_meal(client, msg)

    else:
        await start_handler(client, msg)
        return
