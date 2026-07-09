import asyncio
from typing import Dict, Any, Optional
from pyrogram import Client
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait, RPCError
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from COMMON.config import SESSION_STRING, API_HASH, API_ID, PHONE_NUMBER, ADMIN_USER_ID
from TELEGRAM_BOT_API.core.config import *



# Rate limiting
RATE_LIMIT_DELAY = 2  # Seconds between API calls



from COMMON.config import SESSION_STRING

# Create Pyrogram client (shared across all functions)
app = Client(
    f"/app/sessions/{SESSION_STRING}",
    api_id=API_ID,
    api_hash=API_HASH,
    phone_number=PHONE_NUMBER
)
