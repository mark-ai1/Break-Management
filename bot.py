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

# Track employee breaks and returns
employee_breaks = {}

def is_on_break(user_id):
    return user_id in employee_breaks

def start_break(user_id, break_type):
    employee_breaks[user_id] = {"break_type": break_type, "start_time": datetime.now()}

def end_break(user_id):
    if user_id in employee_breaks:
        del employee_breaks[user_id]

async def notify_admin(user, break_type):
    await bot.send_message(ADMIN_ID, f"⚠️ {user} exceeded 15 minutes on {break_type} break!")

@dp.message(Command("start"))
async def start_command(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=bt, callback_data=f"break_{bt}")] for bt in BREAK_RULES
    ] + [[InlineKeyboardButton(text="Return", callback_data="return")]])
    
    await message.answer("👋 Welcome! Choose your break type:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("break_"))
async def handle_break(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or callback_query.from_user.full_name
    break_type = callback_query.data.split("_")[1]

    if is_on_break(user_id):
        await callback_query.answer("❌ You are already on a break! Please return first.", show_alert=True)
        return

    start_break(user_id, break_type)
    await bot.send_message(callback_query.message.chat.id, f"/{break_type.lower()}")
    await callback_query.answer(f"✅ {username}, you started a {break_type} break!")

    await asyncio.sleep(900)
    if is_on_break(user_id):
        await notify_admin(username, break_type)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Provide Reason", callback_data=f"reason_{user_id}")]
        ])
        await bot.send_message(callback_query.message.chat.id, f"⏳ {username}, you are late from {break_type} break. Provide a reason.", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("return"))
async def handle_return(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or callback_query.from_user.full_name

    if not is_on_break(user_id):
        await callback_query.answer("You are not on a break!", show_alert=True)
        return
    
    end_break(user_id)
    await bot.send_message(callback_query.message.chat.id, "/return")
    await callback_query.answer(f"✅ {username}, you have returned from your break!")

@dp.callback_query(F.data.startswith("reason_"))
async def handle_reason(callback_query: CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Approve", callback_data=f"approve_{user_id}"),
         InlineKeyboardButton(text="Fine 100 Rupees", callback_data=f"fine_{user_id}")]
    ])
    await bot.send_message(ADMIN_ID, f"🔍 Verify late return for user ID {user_id}.", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("approve_"))
async def handle_approval(callback_query: CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    await bot.send_message(user_id, "✅ Your reason has been approved. No fine applied.")
    await callback_query.answer("Approved successfully!")

@dp.callback_query(F.data.startswith("fine_"))
async def handle_fine(callback_query: CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    await bot.send_message(user_id, "⚠️ You have been fined 100 Rupees for exceeding the break time.")
    await callback_query.answer("Fine applied successfully!")

async def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
