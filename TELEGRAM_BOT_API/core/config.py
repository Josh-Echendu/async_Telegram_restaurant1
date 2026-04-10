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
from core.redis import redis_client
import json


# python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"


load_dotenv(Path(__file__).resolve().parent.parent / ".env")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

NGROK_DJANGO = os.getenv('NGROK_DJANGO')
NGROK_FAST_API = os.getenv('NGROK_FAST_API')


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def get_restaurant_data(update):
    user_id = update.effective_user.id
    restaurant_data = json.loads(await redis_client.get(f'user:{user_id}'))
    return restaurant_data


async def get_user_session(user_id):
    data = await redis_client.get(f"user:{user_id}")

    # convert the json string back to a dict
    return json.loads(data) if data else {}


async def save_user_session(user_id, session):

    # json.dumps(session): 👉 This converts your Python dict into a string
    await redis_client.set(f"user:{user_id}", json.dumps(session)) # '{"current_rid": "pizza_123", "table_number": 6}'
    
    check = await redis_client.get(f"user:{user_id}")
    print("Stored in Redis:", check)
    return check





async def logger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
        Logs incoming updates and context for debugging purposes.
    """
    logging.info("Received /start command: %s", context)
    logging.info("Bot details: %s", context.bot)
    logging.info("arguments: %s", context.args)
    logging.info("user_data: %s", context.chat_data)
    logging.info("Update details: %s", update)