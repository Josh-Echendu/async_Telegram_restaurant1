import asyncio
# CHANGE: Use pywa_async instead of pywa
from pywa_async import WhatsApp, filters, handlers
from pywa_async.types import Message, CallbackButton
from WHATSAPP_BOT_API.handlers.echo_handler import echo
from WHATSAPP_BOT_API.handlers.button_handler import handle_order_buttons
from WHATSAPP_BOT_API.core.config import *

wa_clients = {}
lock = asyncio.Lock()

# Fix your handler registration in get_wa_client()

async def get_wa_client(phone_id: str, token: str):
    async with lock:
        if phone_id not in wa_clients:

            client = WhatsApp(
                phone_id=phone_id,
                token=token,
                server=None,
                verify_token=VERIFY_TOKEN,
                app_secret=APP_SECRET,
            )

            # ✅ IMPORTANT:
            # Do NOT wrap filters in a list.
            # Wrong: filters=[filters.text]
            # Right: filters=filters.text
            @client.on_message(filters=filters.text)
            async def handle_text(client: WhatsApp, msg: Message):
                await echo(client, msg)

            # ✅ IMPORTANT:
            # Do NOT wrap filters in a list.
            # Wrong: filters=[filters.startswith("order_")]
            # Right: filters=filters.startswith("order_")
            @client.on_callback_button(filters=filters.startswith("order_"))
            async def handle_callback(client: WhatsApp, btn: CallbackButton):
                await handle_order_buttons(client, btn)

            wa_clients[phone_id] = client

        return wa_clients[phone_id]