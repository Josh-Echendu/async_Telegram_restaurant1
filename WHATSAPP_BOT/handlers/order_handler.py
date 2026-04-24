# handlers/order_handler.py - CONVERTED TO PYWA
from core.config import *
from utils.cart_utils import *
from utils.image_utils import *
from pywa.types import ListMessage, Section, Row
from pywa import WhatsApp
from pywa.types import Message as WhatsAppMessage
from pywa.types import Button



EMOJI_NUMBERS = {
    1: "1️⃣", 2: "2️⃣", 3: "3️⃣",
    4: "4️⃣", 5: "5️⃣", 6: "6️⃣",
    7: "7️⃣", 8: "8️⃣", 9: "9️⃣",
    10: "🔟",
    11: "1️⃣1️⃣",
    12: "1️⃣2️⃣",
    13: "1️⃣3️⃣",
    14: "1️⃣4️⃣",
    15: "1️⃣5️⃣",
    16: "1️⃣6️⃣",
    17: "1️⃣7️⃣",
    18: "1️⃣8️⃣",
    19: "1️⃣9️⃣",
    20: "2️⃣0️⃣"
}


async def choose_table(client: WhatsApp, callback_query):
    user_session = await get_user_session(callback_query.from_user.phone)
    max_tables = user_session['max_tables']

    # ONE SINGLE LIST - ONE SECTION WITH ALL ROWS
    rows = []
    
    for i in range(1, max_tables + 1):
        emoji = EMOJI_NUMBERS.get(i, str(i))
        rows.append(Row(id=f"table_{emoji}", title=emoji))

    list_message = ListMessage(
        body="Select a table:",
        button_text="📋 Choose Table",
        sections=[Section(title="Tables", rows=rows)]  # ONE SECTION - NOT BROKEN
    )
    
    await client.send_message(
        to=callback_query.from_user,
        interactive=list_message
    )

async def order_meal(client: WhatsApp, msg: WhatsAppMessage):
    await logger_whatsapp(client, msg)
    user_session = await get_user_session(msg.author.phone)
    service_mode = user_session['service_mode'].lower()
    business_type = user_session['business_type'].lower()

    buttons = []
    
    if business_type == "vendor":
        buttons.append(Button(title="🚚 Delivery", callback_data="order_delivery"))
    else:
        if service_mode.lower() in ["dine_in", "both"]:
            buttons.append(Button(title="🍽️ Dine-in", callback_data="order_dine_in"))
        
        if service_mode.lower() in ["delivery", "both"]:
            buttons.append(Button(title="🚚 Delivery", callback_data="order_delivery"))
    
    await client.send_message(
        to=msg.from_user,
        text="How would you like to order?",
        buttons=buttons  # Same Button class, not CallbackButton
    )