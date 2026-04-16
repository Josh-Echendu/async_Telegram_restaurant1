from arq import Worker
from arq.connections import RedisSettings
from dotenv import load_dotenv
from pathlib import Path    
import os
from workers.tasks import handle_telegram_update

load_dotenv(Path(__file__).resolve().parent / ".env")
REDIS_URL = os.getenv("REDIS_URL")

class WorkerSettings:
    functions = [handle_telegram_update]

    # ARQ will: parse the URL, extract host, port, db, password
    # configure connection automatically
    redis_settings = RedisSettings.from_dsn(REDIS_URL)

    # 🔥 Production tuning
    max_jobs = 50              # concurrency
    
    # “How many jobs can run at the same time?”
    job_timeout = 60           # seconds
    
    # 👉 How long ARQ stores job results in Redis
    keep_result = 10         # 1 hour
    max_tries = 5              # retries
    queue_name = "restaurant_jobs"  # queue name