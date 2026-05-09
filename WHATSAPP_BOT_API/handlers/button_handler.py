import platform
from .order_handler import choose_table, EMOJI_NUMBERS
from pywa import WhatsApp

from services.restaurant_cache import get_restaurant
from core.config import get_user_session, save_user_session

from pywa import filters # Standard way to access filters in pywa

from pywa.types import CallbackButton, WhatsApp, Message
from pywa.types import Button, ListMessage, Section, Row, CallbackButton
from core.config import *

import pytz
from datetime import datetime, timezone, time





# Using .startswith is safer than matching the whole string for scalability
@wa.on_callback_button(filters.callback_data.startswith("order_"))
async def handle_order_buttons(client: WhatsApp, btn: CallbackButton):
    # btn.data is the property to access the callback data in PyWa
    data = btn.data 
    
    if data == "order_dine_in":
        user_session = await get_user_session(btn.from_user.wa_id)
        user_session['user_service_mode'] = 'dine_in'
        await save_user_session(btn.from_user.wa_id, user_session)
        
        # Call the next function in your flow
        await choose_table(client, btn)
    
    elif data == "order_delivery":
        restaurant_data = await get_user_session(btn.from_user.wa_id)
        business_type = restaurant_data['business_type']
        service_mode = restaurant_data['service_mode']
        
        # Delivery Logic Check
        if service_mode.lower() in ['delivery', 'both']:
            is_available, message = await is_delivery_available_whatsapp(btn)
            
            if not is_available:
                await btn.reply_text(text=message)
                return 
        
        # Valid: Proceed to update session
        # ✅ Only reach here if:
        # - Business is VENDOR, OR
        # - Restaurant AND delivery is available
        user_session = await get_user_session(btn.from_user.wa_id)
        user_session['user_service_mode'] = 'delivery'
        user_session.pop('table_number', None)
        
        await save_user_session(btn.from_user.wa_id, user_session)
        
        # Call the menu
        await menu_keyboard_whatsapp(client, btn)


# Helper functions you need to adapt:
async def is_delivery_available_whatsapp(update: CallbackButton | Message):
    """
    Checks if a restaurant is open for delivery based on its timezone.
    Accepts either a CallbackButton or Message from pywa.
    """
    # Use .wa_id for consistency with your registration/session flow
    user_id = update.from_user.wa_id
    user_session = await get_user_session(user_id)
    
    restaurant_id = user_session.get('current_rid')
    if not restaurant_id:
        return False, "Session expired. Please restart the order."

    # Fetch fresh data
    restaurant_data = await get_restaurant(restaurant_id)
    
    if not restaurant_data:
        return False, "Restaurant data unavailable. Please try again."
    
    # Extract data from dictionary
    time_zone = restaurant_data.get('time_zone', 'Africa/Lagos')
    open_time_str = restaurant_data.get('open_time')
    close_time_str = restaurant_data.get('close_time')
    is_closed = restaurant_data.get('is_closed', False)

    try:
        restaurant_tz = pytz.timezone(time_zone)
    except Exception:
        restaurant_tz = pytz.timezone('Africa/Lagos')

    # Get current time in the restaurant's local timezone
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(restaurant_tz)
    current_time = now_local.time()

    # Check manual closure
    if is_closed:
        return False, "🙏 We're closed for delivery today. See you tomorrow!"

    # Check if hours are defined
    if not open_time_str or not close_time_str:
        return False, "🙏 Delivery hours are not set for this location yet."

    try:
        # Standard isoformat expects 'HH:MM:SS' or 'HH:MM'
        open_time = time.fromisoformat(open_time_str)
        close_time = time.fromisoformat(close_time_str)
    except Exception:
        return False, "System error calculating opening hours."

    # Logic for normal vs. overnight hours
    if open_time <= close_time:
        # Day shift (e.g., 08:00 - 20:00)
        is_open = open_time <= current_time <= close_time
    else:
        # Night shift (e.g., 22:00 - 04:00)
        is_open = current_time >= open_time or current_time <= close_time

    if not is_open:
        open_12hr = open_time.strftime('%I:%M %p')
        close_12hr = close_time.strftime('%I:%M %p')
        return False, f"🚚 Delivery available from {open_12hr} to {close_12hr}."

    return True, "Delivery available"




async def menu_keyboard_whatsapp(client: WhatsApp, clb: CallbackButton | Message):
    # Use .wa_id for consistency
    user_id = clb.from_user.wa_id
    user_session = await get_user_session(user_id)
    
    restaurant_id = user_session.get('current_rid')
    user_service_mode = user_session.get('user_service_mode')
    table_number = user_session.get('table_number')
    platform = "whatsapp"  # or "telegram", depending on the platform

    WEB_APP_URL = await whatsapp_init_session(
        restaurant_id=restaurant_id,
        user_id=user_id, 
        platform=platform, 
        user_service_mode=user_service_mode, 
        table_number=table_number
    )

    # WhatsApp Reality: You can't "Edit" the previous message.
    # We send a NEW message with the link.
    
    body_text = (
        "🍟 *Check out our Menu!* 🍟\n\n"
        "Click the link below to view our meals and place your order:\n"
        f"{WEB_APP_URL}"
    )

    # Since WhatsApp automatically generates a preview for URLs, 
    # this will look like a "Card" in the chat.
    await clb.reply_text(
        text=body_text,
        preview_url=True
    )

async def whatsapp_init_session(restaurant_id: str, user_id: str, platform: str, user_service_mode: str = None, table_number: str = None):
    # This is where you can initialize any session variables if needed
    
    payload = {
        "restaurant_id": restaurant_id,
        "user_id": user_id,
        "mode": user_service_mode,
        "table_number": table_number,
        "platform": platform
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"http://web:8000/userauths/whatsapp/init_session/",
            json=payload,
        )

        data = response.json()
        print("data: ", data)
        return data.get('url')



