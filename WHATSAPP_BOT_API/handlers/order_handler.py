# handlers/order_handler.py - UPDATED PYWA VERSION
from WHATSAPP_BOT_API.core.config import *


async def order_meal(client: WhatsApp, btn):
    user_session = await get_user_session(btn.from_user.wa_id)

    service_mode = (user_session.get("service_mode") or "").lower()
    business_type = (user_session.get("business_type") or "").lower()

    buttons = []

    # 🟢 Vendor → always delivery only
    if business_type == "vendor":
        buttons.append(
            Button(
                title="🚚 Browse & Order Delivery",
                callback_data="order_delivery"
            )
        )

    # 🟡 Restaurant → depends on service_mode
    elif business_type == "restaurant":
        if service_mode in ["dine_in", "both"]:
            buttons.append(
                Button(
                    title="🍽️ Dine-in (Table)",
                    callback_data="order_dine_in"
                )
            )

        if service_mode in ["delivery", "both"]:
            buttons.append(
                Button(
                    title="🚚 Delivery",
                    callback_data="order_delivery"
                )
            )

    # ❌ No options available
    if not buttons:
        await btn.reply(
            text=(
                "❌ <b>Ordering Unavailable</b>\n\n"
                "We're sorry, but ordering is currently not available "
                "for your account.\n"
                "Please contact support for assistance."
            ),
            parse_mode="HTML"
        )
        return

    # ✅ BEAUTIFUL PROMPT
    prompt_text = (
        "🍽️ <b>Ready to place your order?</b>\n\n"
        "How would you like to enjoy your meal today?\n"
        "👇 <i>Choose an option below:</i>"
    )

    await btn.reply(
        text=prompt_text,
        buttons=buttons,
        parse_mode="HTML"
    )