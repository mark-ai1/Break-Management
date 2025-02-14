import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from dotenv import load_dotenv
import os
import sqlite3

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))  # Default to 0 if not set

# Initialize bot and dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Define break rules and tracking
BREAK_RULES = {
    "Drink": 2,
    "Toilet": 2,
    "Shopping/Smoking": 4,
    "Prayer": 2
}

# Database setup
def init_db():
    conn = sqlite3.connect('breaks.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS breaks
                 (user_id INTEGER, username TEXT, break_type TEXT, start_time TEXT, end_time TEXT, duration INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# Create keyboard with break options
def get_break_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=bt, callback_data=f"break_{bt}")] for bt in BREAK_RULES
    ])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="Return", callback_data="return")])
    return keyboard

async def notify_admin(user, break_type):
    await bot.send_message(ADMIN_ID, f"⚠️ {user} exceeded 15 minutes on {break_type} break!")

@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer("👋 Welcome! Choose your break type:", reply_markup=get_break_keyboard())

@dp.callback_query(F.data.startswith("break_"))
async def handle_break(callback_query: CallbackQuery):
    break_type = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or callback_query.from_user.full_name
    
    conn = sqlite3.connect('breaks.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM breaks WHERE break_type = ? AND end_time IS NULL", (break_type,))
    count = c.fetchone()[0]
    
    if count >= BREAK_RULES[break_type]:
        await callback_query.answer(f"❌ {break_type} break is full. Please wait.", show_alert=True)
        conn.close()
        return
    
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO breaks (user_id, username, break_type, start_time) VALUES (?, ?, ?, ?)",
              (user_id, username, break_type, start_time))
    conn.commit()
    conn.close()
    
    await callback_query.answer(f"✅ {username}, you started a {break_type} break!", show_alert=True)
    await bot.send_message(callback_query.message.chat.id, f"/{break_type.lower()}")
    
    await asyncio.sleep(900)  # Wait 15 minutes
    conn = sqlite3.connect('breaks.db')
    c = conn.cursor()
    c.execute("SELECT * FROM breaks WHERE user_id = ? AND end_time IS NULL", (user_id,))
    if c.fetchone():
        await notify_admin(username, break_type)
    conn.close()

@dp.callback_query(F.data == "return")
async def handle_return(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or callback_query.from_user.full_name
    
    conn = sqlite3.connect('breaks.db')
    c = conn.cursor()
    c.execute("SELECT * FROM breaks WHERE user_id = ? AND end_time IS NULL", (user_id,))
    break_data = c.fetchone()
    
    if not break_data:
        await callback_query.answer("⚠️ You are not on a break!", show_alert=True)
        conn.close()
        return
    
    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start_time = datetime.strptime(break_data[3], "%Y-%m-%d %H:%M:%S")
    duration = (datetime.now() - start_time).seconds
    
    c.execute("UPDATE breaks SET end_time = ?, duration = ? WHERE user_id = ? AND end_time IS NULL",
              (end_time, duration, user_id))
    conn.commit()
    conn.close()
    
    if duration > 900:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Verify Reason", callback_data=f"verify_{user_id}")]
        ])
        await bot.send_message(ADMIN_ID, f"⚠️ {username} was late from {break_data[2]} break. Verify reason?", reply_markup=keyboard)
    else:
        await callback_query.answer("✅ You have returned from your break.", show_alert=True)
    
    await bot.send_message(callback_query.message.chat.id, "/return")

@dp.callback_query(F.data.startswith("verify_"))
async def verify_reason(callback_query: CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    await bot.send_message(user_id, "✅ Your late return has been verified by the admin. No fine applied.")
    await callback_query.answer("Verified. No fine applied.", show_alert=True)

@dp.message(Command("history"))
async def history_command(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect('breaks.db')
    c = conn.cursor()
    c.execute("SELECT * FROM breaks WHERE user_id = ?", (user_id,))
    breaks = c.fetchall()
    conn.close()
    
    if not breaks:
        await message.answer("No break history found.")
        return
    
    history_text = "Your break history:\n"
    for break_data in breaks:
        history_text += f"{break_data[2]} - {break_data[3]} to {break_data[4]} ({break_data[5]} seconds)\n"
    
    await message.answer(history_text)

async def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
