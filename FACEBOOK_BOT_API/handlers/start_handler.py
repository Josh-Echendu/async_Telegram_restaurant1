from core.config import _request_with_retry

fb_user_data = {}


async def start(event, restaurant_data):

    restaurant_id = restaurant_data.get("current_rid")
    restaurant_name = restaurant_data.get("restaurant_name")
    business_type = (restaurant_data.get("business_type") or "").lower()
    vendor_type = (restaurant_data.get("vendor_type") or "").lower()
    service_mode = (restaurant_data.get("service_mode") or "").lower()

    user_id = event["sender"]["id"]

    # Messenger has no username
    username = None

    # --------------------------------------------------
    # GET USER PROFILE (CACHE FIRST)
    # --------------------------------------------------
    if user_id in fb_user_data:

        profile = fb_user_data[user_id]

    else:

        response = await _request_with_retry(
            method="GET",
            url=f"https://graph.facebook.com/v23.0/{user_id}",
            params={
                "fields": "first_name,last_name",
                "access_token": restaurant_data["fb_token"],
            },
        )

        # Keep this if your _request_with_retry() returns a Response on failures.
        if response.status_code != 200:
            return

        profile = response.json()

        # --------------------------------------------------
        # REGISTER USER
        # --------------------------------------------------
        registration = await facebook_registration(
            facebook_id=user_id,
            first_name=profile.get("first_name", ""),
            last_name=profile.get("last_name", ""),
            username=username,
            restaurant_id=restaurant_id,
        )

        if not registration:
            return

        fb_user_data[user_id] = profile

    # Always available
    first_name = profile.get("first_name", "")
    last_name = profile.get("last_name", "")

    # --------------------------------------------------
    # BUSINESS BUTTONS
    # --------------------------------------------------
    buttons = None

    if business_type == "restaurant":

        if service_mode == "delivery":
            buttons = [
                {
                    "type": "postback",
                    "title": "🍽 Order Food",
                    "payload": "order_food",
                },
                {
                    "type": "postback",
                    "title": "📦 Track Order",
                    "payload": "track_order",
                },
                {
                    "type": "postback",
                    "title": "📞 Contact Staff",
                    "payload": "contact_staff",
                },
            ]

        elif service_mode in ["dine_in", "both"]:
            buttons = [
                {
                    "type": "postback",
                    "title": "🍽 Order Food",
                    "payload": "order_food",
                },
                {
                    "type": "postback",
                    "title": "📦 Track Order",
                    "payload": "track_order",
                },
                {
                    "type": "postback",
                    "title": "💳 Checkout/Pay",
                    "payload": "checkout",
                },
            ]

    elif business_type == "vendor":

        if vendor_type == "goods":
            buttons = [
                {
                    "type": "postback",
                    "title": "🛍 Browse Products",
                    "payload": "browse_products",
                },
                {
                    "type": "postback",
                    "title": "📦 Track Order",
                    "payload": "track_order",
                },
                {
                    "type": "postback",
                    "title": "📞 Contact Staff",
                    "payload": "contact_staff",
                },
            ]

        elif vendor_type == "cooked_food":
            buttons = [
                {
                    "type": "postback",
                    "title": "🍽 Order Food",
                    "payload": "order_food",
                },
                {
                    "type": "postback",
                    "title": "📦 Track Order",
                    "payload": "track_order",
                },
                {
                    "type": "postback",
                    "title": "📞 Contact Staff",
                    "payload": "contact_staff",
                },
            ]

        else:
            buttons = [
                {
                    "type": "postback",
                    "title": "🛍 Browse Products",
                    "payload": "browse_products",
                },
                {
                    "type": "postback",
                    "title": "📦 Track Order",
                    "payload": "track_order",
                },
                {
                    "type": "postback",
                    "title": "📞 Contact Staff",
                    "payload": "contact_staff",
                },
            ]

    else:
        buttons = [
            {
                "type": "postback",
                "title": "🍽 Order Food",
                "payload": "order_food",
            },
            {
                "type": "postback",
                "title": "📦 Track Order",
                "payload": "track_order",
            },
            {
                "type": "postback",
                "title": "📞 Contact Staff",
                "payload": "contact_staff",
            },
        ]

    # --------------------------------------------------
    # WELCOME MESSAGE
    # --------------------------------------------------
    messages = {
        "restaurant": {
            "icon": "🍽️",
            "role": "Your personal restaurant assistant",
            "features": "🛍 Browse meals\n🛒 View cart\n📦 Track orders\n⚡ Enjoy fast and easy ordering",
        },
        "vendor_goods": {
            "icon": "🛍️",
            "role": "Your personal store assistant",
            "features": "🛍️ Browse products\n🛒 Add to cart\n📦 Track orders\n💰 Quick and secure checkout",
        },
        "vendor_cooked_food": {
            "icon": "🍲",
            "role": "Your personal food vendor assistant",
            "features": "🍽 Browse meals\n🛒 Place orders\n📦 Track deliveries\n⚡ Fresh and fast service",
        },
    }

    if business_type == "restaurant":
        message_template = messages["restaurant"]
    elif business_type == "vendor" and vendor_type == "goods":
        message_template = messages["vendor_goods"]
    elif business_type == "vendor" and vendor_type == "cooked_food":
        message_template = messages["vendor_cooked_food"]
    else:
        message_template = messages["restaurant"]

    welcome_text = (
        f"{message_template['icon']} Welcome to {restaurant_name}, {first_name}!\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 {message_template['role']}\n\n"
        "✨ What you can do:\n\n"
        f"{message_template['features']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👇 Choose an option below."
    )

    await send_button_message(
        recipient_id=user_id,
        text=welcome_text,
        buttons=buttons,
        access_token=restaurant_data["fb_token"],
    )



async def send_button_message(recipient_id, text, access_token, buttons=None):

    payload = {
        "recipient": {
            "id": recipient_id,
        },
        "messaging_type": "RESPONSE",
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": text,
                    "buttons": buttons or [],
                },
            }
        },
    }

    response, success = await _request_with_retry(
        method="POST",
        url="https://graph.facebook.com/v23.0/me/messages",
        params={
            "access_token": access_token,
        },
        json=payload,
    )

    return success











async def facebook_registration():
        pass