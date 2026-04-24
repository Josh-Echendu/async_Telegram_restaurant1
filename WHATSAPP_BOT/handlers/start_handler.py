import httpx
import asyncio
import logging
from typing import Optional, Dict, Any

# PyWa specific imports
from pywa.types import Message
from pywa import WhatsApp
# For WhatsApp-specific buttons
from pywa.types import (
    ReplyButton,           # Like Telegram's ReplyKeyboardButton
    InteractiveMessage,    # Like Telegram's InlineKeyboard but different
    ListMessage,           # Another way to show options
    Section,               # For organizing ListMessage
    Row                    # For button rows
)

from core.config import get_restaurant_data_whatsapp


# ============================================
# 📊 LOGGER FUNCTION (Converted from your logger)
# ============================================
async def logger_whatsapp(client: WhatsApp, msg: Message):
    """
    Convert your existing logger function
    Logs user interactions
    """
    user_name = msg.author.name or "Unknown"
    user_phone = msg.author.phone
    message_text = msg.text or "[Non-text message]"
    
    print(f"""
    📱 WhatsApp Interaction Log
    ━━━━━━━━━━━━━━━━━━━━━━━
    User: {user_name}
    Phone: {user_phone}
    Message: {message_text}
    Timestamp: {msg.timestamp}
    ━━━━━━━━━━━━━━━━━━━━━━━
    """)


async def start_handler(client: WhatsApp, msg: Message):
    
    # In PyWa: We'll adapt your logger function
    await logger_whatsapp(client, msg)

    # In PTB: restaurant_data = await get_restaurant_data(update)
    # In PyWa: Same function, just pass msg instead of update
    restaurant_data = await get_restaurant_data_whatsapp(msg)
    restaurant_id = restaurant_data.get('current_rid')
    restaurant_name = restaurant_data.get('restaurant_name')
    
    print(f"🏪 Restaurant ID: {restaurant_id}")
    print(f"🏪 Restaurant Name: {restaurant_name}")

    # PyWa way (CORRECT)
    chat_id = msg.from_user.phone      # ✅ exists in PyWa
    user_id = msg.author.phone         # ✅ exists in PyWa  
    first_name = msg.author.name or "Customer"  # ✅ exists in PyWa
    user_phone = msg.author.phone    # ✅ exists in PyWa

    print(f"👤 User: {first_name} ({user_phone})")


    interactive_buttons = InteractiveMessage.create(
        body="👇 *Choose an option below*",  # This is like your "text" parameter
        action=InteractiveMessage.Action(
            buttons=[
                ReplyButton(type="reply", reply=ReplyButton.Reply(id="order_food", title="🍽 Order Food")),
                ReplyButton(type="reply", reply=ReplyButton.Reply(id="contact_staff", title="📞 Contact Staff")),
                ReplyButton(type="reply", reply=ReplyButton.Reply(id="checkout_pay", title="🛍️✅💳 Checkout/Pay"))
            ]
        )
    )

    list_message = ListMessage.create(
        body="👇 *Choose an option below*",  # This is like your "text"
        action=ListMessage.Action(
            button_title="Options",  # The text on the button that opens the list
            sections=[
                Section(
                    title="Main Options",
                    rows=[
                        Row(id="order_food", title="🍽 Order Food", description="Browse our delicious meals"), # Helper text
                        Row(id="contact_staff", title="📞 Contact Staff", description="Get in touch with our team"),
                        Row(id="checkout_pay", title="🛍️✅💳 Checkout/Pay", description="Complete your purchase")
                    ]
                )
            ]
        )
    )

    # PyWa way:
    welcome_text = (
        f"👋 *Welcome to {restaurant_name}, {first_name}!*\n\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🍽 I'm your personal restaurant assistant\n\n"
        f"What you can do:\n\n"
        f"🛍 Browse meals\n"
        f"🛒 View cart\n"
        f"📦 Track orders\n"
        f"⚡ Enjoy fast and easy ordering\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"👇 *Choose an option below*"
    )

    # Send the welcome message with the ListMessage (dropdown)
    # First send the text, then send the button menu
    await client.send_message(
        to=msg.from_user,
        text=welcome_text
    )

    # Now send the interactive menu (the LIST)
    await client.send_message(
        to=msg.from_user,
        interactive=list_message
    )

    # You can choose to send either interactive_buttons or list_message based on your preference
    await client.send_message(
        to=msg.from_user,
        interactive=interactive_buttons
    )

    username = msg.author.name or f"user_{user_phone[-4:]}"  # Create username from name or phone


    await whatsapp_registration(
        whatsapp_id=user_id,
        first_name=first_name,
        username=username,
        phone_number=user_phone,
        restaurant_id=restaurant_id
    )

# ============================================
# 📝 REGISTRATION FUNCTION (Converted from telegram_registration)
# ============================================
async def whatsapp_registration(
    whatsapp_id: str,      # Changed from telegram_id
    first_name: str,
    username: str,
    phone_number: str,     # Added this field
    restaurant_id: str,
    max_retries: int = 5
):
    """
    Converts your telegram_registration function
    Same logic, just adapted for WhatsApp user data
    """
    
    payload = {
        "whatsapp_id": str(whatsapp_id),      # Changed field name
        "first_name": str(first_name),
        "username": str(username),
        "phone_number": str(phone_number),    # Added this field
        "restaurant_id": str(restaurant_id)
    }
    
    print(f"📝 Registering user: {payload}")
    
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"http://web:8000/userauths/register_user/whatsapp/",  # Changed endpoint
                    headers={"Accept": "application/json"},
                    json=payload
                )
                response.raise_for_status()
                print("✅ User registration successful:", response.json())
                return response.json()
                
        except httpx.HTTPStatusError as e:
            # Try to get error details
            try:
                error_data = e.response.json()
                print(f"❌ User registration error: {error_data}")
            except:
                print(f"❌ HTTP error {e.response.status_code}: {e.response.text}")
                
            logging.warning(f"Attempt {attempt}/{max_retries} failed: {e}")
            
            if attempt == max_retries:
                logging.error(f"All {max_retries} attempts failed")
                return None
                
            await asyncio.sleep(2 ** attempt)  # Exponential backoff: 2, 4, 8 seconds
            
        except httpx.RequestError as e:
            print(f"🌐 Network error on attempt {attempt}: {e}")
            logging.warning(f"Attempt {attempt} failed: {e}")
            
            if attempt == max_retries:
                logging.error(f"All {max_retries} attempts failed")
                return None
                
            await asyncio.sleep(2 ** attempt)
    
    return None