from tasks import handle_whatsapp_update, handle_telegram_update
from COMMON.redis import redis_settings


class WorkerSettings:
    functions = [handle_whatsapp_update, handle_telegram_update]

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