import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from dotenv import load_dotenv
import os
import time

# Load environment variables
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))  

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

BREAK_RULES = {
    "Drink": 2,
    "Toilet": 2,
    "Shopping/Smoking": 4,
    "Prayer": 2
}

BREAK_TRACKER = {}

async def notify_admin_late(user, break_type):
    """Notify admin when an employee is late returning."""
    await bot.send_message(
        ADMIN_ID, 
        f"⚠️ {user} is **late** from their {break_type} break!\n"
        "📝 They must select a reason."
    )

@dp.message(Command("start"))
async def start_command(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=bt, callback_data=f"break_{bt}")] for bt in BREAK_RULES
    ])
    await message.answer("👋 Choose your break:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("break_"))
async def handle_break(callback_query: CallbackQuery):
    break_type = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or callback_query.from_user.full_name

    if BREAK_RULES[break_type] == 0:
        await callback_query.answer(f"❌ {break_type} break is full.", show_alert=True)
        return

    BREAK_RULES[break_type] -= 1
    BREAK_TRACKER[user_id] = {"break_type": break_type, "start_time": time.time(), "returned": False}

    return_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚶 Return", callback_data=f"return_{user_id}")]
    ])

    await callback_query.message.answer(
        f"✅ {username}, you started a **{break_type}** break.\n"
        "⏳ Click 'Return' when you're back!", reply_markup=return_keyboard
    )

    await asyncio.sleep(900)  # Wait 15 minutes

    if user_id in BREAK_TRACKER and not BREAK_TRACKER[user_id]["returned"]:
        await notify_admin_late(username, break_type)

@dp.callback_query(F.data.startswith("return_"))
async def handle_return(callback_query: CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    if user_id not in BREAK_TRACKER:
        await callback_query.answer("⚠️ No active break found.", show_alert=True)
        return

    username = callback_query.from_user.username or callback_query.from_user.full_name
    break_type = BREAK_TRACKER[user_id]["break_type"]
    elapsed_time = time.time() - BREAK_TRACKER[user_id]["start_time"]

    if elapsed_time > 900:
        reason_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Emergency", callback_data=f"reason_{user_id}_Emergency")],
            [InlineKeyboardButton(text="Manager Approved", callback_data=f"reason_{user_id}_ManagerApproved")],
            [InlineKeyboardButton(text="Lost Track of Time", callback_data=f"reason_{user_id}_LostTime")],
            [InlineKeyboardButton(text="Other", callback_data=f"reason_{user_id}_Other")]
        ])
        await callback_query.message.answer(
            f"⚠️ {username}, you **exceeded 15 minutes** on your {break_type} break!\n"
            "📝 Select a reason:", reply_markup=reason_keyboard
        )
    else:
        await callback_query.message.answer(f"✅ {username} **returned** from {break_type} break on time!")

    BREAK_RULES[break_type] += 1
    BREAK_TRACKER[user_id]["returned"] = True

@dp.callback_query(F.data.startswith("reason_"))
async def handle_reason(callback_query: CallbackQuery):
    data_parts = callback_query.data.split("_")
    user_id = int(data_parts[1])
    reason = data_parts[2]

    username = callback_query.from_user.username or callback_query.from_user.full_name
    break_type = BREAK_TRACKER[user_id]["break_type"]

    await bot.send_message(
        ADMIN_ID, 
        f"🔎 **Verification Needed**\n"
        f"👤 Employee: {username}\n"
        f"⏳ Break: {break_type}\n"
        f"📝 Reason: {reason}\n\n"
        f"✅ Approve: `/verify @{username} {reason}`\n"
        f"❌ Reject: `/reject @{username}`"
    )

@dp.message(Command("verify"))
async def verify_reason(message: types.Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply("⚠️ Usage: /verify @username reason")
        return
    
    username = parts[1].lstrip("@")
    await message.reply(f"✅ Reason for {username} **approved**. No fine applied.")

@dp.message(Command("reject"))
async def reject_reason(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ Usage: /reject @username")
        return
    
    username = parts[1].lstrip("@")
    await message.reply(f"❌ {username} was **fined ₹100** for exceeding 15 minutes.")

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
