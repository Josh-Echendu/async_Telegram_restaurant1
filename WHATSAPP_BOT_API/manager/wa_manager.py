import asyncio
from pywa import WhatsApp
from pywa.types import Message, CallbackButton
from handlers.start_handler import start_handler
from pywa import filters
from handlers.echo_handler import echo
from handlers.button_handler import handle_order_buttons


# This replaces your 'bots' dict
wa_clients = {}
lock = asyncio.Lock()


async def get_wa_client(phone_id: str, token: str):

    async with lock:
        if phone_id not in wa_clients:

            client = WhatsApp(
                phone_id=phone_id,
                token=token,
                server=None 
            )

            # 1. REGISTER TEXT/REPLY BUTTON HANDLER (The "Echo")
            # We use is_reply_button filter so it only handles the 3 main buttons
            client.add_handlers(
                Message(
                    handler=echo, 
                    filters=[filters.text.is_reply_button]
                )
            )

            # 2. REGISTER CALLBACK BUTTON HANDLER (The "Order Flow")
            # This handles the "order_" callbacks from your payment/service logic
            client.add_handlers(
                CallbackButton(
                    handler=handle_order_buttons,
                    filters=[filters.callback_data.startswith("order_")]
                )
            )

            # 3. REGISTER THE START HANDLER (Catch-all for new users)
            # This handles everything else that isn't a button click
            client.add_handlers(
                Message(
                    handler=start_handler,
                    filters=[~filters.text.is_reply_button]
                )
            )

            wa_clients[phone_id] = client
            print(f"✅ Pywa client {phone_id} initialized with handlers.")
            print("wa_client: ", wa_clients[phone_id])
        
        return wa_clients[phone_id]