import asyncio
import logging
import mysql.connector
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Retrieve credentials securely
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))  # Default to 0 if not set
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}

# Initialize bot and dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Define break rules
BREAK_RULES = {
    "Drink": 2,
    "Toilet": 2,
    "Shopping/Smoking": 4,
    "Prayer": 2
}

def connect_db():
    """Create a new database connection."""
    return mysql.connector.connect(**DB_CONFIG)

def get_active_breaks(break_type):
    """Fetch active breaks from the database."""
    try:
        with connect_db() as conn, conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM breaks WHERE break_type=%s AND end_time IS NULL", (break_type,))
            result = cursor.fetchone()
            return result["count"]
    except Exception as e:
        logging.error(f"Database error: {e}")
        return 0

def start_break(user_id, username, break_type):
    """Start a break for a user."""
    try:
        with connect_db() as conn, conn.cursor() as cursor:
            cursor.execute("INSERT INTO breaks (user_id, username, break_type, start_time) VALUES (%s, %s, %s, NOW())", 
                           (user_id, username, break_type))
            conn.commit()
    except Exception as e:
        logging.error(f"Database error: {e}")

def end_break(user_id):
    """End a user's break."""
    try:
        with connect_db() as conn, conn.cursor() as cursor:
            cursor.execute("UPDATE breaks SET end_time = NOW() WHERE user_id = %s AND end_time IS NULL", (user_id,))
            conn.commit()
    except Exception as e:
        logging.error(f"Database error: {e}")

async def notify_admin(user, break_type):
    """Notify admin when someone exceeds 15 minutes."""
    try:
        await bot.send_message(ADMIN_ID, f"⚠️ {user} exceeded 15 minutes on {break_type} break!")
    except Exception as e:
        logging.error(f"Failed to notify admin: {e}")

@dp.message(Command("start"))
async def start_command(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=bt, callback_data=f"break_{bt}")] for bt in BREAK_RULES
    ])
    
    await message.answer("👋 Welcome! Choose your break type:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("break_"))
async def handle_break(callback_query: CallbackQuery):
    break_type = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or callback_query.from_user.full_name

    if get_active_breaks(break_type) >= BREAK_RULES[break_type]:
        await callback_query.answer(f"❌ {break_type} break is full. Please wait.", show_alert=True)
        return

    start_break(user_id, username, break_type)
    await callback_query.answer(f"✅ {username}, you started a {break_type} break!")

    await asyncio.sleep(900)  # Wait 15 minutes
    end_break(user_id)
    await notify_admin(username, break_type)

async def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
