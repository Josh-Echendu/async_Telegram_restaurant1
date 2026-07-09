from COMMON.config import *
from COMMON.sessions import get_user_session, save_user_session
from COMMON.redis import get_arq_redis, redis_client
from COMMON.logger_config import logger
import httpx
import asyncio
import json
from decimal import Decimal
from pywa_async.types import Button, Message, CallbackButton
from pywa_async import WhatsApp, filters, handlers



load_dotenv(Path(__file__).resolve().parent.parent / ".env")
APP_SECRET = os.getenv("META_APP_SECRET")
VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN")
PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")

