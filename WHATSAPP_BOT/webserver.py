from pywa import WhatsApp, types
import fastapi

app = fastapi.FastAPI()

# Initialize the client
wa = WhatsApp(
    phone_id="YOUR_PHONE_NUMBER_ID",
    token="YOUR_ACCESS_TOKEN",
    server=app,
    callback_url="https://your-domain.com/webhook", # Your public URL
    verify_token="a_secure_random_string",          # You choose this
)

@wa.on_message()
def handle_message(client: WhatsApp, msg: types.Message):
    # React to the message
    msg.react("🍛")
    
    # Reply with a button to open your Mini-App
    msg.reply_text(
        text=f"Welcome to Vibe Flow, {msg.from_user.name}! Ready to order?",
        buttons=[
            types.Button(
                title="Open Menu 🍴",
                callback_data="open_menu"
            )
        ]
    )

# Run with: uvicorn filename:app --reload