# handlers/order_handler.py - CONVERTED TO PYWA
from WHATSAPP_BOT_API.core.config import *


async def order_meal(client: WhatsApp, btn):
    user_session = await get_user_session(btn.from_user.wa_id)

    service_mode = (user_session.get("service_mode") or "").lower()
    business_type = (user_session.get("business_type") or "").lower()

    buttons = []

    # 🟢 Vendor → always delivery only
    if business_type == "vendor":

        buttons = [
            Button(title="🚚 Delivery", callback_data="order_delivery")
        ]

    # 🟡 Restaurant → depends on service_mode
    elif business_type == "restaurant":

        if service_mode == "dine_in":
            buttons = [
                Button(title="🍽️ Dine-in", callback_data="order_dine_in")
            ]

        elif service_mode == "delivery":
            buttons = [
                Button(title="🚚 Delivery", callback_data="order_delivery")
            ]

        elif service_mode == "both":
            buttons = [
                Button(title="🍽️ Dine-in", callback_data="order_dine_in"),
                Button(title="🚚 Delivery", callback_data="order_delivery")
            ]

    # ❌ No options available
    if not buttons:
        await btn.reply(
            text="❌ Ordering is not available for your business type. Please contact support."
        )
        return

    await btn.reply(
        text="How would you like to order ? 🍔",
        buttons=buttons
    )