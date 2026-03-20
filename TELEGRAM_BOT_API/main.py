# main.py - EXACT COPY FROM ORIGINAL FILE (with imports adjusted)
from config import *
from handlers.start_handler import start
from handlers.button_handler import button_click
from handlers.echo_handler import echo, debug_chat
from handlers.order_handler import order_meal


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


# =========================
# MAIN ENTRY
# =========================
NGROK_URL = "https://567c-102-89-82-170.ngrok-free.app"  # replace with your ngrok URL
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{NGROK_URL}{WEBHOOK_PATH}"


if __name__ == '__main__':
    logging.info("Starting bot...")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)
        .build()
    )

    # print("app: ", app.job_queue)
    # app = ApplicationBuilder().token("8571806750:AAFOY6-QdejiSOthWBkJK3ufR4I2FYpV31Q").build()

    # 🔒 Guards — catch EVERYTHING first
    app.add_handler(MessageHandler(filters.ALL, global_guard), group=0)
    app.add_handler(CallbackQueryHandler(global_guard), group=0)

    # 🚦 Actual logic — only runs if guard allows
    app.add_handler(CommandHandler("start", start), group=1)
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo), group=1)
    app.add_handler(CallbackQueryHandler(button_click), group=1)
    
    # DEBUG - catch everything else and print to console
    app.add_handler(MessageHandler(filters.ALL, debug_chat), group=99)

    # Run webhook instead of polling
    app.run_webhook(
        listen="0.0.0.0",
        port=8080,
        url_path=WEBHOOK_PATH,
        webhook_url=WEBHOOK_URL,
        drop_pending_updates=True,
    )

    # app.run_polling(drop_pending_updates=True)

