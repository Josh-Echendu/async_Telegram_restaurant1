import logging
import asyncio
from typing import Dict, Any, Optional
from pyrogram import Client
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait, RPCError
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from COMMON.config import *



# Rate limiting
RATE_LIMIT_DELAY = 2  # Seconds between API calls

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Create Pyrogram client (shared across all functions)
app = Client(
    SESSION_STRING,
    api_id=API_ID,
    api_hash=API_HASH,
    phone_number=PHONE_NUMBER
)