from decimal import Decimal
from pywa.types import Button
from pywa.types import Message
from pywa import WhatsApp

async def debug_chat(client: WhatsApp, msg: Message):
    pass
    # always turn off privacy with /setprivacy so bot can receive all messages sent to group
    print("CHAT ID:", msg.from_user.phone)  # This is the user's phone number
    print("CHAT TYPE:", msg.chat_type)  # This will show if it's a private
    print("CHAT data structure:", type(msg.from_user.phone))
    print("CHAT TYPE:", msg.author.name)  # This is the user's name
    print("CHAT:", msg)


async def echo(client: WhatsApp, msg: Message):
    text = msg.text or "No text content"

    user_id = msg.author.phone  # Changed from update.effective_user.id
    print(f"Echoing back to {user_id}: {text}")

    if text == "🍽 Order Food":
        await order_meal(client, msg)

    elif text == "📞 Contact Staff":
        first_name = msg.author.name or "Customer"

        await client.send_message(
            to=msg.from_user,
            text=f"Good day {first_name} 😊, to contact us you call us on \n\n CONTACT: +234 906 393 8743."
        )


    elif text == "🛍️✅💳 Checkout/Pay":
        lines = []
        vat = int(100)
        grand_total = Decimal('0.00')  # ← initialize here

        # Note: You'll need to adapt this function - same logic but pass msg instead of update
        order_batches = await api_get_user_order_batches_whatsapp(msg)

        if not order_batches:
            await client.send_message(
                to=msg.from_user,
                text="You have no active orders."
            )
            return
        
        for order in order_batches:
            lines.append(f"🆔 BATCH ID: *{order['bid']}*")  # Changed <b> to * for Markdown

            for item in order["items"]:
                qty = item["quantity"]
                price = item["price"]
                title = item["product_title"]
                subtotal = qty * price
                lines.append(f"_{qty}x {title} - ₦{subtotal:,}_")  # Changed <i> to _

            grand_total += int(order["total_price"])  # now this works
            lines.append("")  # blank line between batches

        summary = (
            "🧾 *Your Order Summary*\n\n"
            f"Restaurant 📜🍽️🍷: _{order['restaurant']}_\n"
            f"👤 Customer: _{msg.author.name or 'Customer'}_\n\n"
            + "\n".join(lines)
            + f"\n\nTotal Price: ₦{grand_total:,}"
            + f"\nVAT Charges: ₦{vat:,}"
            + f"\n——————————\n*Grand Total: ₦{int(grand_total + vat):,}*"
        )

        await client.send_message(
            to=msg.from_user,   
            text=summary
        )

        # CORRECTED: In PyWa, buttons are sent as part of the interactive parameter
        await client.send_message(
            to=msg.from_user,  # Changed from chat_id to 'to' (parameter name matters)
            text="💰 Select your payment method:",  # Added text before buttons
            buttons=await payment_keyboard_whatsapp()  # This is correct for PyWa
        )


async def payment_keyboard_whatsapp():
    # CORRECT: In PyWa, Button objects work like Telegram's InlineKeyboardButton
    # They trigger a callback through your webhook
    return [
        Button(
            title="💵 Cash Payment", 
            callback_data="pay_cash"
        ),
        Button(
            title="🏦💸 Bank Transfer", 
            callback_data="bank_transfer"
        ),
        Button(
            title="🛒💳 POS Payment", 
            callback_data="pay_pos"
        )
    ]