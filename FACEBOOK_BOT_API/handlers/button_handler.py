from .utils_handler import send_button_message
from FACEBOOK_BOT_API.core.config import _request_with_retry
import pytz
from datetime import datetime, timezone, time
from FACEBOOK_BOT_API.core.config import logger
from .order_handler import order_meal




async def handle_postback(event, restaurant):

    payload = event["postback"]["payload"]
    user_id = event["sender"]["id"]

    if payload == "order_delivery":
        business_type = restaurant['business_type']
        service_mode = restaurant['service_mode']
        
        # Delivery Logic Check
        if service_mode.lower() in ['delivery', 'both']:
            is_available, message = await is_delivery_available_whatsapp(user_id, restaurant)
            
            if not is_available:
                await send_button_message(
                    recipient_id=user_id,
                    text=message,
                    access_token=restaurant["fb_token"],
                )
            return 
        
        # Call the menu
        await menu_keyboard_facebook(event, user_id, restaurant, service_mode='delivery')

    elif payload == "order_food":
        await order_meal(event, restaurant)

    elif payload == "browse_products":
        await order_meal(event, restaurant)



# Helper functions you need to adapt:
async def is_delivery_available_whatsapp(user_id, restaurant_data):
    """
    Checks if a restaurant is open for delivery based on its timezone.
    Accepts either a CallbackButton or Message from pywa.
    """

    if not restaurant_data:
        return False, "Restaurant data unavailable. Please try again."
    
    logger.info(f"Checking delivery availability for user_id: {user_id}, restaurant: {restaurant_data.get('rid')}, app: facebook")

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




async def menu_keyboard_facebook(event, user_id, restaurant, service_mode):

    restaurant_id = restaurant.get("rid")

    WEB_APP_URL = await facebook_init_session(
        restaurant_id=restaurant_id,
        user_id=user_id,
        platform="facebook",
        user_service_mode=service_mode,
    )

    button =  [
        {
            "type": "web_url",
            "url": WEB_APP_URL,
            "title": "🍽 Open Menu",
            "webview_height_ratio": "full",
        }
    ]

    await send_button_message(
        recipient_id=user_id,
        text="🍟 Check out our Menu!",
        access_token=restaurant["fb_token"],
        buttons=button,
    )