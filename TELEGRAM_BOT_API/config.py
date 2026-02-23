# config.py - EXACT COPY OF CONSTANTS FROM ORIGINAL FILE
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ChatPermissions  # Update → Represents an incoming update from Telegram, like a message or command.
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackContext # ContextTypes → Provides the context for the message or chat, like info about who sent it, what chat it came from, etc.
from telegram.ext import MessageHandler, filters, CallbackQueryHandler
from telegram.ext import ChatMemberHandler
import logging
from telegram import ReplyKeyboardRemove, WebAppInfo
from telegram import ChatMember
import asyncio
import zipfile
from telegram import InputFile
import shutil
import glob
from telegram import Update
from telegram.ext import ContextTypes
from telegram.ext import ApplicationHandlerStop
import os
from telegram import InputFile, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import MenuButtonWebApp, WebAppInfo
import httpx
import asyncio
from telegram import Bot, Update
from decimal import Decimal
import os
from dotenv import load_dotenv
from pathlib import Path
from redis_client import redis_client


# python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"


load_dotenv(Path(__file__).resolve().parent.parent / ".env")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def get_cart_items(update, max_retries=3):
    user = update.effective_user
    telegram_id = int(user.id)
    print("telegram_id for get_cart_items: ", telegram_id)

    for attempt in range(1, int(max_retries + 1)):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"http://web:8000/api/cart_list/{telegram_id}/",
                    headers={"Accept": "application/json"}  # ask for JSON explicitly
                )
                response.raise_for_status()
                # print("Cart List Response text:", response.text)
                print("Cart List Response:", response.json())
                response_json = response.json()
                return response_json

        except (httpx.RequestError, httpx.HTTPStatusError, ValueError, Exception) as e:
            logging.warning(f"Attempt {attempt} failed for retrieving cart items: {e}")
            
            if attempt == max_retries:
                logging.error(f"All {max_retries} attempts failed for retrieving cart items: {e}")
                return None
            
            # optional: wait before retrying
            await asyncio.sleep(1)