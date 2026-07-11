from tasks import handle_whatsapp_update, handle_telegram_update, process_telegram_setup, notify_telegram_payment_request, notify_whatsapp_payment_confirmed
from COMMON.redis import redis_settings, redis_client
import asyncio
from COMMON.logger_config import *

import os



async def startup(ctx):
    logger.info("🚀 STARTUP CALLED")
    logger.info("🚀 STARTUP CALLED — launching WhatsApp processor")
    logger.info("🚀 STARTUP CALLED — launching WhatsApp processor")  # This should print to stdout
    
    try:
        # Test Redis connection
        await ctx['redis'].ping()
        logger.info("✅ Redis connected")
        # asyncio.create_task(process_whatsapp_messages(ctx))

        asyncio.create_task(process_telegram_setup(ctx))
        logger.info("✅ Telegram Setup connected")

    except Exception as e:
        logger.exception(f"❌ Redis error: {e}")

    
    try:
        await redis_client.xgroup_create(
            name="telegram:setup",
            groupname="telegram_workers",
            id="0",
            mkstream=True,
        )

        logger.info(
            "Created telegram consumer group."
        )

    except Exception as e:

        if "BUSYGROUP" not in str(e):
            raise

        logger.info(
            "Telegram consumer group already exists."
        )

    # # Browser
    # try:
    #     browser = await start_browser()
    #     tab = await browser.start()

    #     ctx["browser"] = browser
    #     ctx["telegram_tab"] = tab

    #     await ctx['telegram_tab'].go_to("https://web.telegram.org/a/", timeout=120)

    #     print("✅ Telegram loaded")

    # except Exception as e:
    #     print(f"❌ Browser session error: {e}")


# async def start_browser():
#     options = ChromiumOptions()

#     session_folder = os.path.abspath(
#         r"C:\Users\Admin\Music\async_Telegram_restaurant\PYDOLL_TELEGRAM_WEB_AUTOMATION\web_automation\telegram_persistent_profile"
#     )
#     os.makedirs(session_folder, exist_ok=True)

#     options.binary_location = r"C:\Users\Admin\AppData\Local\Google\Chrome\Application\chrome.exe"
#     options.add_argument(f"--user-data-dir={session_folder}")

#     return Chrome(options=options)


class WorkerSettings:
    functions = [
                handle_whatsapp_update, handle_telegram_update, 
                notify_telegram_payment_request, notify_whatsapp_payment_confirmed
            ]

    # ✅ This is the missing piece - register the startup function
    on_startup = startup  # <-- ADD THIS


    # ARQ will: parse the URL, extract host, port, db, password
    # configure connection automatically
    redis_settings = redis_settings

    # 🔥 Production tuning
    max_jobs = 50              # concurrency
    
    # “How many jobs can run at the same time?”
    job_timeout = 60           # seconds
    
    # 👉 How long ARQ stores job results in Redis
    keep_result = 10         # 1 hour
    max_tries = 5              # retries
    queue_name = "restaurant_jobs"  # queue name

    # ✅ Add this to debug
    def __init__(self):
        logger.info("🔧 WorkerSettings initialized")
        logger.info(f"   on_startup = {self.on_startup}")
