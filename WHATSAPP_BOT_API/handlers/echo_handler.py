from .order_handler import order_meal
from .start_handler import start_handler
from WHATSAPP_BOT_API.core.config import *
from WHATSAPP_BOT_API.core.config import _request_with_retry





async def echo(client: WhatsApp, msg: Message):
    text = msg.text or "No text content"

    user_id = msg.from_user.wa_id
    logger.info(f"Echoing back to {user_id}: {text}")

    await start_handler(client, msg)
    return
