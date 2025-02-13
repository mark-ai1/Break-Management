import asyncio
import logging
import time
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))  

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

BREAK_RULES = {
    "Drink پینا": 2,
    "Toilet باتھروم": 2,
    "Shopping/Smoking سوکنگ / شاپنگ": 4,
    "Prayer نماز": 2
}

BREAK_TRACKER = {}

async def notify_admin_late(user, break_type):
    """Notify admin when an employee is late returning."""
    await bot.send_message(
        ADMIN_ID, 
        f"\u26a0\ufe0f {user} is **late** from their {break_type} break!\n"
        "\U0001F4DD They must select a reason."
    )

@dp.message(Command("start"))
async def start_command(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=bt, callback_data=f"break_{bt}")] for bt in BREAK_RULES
    ])
    await message.answer("\U0001F44B Choose your break: \U0001F44C \n\n" 
                         "\U0001F449 \U0001F6B0 Drink \u067e\u06cc\u0646\u0627" 
                         "\n\U0001F449 \U0001F6BD Toilet \u0628\u0627\u062a\u06be\u0631\u0648\u0645" 
                         "\n\U0001F449 \U0001F6CD Shopping/Smoking \u0633\u0648\u06a9\u0646\u06af / \u0634\u0627\u067e\u0646\u06af" 
                         "\n\U0001F449 \U0001F64F Prayer \u0646\u0645\u0627\u0632", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("break_"))
async def handle_break(callback_query: CallbackQuery):
    break_type = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or callback_query.from_user.full_name

    if BREAK_RULES[break_type] == 0:
        await callback_query.answer(f"\u274C {break_type} break is full.", show_alert=True)
        return

    BREAK_RULES[break_type] -= 1
    BREAK_TRACKER[user_id] = {"break_type": break_type, "start_time": time.time(), "returned": False}

    return_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001F6B6 Return \u0648\u0627\u0679\u0633 ", callback_data=f"return_{user_id}")]
    ])

    await callback_query.message.answer(
        f"\u2705 {username}, you started a **{break_type}** break.\n"
        "⏳ Click 'Return' when you're back!", reply_markup=return_keyboard
    )

    await asyncio.sleep(900)

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
            [InlineKeyboardButton(text="Emergency \u0627\u06be\u0645 \u0635\u0648\u0631\u062a \u062d\u0627\u0644", callback_data=f"reason_{user_id}_Emergency")],
            [InlineKeyboardButton(text="Manager Approved \u0645\u0646\u0638\u0648\u0631 \u0634\u062f\u06c1", callback_data=f"reason_{user_id}_ManagerApproved")],
            [InlineKeyboardButton(text="Lost Track of Time \u0648\u0642\u062a \u0646\u06cc\u06ba \u062f\u06be\u06cc\u0627", callback_data=f"reason_{user_id}_LostTime")],
            [InlineKeyboardButton(text="Other \u062f\u0648\u0633\u0631\u0627", callback_data=f"reason_{user_id}_Other")]
        ])
        await callback_query.message.answer(
            f"⚠️ {username}, you **exceeded 15 minutes** on your {break_type} break!\n"
            "📝 Select a reason:", reply_markup=reason_keyboard
        )
    else:
        await callback_query.message.answer(f"✅ {username} **returned** from {break_type} break on time!")

    BREAK_RULES[break_type] += 1
    BREAK_TRACKER[user_id]["returned"] = True

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
