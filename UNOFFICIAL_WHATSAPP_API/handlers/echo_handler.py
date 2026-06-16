from decimal import Decimal
from .order_handler import order_meal
from .kitchen_handler import api_get_user_order_batches
from .start_handler import start_handler


async def echo(wa_id, text, push_name, restaurant):
    """Returns a dict with reply text and optional buttons."""

    print(f"Echo handler for {wa_id}: {text}")

    if text == "🍽 Order Food":
        return await order_meal(wa_id, restaurant)

    elif text == "📦 Track Order":
        first_name = push_name or "Customer"
        return {
            "text": f"Good day {first_name} 😊, to contact us call:\n\n📞 +234 906 393 8743."
        }

    elif text == "🛍️✅💳 Checkout/Pay":
        return await handle_checkout(wa_id, push_name, restaurant)

    else:
        return await start_handler(wa_id, text, push_name, restaurant)


async def handle_checkout(wa_id, push_name, restaurant):
    """Builds order summary and returns it with payment buttons."""
    lines = []
    vat = int(100)
    grand_total = Decimal('0.00')

    order_batches = await api_get_user_order_batches(wa_id, restaurant)

    if not order_batches:
        return {"text": "You have no active orders."}

    for order in order_batches:
        lines.append(f"🆔 BATCH ID: *{order['bid']}*")

        for item in order["items"]:
            qty = item["quantity"]
            price = item["price"]
            title = item["product_title"]
            subtotal = qty * price
            lines.append(f"_{qty}x {title} - ₦{subtotal:,}_")

        grand_total += int(order["total_price"])
        lines.append("")

    first_name = push_name or "Customer"

    summary = (
        "🧾 *Your Order Summary*\n\n"
        f"Restaurant 📜🍽️🍷: _{order['restaurant']}_\n"
        f"👤 Customer: _{first_name}_\n\n"
        + "\n".join(lines)
        + f"\n\nTotal Price: ₦{grand_total:,}"
        + f"\nVAT Charges: ₦{vat:,}"
        + f"\n——————————\n*Grand Total: ₦{int(grand_total + vat):,}*"
    )

    return {
        "text": summary,
        "buttons": [
            {"id": "pay_cash", "text": "💵 Cash Payment"},
            {"id": "bank_transfer", "text": "🏦💸 Bank Transfer"},
            {"id": "pay_pos", "text": "🛒💳 POS Payment"},
        ]
    }