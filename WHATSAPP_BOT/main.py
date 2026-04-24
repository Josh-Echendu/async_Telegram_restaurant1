"""
Main entry point - This is like your bot.py in PTB
"""

import os
from fastapi import FastAPI
from pywa import WhatsApp
from dotenv import load_dotenv

# Import your handlers
from handlers.start_handler import start_handler

load_dotenv()

# Initialize FastAPI (acts as your webhook server)
app = FastAPI()

# Initialize WhatsApp client (like your Application in PTB)
wa = WhatsApp(
    phone_id=os.getenv("WHATSAPP_PHONE_ID"),
    token=os.getenv("WHATSAPP_TOKEN"),
    server=app,  # Attaches webhook to FastAPI
    verify_token=os.getenv("VERIFY_TOKEN"),
    callback_url="https://your-ngrok-url.ngrok.io",  # Will be replaced
)

# ============================================
# 📱 REGISTER YOUR HANDLERS
# ============================================
# In PTB: application.add_handler(CommandHandler("start", start))
# In PyWa: We use decorators

@wa.on_message()
async def handle_all_messages(client: WhatsApp, msg):
    """
    This is like your message_handler in PTB
    We'll route messages based on what they say
    """
    
    # Check if it's a new user or "hi" or "start"
    if not msg.text:
        return  # Ignore non-text messages for now
    
    user_text = msg.text.lower().strip()
    
    # Like CommandHandler("start") in PTB
    if user_text in ["start", "hi", "hello", "hey"]:
        await start_handler(client, msg)
    
    # You can add more handlers here
    # elif user_text == "menu":
    #     await menu_handler(client, msg)
    
    else:
        # Default response
        await client.send_message(
            to=msg.from_user,
            text="Type 'hi' to get started with our restaurant bot! 🍽️"
        )

# ============================================
# 🚀 RUN THE SERVER
# ============================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)