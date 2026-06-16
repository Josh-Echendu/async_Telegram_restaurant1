from UNOFFICIAL_WHATSAPP_API.core.config import get_user_session


async def order_meal(user_session):
    """Returns dict with order mode selection buttons."""
    
    service_mode = user_session.get('service_mode', '').lower()
    business_type = user_session.get('business_type', '').lower()

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