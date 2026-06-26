from tasks import handle_whatsapp_update, handle_telegram_update, process_whatsapp_messages, process_telegram_setup  
from COMMON.redis import redis_settings
import asyncio
import logging

import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def startup(ctx):
    print("🚀 STARTUP CALLED")
    logger.info("🚀 STARTUP CALLED — launching WhatsApp processor")
    print("🚀 STARTUP CALLED — launching WhatsApp processor")  # This should print to stdout
    
    try:
        # Test Redis connection
        await ctx['redis'].ping()
        print("✅ Redis connected")
        asyncio.create_task(process_whatsapp_messages(ctx))

        asyncio.create_task(process_telegram_setup(ctx))
        print("✅ Telegram Setup connected")
        print('✅ love')

    except Exception as e:
        print(f"❌ Redis error: {e}")

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
    functions = [handle_whatsapp_update, handle_telegram_update]

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
        print("🔧 WorkerSettings initialized")
        print(f"   on_startup = {self.on_startup}")