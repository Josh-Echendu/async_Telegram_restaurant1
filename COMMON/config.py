import os
from dotenv import load_dotenv
from pathlib import Path
import logging

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
REDIS_URL = os.getenv("REDIS_URL")

NGROK_DJANGO = os.getenv("NGROK_DJANGO")
NGROK_FAST_API = os.getenv("NGROK_FAST_API")


# pyrogram config !!!!
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
SESSION_STRING = os.getenv("SESSION_STRING")



# whatsapp verify token
VERIFY_TOKEN = os.getenv('META_VERIFY_TOKEN')

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

