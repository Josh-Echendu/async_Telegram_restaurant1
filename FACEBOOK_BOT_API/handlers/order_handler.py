# handlers/order_handler.py
from core.config import *
from utils_handler import send_button_message


async def order_meal(event, restaurant):

    user_id = event["sender"]["id"]

    service_mode = (restaurant.get("service_mode") or "").lower()
    business_type = (restaurant.get("business_type") or "").lower()

    buttons = []

    # 🟢 Vendor → always delivery only
    if business_type == "vendor":

        buttons = [
            {
                "type": "postback",
                "title": "🚚 Delivery",
                "payload": "order_delivery",
            }
        ]

    # 🟡 Restaurant
    elif business_type == "restaurant":

        if service_mode == "dine_in":

            buttons = [
                {
                    "type": "postback",
                    "title": "🍽️ Dine-in",
                    "payload": "order_dine_in",
                }
            ]

        elif service_mode == "delivery":

            buttons = [
                {
                    "type": "postback",
                    "title": "🚚 Delivery",
                    "payload": "order_delivery",
                }
            ]

        elif service_mode == "both":

            buttons = [
                {
                    "type": "postback",
                    "title": "🍽️ Dine-in",
                    "payload": "order_dine_in",
                },
                {
                    "type": "postback",
                    "title": "🚚 Delivery",
                    "payload": "order_delivery",
                },
            ]

    # ❌ No ordering available
    if not buttons:

        await send_button_message(
            recipient_id=user_id,
            text="❌ Ordering is not available for your business type. Please contact support.",
            access_token=restaurant["fb_token"],
        )
        return

    await send_button_message(
        recipient_id=user_id,
        text="How would you like to order? 🍔",
        buttons=buttons,
        access_token=restaurant["fb_token"],
    )