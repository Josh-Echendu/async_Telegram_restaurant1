import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import httpx
from arq import create_pool
from arq.connections import RedisSettings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import redis.asyncio as redis


CONFIG = {
    "FASTAPI_USERBOT_URL": "http://localhost:8000",
    "ADMIN_USER_ID": "YOUR_TELEGRAM_USER_ID",  # Your account ID
    "MAX_RETRIES": 3,
    "TIMEOUT_SECONDS": 30,
    "RATE_LIMIT_DELAY": 2,  # Seconds between API calls
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)





