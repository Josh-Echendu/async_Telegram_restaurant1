import pytz
import httpx
from datetime import datetime, timezone, time
from UNOFFICIAL_WHATSAPP_API.services.restaurant_cache import get_restaurant


async def handle_order_buttons(wa_id, callback_data, restaurant):
    """Returns dict with reply text, buttons, or menu URL."""

    if callback_data == "order_dine_in":
        return await menu_keyboard_whatsapp(wa_id, restaurant, service_mode="dine_in")

    elif callback_data == "order_delivery":
        service_mode = restaurant.get('service_mode', '').lower()

        if service_mode in ['delivery', 'both']:
            is_available, message = await is_delivery_available_whatsapp(restaurant)
            if not is_available:
                return {"text": message}

        return await menu_keyboard_whatsapp(wa_id, restaurant, service_mode="delivery")

    elif callback_data == "order_food":
        service_mode = restaurant.get('service_mode', '').lower()
        business_type = restaurant.get('business_type', '').lower()

        buttons = []

        if business_type == "vendor":
            buttons.append({"id": "order_delivery", "text": "🚚 Delivery"})
        else:
            if service_mode in ["dine_in", "both"]:
                buttons.append({"id": "order_dine_in", "text": "🍽️ Dine-in"})
            if service_mode in ["delivery", "both"]:
                buttons.append({"id": "order_delivery", "text": "🚚 Delivery"})

        return {
            "text": "How would you like to order today? 🍔",
            "buttons": buttons,
        }

    elif callback_data == "pay_cash":
        return {"text": "💵 Please pay cash at the counter. Your order is being prepared!"}

    elif callback_data == "bank_transfer":
        return {"text": "🏦 Bank transfer details:\n\nAccount: 0123456789\nBank: GTBank\nName: MamaPut"}

    elif callback_data == "pay_pos":
        return {"text": "🛒 POS payment will be processed at the counter."}

    else:
        return {"text": "Unknown option. Please try again."}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def is_delivery_available_whatsapp(restaurant):
    """Checks if restaurant is open for delivery. Returns (bool, message)."""

    rid = restaurant.get('rid')
    time_zone = restaurant.get('time_zone', 'Africa/Lagos')
    open_time_str = restaurant.get('open_time')
    close_time_str = restaurant.get('close_time')
    is_closed = restaurant.get('is_closed', False)

    try:
        restaurant_tz = pytz.timezone(time_zone)
    except Exception:
        restaurant_tz = pytz.timezone('Africa/Lagos')

    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(restaurant_tz)
    current_time = now_local.time()

    if is_closed:
        return False, "🙏 We're closed for delivery today. See you tomorrow!"

    if not open_time_str or not close_time_str:
        return False, "🙏 Delivery hours are not set for this location yet."

    try:
        open_time = time.fromisoformat(open_time_str)
        close_time = time.fromisoformat(close_time_str)
    except Exception:
        return False, "System error calculating opening hours."

    if open_time <= close_time:
        is_open = open_time <= current_time <= close_time
    else:
        is_open = current_time >= open_time or current_time <= close_time

    if not is_open:
        open_12hr = open_time.strftime('%I:%M %p')
        close_12hr = close_time.strftime('%I:%M %p')
        return False, f"🚚 Delivery available from {open_12hr} to {close_12hr}."

    return True, "Delivery available"


async def menu_keyboard_whatsapp(wa_id, restaurant, service_mode=None):
    """Generates web app URL and returns it as a text reply."""

    restaurant_id = restaurant.get('rid')
    platform = "whatsapp2"

    WEB_APP_URL = await whatsapp_init_session(
        restaurant_id=restaurant_id,
        user_id=wa_id,
        platform=platform,
        user_service_mode=service_mode,
    )

    return {
        "text": (
            "🍟 *Check out our Menu!* 🍟\n\n"
            "Click the link below to view our meals and place your order:\n"
            f"{WEB_APP_URL}"
        )
    }


async def whatsapp_init_session(restaurant_id, user_id, platform, user_service_mode=None):
    """Calls Django to initialize a session and returns the web app URL."""

    payload = {
        "restaurant_id": restaurant_id,
        "user_id": user_id,
        "mode": user_service_mode,
        "platform": platform,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "http://web:8000/userauths/whatsapp/init_session/",
            json=payload,
        )
        data = response.json()
        return data.get('url')