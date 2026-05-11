# handlers/order_handler.py - CONVERTED TO PYWA
from WHATSAPP_BOT_API.core.config import *
from pywa import WhatsApp
from .start_handler import logger_whatsapp
from pywa.types import Button, Message



async def order_meal(client: WhatsApp, msg: Message):
    await logger_whatsapp(client, msg)
    
    # 1. Use .wa_id for session and identification
    user_id = msg.from_user.wa_id
    user_session = await get_user_session(user_id)
    
    # Use .get() with defaults to prevent KeyErrors if session is empty
    service_mode = user_session.get('service_mode').lower()
    business_type = user_session.get('business_type').lower()

    buttons = []
    
    if business_type == "vendor":
        buttons.append(Button(title="🚚 Delivery", callback_data="order_delivery"))
    else:
        # Check for Dine-in
        if service_mode in ["dine_in", "both"]:
            buttons.append(Button(title="🍽️ Dine-in", callback_data="order_dine_in"))
        
        # Check for Delivery
        if service_mode in ["delivery", "both"]:
            buttons.append(Button(title="🚚 Delivery", callback_data="order_delivery"))
    
    # 2. Use .reply() helper — it's faster and cleaner than client.send_message
    await msg.reply(
        body="How would you like to order today? 🍔",
        buttons=buttons
    )