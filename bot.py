import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# Initialize bot and dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Define break rules and tracking
daily_breaks = {}
return_status = {}
BREAK_RULES = {"Drink": 2, "Toilet": 2, "Shopping/Smoking": 4, "Prayer": 2}

# Helper functions
def get_active_breaks(break_type):
    return sum(1 for status in daily_breaks.values() if status == break_type)

def user_on_break(user_id):
    return user_id in daily_breaks

def user_returned(user_id):
    return user_id in return_status and return_status[user_id]

async def notify_admin(user, break_type):
    await bot.send_message(ADMIN_ID, f"⚠️ {user} exceeded 15 minutes on {break_type} break! Waiting for reason.")

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

    if user_on_break(user_id):
        await callback_query.answer("❌ You are already on a break! Return first.", show_alert=True)
        return

    if get_active_breaks(break_type) >= BREAK_RULES[break_type]:
        await callback_query.answer(f"❌ {break_type} break is full. Please wait.", show_alert=True)
        return

    daily_breaks[user_id] = break_type
    return_status[user_id] = False
    await callback_query.answer(f"✅ {username}, you started a {break_type} break!\n/break_{break_type}")
    await asyncio.sleep(900)
    if user_on_break(user_id):
        await notify_admin(username, break_type)

@dp.callback_query(F.data == "return")
async def handle_return(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or callback_query.from_user.full_name
    
    if not user_on_break(user_id):
        await callback_query.answer("❌ You are not on a break!", show_alert=True)
        return

    if user_returned(user_id):
        await callback_query.answer("⚠️ You have already returned.", show_alert=True)
        return

    return_status[user_id] = True
    del daily_breaks[user_id]
    await callback_query.answer(f"✅ {username}, you have returned from your break.\n/return")

async def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
