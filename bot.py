import asyncio
import logging
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

# Track daily stats
DAILY_STATS = {key: 0 for key in BREAK_RULES}

async def reset_daily_stats():
    """Reset stats every 24 hours."""
    while True:
        await asyncio.sleep(86400)  # Wait 24 hours
        for key in DAILY_STATS:
            DAILY_STATS[key] = 0
        logging.info("🔄 Daily stats reset.")

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

    if DAILY_STATS[break_type] >= BREAK_RULES[break_type]:
        await callback_query.answer(f"❌ {break_type} break is full. Please wait.", show_alert=True)
        return

    DAILY_STATS[break_type] += 1
    await callback_query.answer(f"✅ {username}, you started a {break_type} break!")

    await asyncio.sleep(900)  # Wait 15 minutes
    DAILY_STATS[break_type] -= 1  # Remove user from count
    await notify_admin(username, break_type)

@dp.message(Command("stats"))
async def send_stats(message: types.Message):
    """Show the current daily stats."""
    stats_msg = "\n".join([f"🔹 {key}: {value}" for key, value in DAILY_STATS.items()])
    await message.answer(f"📊 **Today's Break Stats:**\n\n{stats_msg}")

async def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("Bot is starting...")
    
    # Start daily stats reset task
    asyncio.create_task(reset_daily_stats())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
