from WHATSAPP_BOT_API.handlers.echo_handler import echo
from WHATSAPP_BOT_API.handlers.button_handler import handle_order_buttons
from WHATSAPP_BOT_API.core.config import *


wa_clients = {}
lock = asyncio.Lock()

# Fix your handler registration in get_wa_client()

async def get_wa_client(phone_id: str, token: str):

    async with lock:
        if phone_id not in wa_clients:

            session = httpx.AsyncClient(
                timeout=httpx.Timeout(
                connect=30.0,
                read=30.0,
                write=30.0,
                pool=30.0,
            ))

            client = WhatsApp(
                phone_id=phone_id,
                token=token,
                server=None,
                verify_token=VERIFY_TOKEN,
                app_secret=APP_SECRET,
                session=session
            )

            @client.on_message(filters=filters.text)
            async def handle_text(client: WhatsApp, msg: Message):
                await echo(client, msg)

            callback_filter = (
                filters.startswith("order_")
                | filters.startswith("pay")
                | filters.startswith("checkout")
                | filters.startswith("browse_products")
                | filters.startswith("bank_transfer")
            )
            @client.on_callback_button(filters=callback_filter)
            async def handle_callback(client: WhatsApp, btn: CallbackButton):
                await handle_order_buttons(client, btn)

            wa_clients[phone_id] = client

        return wa_clients[phone_id]