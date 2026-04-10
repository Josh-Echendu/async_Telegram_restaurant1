# bot_manager.py

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from handlers.start_handler import start
from handlers.echo_handler import echo, debug_chat
from handlers.button_handler import button_click
import asyncio
from core.config import *

# =========================
# GLOBAL GUARD (UNCHANGED)
# =========================
async def global_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    cart_locked = context.user_data.get('cart_locked', False)
    allowed_callbacks = ['bank_transfer', "cancel_order"]

    if update.callback_query and update.callback_query.data in allowed_callbacks:
        return # let it go through

    if not cart_locked:
        return

    if update.message:
        try: await update.message.delete()
        except: pass
        await update.message.chat.send_message(
            "💳 Payment in progress.\nPlease complete or ❌ Cancel payment to continue."
        )

    elif update.callback_query:
        await update.callback_query.answer(
            "💳 Payment in progress.\nPlease complete or ❌ Cancel payment to continue.",
            show_alert=True
        )

    raise ApplicationHandlerStop

# bots = {
#     "token_1": <Application instance>,
#     "token_2": <Application instance>,
# }
bots = {} # stores all bot in memory: 

# A lock prevents multiple processes from entering the same code at the same time.
lock = asyncio.Lock()

async def get_bot(token: str):

    # Only ONE request can enter this block at a time, others wait 
    async with lock:
        if token not in bots:
            app = (
                ApplicationBuilder() # creates a builder object
                .token(token) # "use this Telegram bot token"
                .concurrent_updates(True) # run multiple messages at same time
                .build() # This actually create the bot instance
            )

            # app = <Telegram Application>

            # 🔒 Guards — catch EVERYTHING first
            app.add_handler(MessageHandler(filters.ALL, global_guard), group=0)
            app.add_handler(CallbackQueryHandler(global_guard), group=0)

            # 🚦 Handlers
            app.add_handler(CommandHandler("start", start), group=1)
            app.add_handler(MessageHandler(filters.TEXT, echo), group=1)
            app.add_handler(CallbackQueryHandler(button_click), group=1)

            # DEBUG - catch everything else and print to console
            app.add_handler(MessageHandler(filters.ALL, debug_chat), group=99)

            # Prepares bot internally, loads configs, Prpare connections
            await app.initialize()

            # starts the bot engine, allows it to process updates
            await app.start()

            # save bots i.e store bot in memory
            bots[token] = app

        return bots[token]