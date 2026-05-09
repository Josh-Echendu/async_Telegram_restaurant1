import logging
from core.config import get_user_session, save_user_session
import logging
from pywa import WhatsApp
from manager.wa_manager import get_wa_client # Your manager we built earlier
from core.config import get_user_session, save_user_session

logger = logging.getLogger(__name__)

async def handle_whatsapp_update(ctx, update_data: dict, restaurant: dict):
    """
    ARQ Task for handling WhatsApp updates.
    """
    print(f"🚀 Processing WhatsApp update for RID: {restaurant['rid']}")
    
    # 🤖 1. Get the Pywa Client Instance
    # The manager already has the handlers (start, echo, buttons) attached
    wa_client = await get_wa_client(
        phone_id=restaurant['wa_phone_id'], 
        token=restaurant['wa_token']
    )
    
    # 🧠 2. Session Logic (Extract WAID from raw data)
    # In WhatsApp, the user ID is their phone number (WAID)
    try:
        # Navigate the Meta JSON to find the sender's ID
        # Webhook -> entry -> changes -> value -> messages or statuses
        value = update_data['entry'][0]['changes'][0]['value']
        
        if 'messages' in value:
            user_info = value['messages'][0]
            wa_id = user_info['from'] # The 234... phone number
            
            print(f"👤 User WAID: {wa_id}")
            
            # Fetch and update session
            user_session = await get_user_session(wa_id)
            user_session.update({
                "current_rid": restaurant["rid"],
                "restaurant_name": restaurant["bot_name"],
                "business_type": restaurant["business_type"],
                "service_mode": restaurant["service_mode"],
                "max_tables": restaurant["max_tables"],
                "time_zone": restaurant["time_zone"],
            })

            # Check for table selection in button callbacks
            if 'button' in user_info and user_info['button']['payload'].startswith("table_"):
                table_number = user_info['button']['payload'].replace("table_", "")
                user_session["table_number"] = table_number

            await save_user_session(wa_id, user_session)

    except (KeyError, IndexError):
        # Statues (sent/delivered/read receipts) don't have user session logic
        pass

    # ⚡ 3. Process the Handlers
    # This triggers your start_handler, echo, or handle_order_buttons
    try:
        wa_client.handler(update_data)
        print("✅ WhatsApp handlers executed successfully")
    except Exception as e:
        logger.error(f"❌ Error in Pywa handler: {e}")