from COMMON.config import *
from COMMON.sessions import get_user_session, save_user_session
from COMMON.redis import get_arq_redis, redis_client




import httpx
import asyncio
import json
import logging
from decimal import Decimal
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("WHATSAPP_BOT")




load_dotenv(Path(__file__).resolve().parent.parent / ".env")
APP_SECRET = os.getenv("META_APP_SECRET")
VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN")
PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")

