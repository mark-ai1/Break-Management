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

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Define break rules and tracking
BREAK_RULES = {"Drink": 2, "Toilet": 2, "Shopping/Smoking": 4, "Prayer": 2}
user_breaks = {}  # {user_id: {"break_type": str, "start_time": datetime}}

@dp.message(Command("start"))
async def start_command(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=bt, callback_data=f"break_{bt}")] for bt in BREAK_RULES
    ])
    await message.answer("👋 Welcome! Choose your break type:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("break_"))
async def handle_break(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or callback_query.from_user.full_name
    break_type = callback_query.data.split("_")[1]
    
    if user_id in user_breaks:
        await callback_query.answer("⚠️ You are already on a break. Return first!", show_alert=True)
        return

    user_breaks[user_id] = {"break_type": break_type, "start_time": datetime.now()}
    
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Return", callback_data="return")
    )
    await callback_query.message.edit_text(f"✅ {username}, you started a {break_type} break!", reply_markup=keyboard)
    await asyncio.sleep(900)
    
    if user_id in user_breaks:
        await bot.send_message(ADMIN_ID, f"⚠️ {username} exceeded 15 minutes on {break_type} break! Waiting for return.")
        await bot.send_message(user_id, "⚠️ You exceeded 15 minutes! Select a reason:",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                   [InlineKeyboardButton("Emergency", callback_data="reason_emergency")],
                                   [InlineKeyboardButton("Work Delay", callback_data="reason_work")],
                                   [InlineKeyboardButton("Other", callback_data="reason_other")]
                               ]))

@dp.callback_query(F.data.startswith("return"))
async def handle_return(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in user_breaks:
        await callback_query.answer("⚠️ You are not on a break!", show_alert=True)
        return
    
    del user_breaks[user_id]
    await callback_query.message.edit_text("✅ You have successfully returned from break!")

@dp.callback_query(F.data.startswith("reason_"))
async def handle_late_reason(callback_query: CallbackQuery):
    reason = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or callback_query.from_user.full_name
    
    await bot.send_message(ADMIN_ID, f"🚨 {username} is late. Reason: {reason.upper()}.",
                           reply_markup=InlineKeyboardMarkup().add(
                               InlineKeyboardButton("Verify", callback_data=f"verify_{user_id}")
                           ))
    await callback_query.message.edit_text("⏳ Waiting for admin approval...")

@dp.callback_query(F.data.startswith("verify_"))
async def handle_verification(callback_query: CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    if user_id in user_breaks:
        await bot.send_message(user_id, "✅ Your late return was verified. No fine applied.")
    else:
        await bot.send_message(user_id, "❌ Your late return was not verified. A fine of 100 Rupees is applied!")

async def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
