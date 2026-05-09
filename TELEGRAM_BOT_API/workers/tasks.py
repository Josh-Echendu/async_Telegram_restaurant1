import logging

from telegram import Update

from manager.bot_manager import get_bot
from core.config import get_user_session, save_user_session
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



