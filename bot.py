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

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # Replace with your Telegram ID
DB_CONFIG = {
    "host": "Mark0101.mysql.pythonanywhere-services.com",
    "user": "Mark0101",
    "password": "K&C63r^dx&&-mK(",
    "database": "Mark0101$default"
}

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Define break rules
BREAK_RULES = {
    "Drink": 2,
    "Toilet": 2,
    "Shopping/Smoking": 4,
    "Prayer": 2
}

def get_active_breaks(break_type):
    """Fetch active breaks from the database."""
    with mysql.connector.connect(**DB_CONFIG) as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM breaks WHERE break_type=%s AND end_time IS NULL", (break_type,))
            result = cursor.fetchone()
            return result["count"]

def start_break(user_id, username, break_type):
    """Start a break for a user."""
    with mysql.connector.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO breaks (user_id, username, break_type) VALUES (%s, %s, %s)", 
                           (user_id, username, break_type))
            conn.commit()

def end_break(user_id):
    """End a user's break."""
    with mysql.connector.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE breaks SET end_time = NOW() WHERE user_id = %s AND end_time IS NULL", (user_id,))
            conn.commit()

async def notify_admin(user, break_type):
    """Notify admin when someone exceeds 15 minutes."""
    await bot.send_message(ADMIN_ID, f"⚠️ {user} exceeded 15 minutes on {break_type} break!")

@dp.message(Command("start"))
async def start_command(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(text=bt, callback_data=f"break_{bt}") for bt in BREAK_RULES]
    keyboard.add(*buttons)
    
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
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
