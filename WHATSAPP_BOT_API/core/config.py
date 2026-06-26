from COMMON.config import *
from COMMON.sessions import get_user_session, save_user_session
from COMMON.redis import get_arq_redis

import httpx
import asyncio
import json
import logging
from decimal import Decimal



load_dotenv(Path(__file__).resolve().parent.parent / ".env")
APP_SECRET = os.getenv("META_APP_SECRET")
VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN")
PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")