import logging
from telegram import Update
from TELEGRAM_BOT_API.manager.bot_manager import get_bot
from TELEGRAM_BOT_API.core.config import get_user_session, save_user_session
from WHATSAPP_BOT_API.manager.wa_manager import get_wa_client


logger = logging.getLogger(__name__)


async def handle_telegram_update(ctx, update_data: dict, restaurant: dict):
    print("ctx: ", ctx)
    print("group ctx: ", ctx)
    
    # 🤖 1. Get the Bot Instance (Ideally from worker context 'ctx')
    bot_app = await get_bot(restaurant['bot_token'])
    print("group bot app: ", bot_app)
    
    # 🔁 2. Reconstruct the Update Object
    # We pass the bot instance so the update knows how to 'reply'
    update = Update.de_json(update_data, bot_app.bot)

    # 🔥 ADD THIS DEBUG
    if update.message and update.message.text:
        print(f"📨 Processing message: {update.message.text}")
        if update.message.text.startswith('/gencode'):
            print("🔥 /gencode command detected!")

    # 🧠 3. Session Logic (Moved from FastAPI to Worker)
    if update.effective_user:
        user_id = update.effective_user.id
        print("user_id group: ", user_id)
        user_session = await get_user_session(user_id)

        user_session.update({
            "current_rid": restaurant["rid"],
            "restaurant_name": restaurant["bot_name"],
            "business_type": restaurant["business_type"],
            "service_mode": restaurant["service_mode"],
            "max_tables": restaurant["max_tables"],
            "time_zone": restaurant["time_zone"],
        })


        if update.callback_query and update.callback_query.data.startswith("table_"):
            table_number = update.callback_query.data.replace("table_", "")
            user_session["table_number"] = table_number

        await save_user_session(user_id, user_session)

    # ⚡ 4. Process the Handlers (start, echo, payment, etc.)
    await bot_app.process_update(update)



async def handle_whatsapp_update(
    ctx,
    update_data: dict,
    raw_payload: bytes,
    signature: str,
    restaurant: dict,
):
    """
    ARQ Task for handling WhatsApp updates.
    """
    print(f"🚀 Processing WhatsApp update for RID: {restaurant['rid']}")

    # 🤖 1. Get the Pywa Client Instance
    # The client already has all handlers (message, buttons, etc.) attached
    wa_client = await get_wa_client(
        phone_id=restaurant["wa_phone_id"],
        token=restaurant["wa_token"],
    )

    # 🧠 2. Session Logic (Extract WAID from parsed JSON)
    try:
        # Webhook -> entry -> changes -> value
        value = update_data["entry"][0]["changes"][0]["value"]

        # Only process actual user messages
        if "messages" in value:
            user_info = value["messages"][0]
            wa_id = user_info["from"]  # e.g. 2349063938743

            print(f"👤 User WAID: {wa_id}")

            # Fetch and update session
            user_session = await get_user_session(wa_id)
            user_session.update({
                "current_rid": restaurant["rid"],
                "restaurant_name": restaurant["bot_name"],
                "business_type": restaurant["business_type"],
                "service_mode": restaurant["service_mode"],
                "max_tables": restaurant["max_tables"],
                "time_zone": restaurant["time_zone"],
            })

            # Handle table selection button payloads
            if (
                "button" in user_info
                and user_info["button"]["payload"].startswith("table_")
            ):
                table_number = user_info["button"]["payload"].replace("table_", "")
                user_session["table_number"] = table_number

            await save_user_session(wa_id, user_session)

    except (KeyError, IndexError):
        # Status updates (sent, delivered, read) do not contain message data
        pass

    # ⚡ 3. Process the Webhook Through pywa_async
    # Since you created the client with server=None, use webhook_update_handler()
    try:
        await wa_client.webhook_update_handler(
            update=raw_payload,
            hmac_header=signature,
        )
        print("✅ WhatsApp handlers executed successfully")
    except Exception:
        logger.exception("❌ Error in Pywa handler")