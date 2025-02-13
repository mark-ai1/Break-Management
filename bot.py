import asyncio
import logging
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
DAILY_STATS = {key: {"started": 0, "returned": 0, "late": 0, "fines": 0} for key in BREAK_RULES}

# Store late employees awaiting admin verification
LATE_EMPLOYEES = {}

async def reset_daily_stats():
    """Reset stats every 24 hours."""
    while True:
        await asyncio.sleep(86400)  # Wait 24 hours
        for key in DAILY_STATS:
            DAILY_STATS[key] = {"started": 0, "returned": 0, "late": 0, "fines": 0}
        logging.info("🔄 Daily stats reset.")

async def notify_admin(user, break_type):
    """Notify admin when someone is late and needs verification."""
    try:
        await bot.send_message(
            ADMIN_ID, 
            f"⚠️ {user} exceeded 15 minutes on {break_type} break!\n"
            f"📝 They must provide a reason for the delay."
        )
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

    if DAILY_STATS[break_type]["started"] >= BREAK_RULES[break_type]:
        await callback_query.answer(f"❌ {break_type} break is full. Please wait.", show_alert=True)
        return

    DAILY_STATS[break_type]["started"] += 1
    await callback_query.answer(f"✅ {username}, you started a {break_type} break!")

    await asyncio.sleep(900)  # Wait 15 minutes

    # Send return message
    DAILY_STATS[break_type]["returned"] += 1
    await bot.send_message(callback_query.message.chat.id, f"🔄 {username} has returned from their {break_type} break!")

    # Wait extra 5 minutes before marking as late
    await asyncio.sleep(300)  # 5 minutes buffer

    # Employee is now late
    DAILY_STATS[break_type]["late"] += 1
    LATE_EMPLOYEES[user_id] = {"username": username, "break_type": break_type}

    # Ask for reason
    reason_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Emergency", callback_data=f"reason_{user_id}_Emergency")],
        [InlineKeyboardButton(text="Manager Approved", callback_data=f"reason_{user_id}_ManagerApproved")],
        [InlineKeyboardButton(text="Lost Track of Time", callback_data=f"reason_{user_id}_LostTime")],
        [InlineKeyboardButton(text="Other", callback_data=f"reason_{user_id}_Other")]
    ])

    await bot.send_message(callback_query.message.chat.id, 
        f"⚠️ {username}, you are **late** from your {break_type} break!\n\n"
        "📝 Please select a reason:", reply_markup=reason_keyboard)
    
    await notify_admin(username, break_type)

@dp.callback_query(F.data.startswith("reason_"))
async def handle_reason(callback_query: CallbackQuery):
    data_parts = callback_query.data.split("_")
    user_id = int(data_parts[1])
    reason = data_parts[2]

    if user_id not in LATE_EMPLOYEES:
        await callback_query.answer("⚠️ Error: No late record found.", show_alert=True)
        return

    username = LATE_EMPLOYEES[user_id]["username"]
    break_type = LATE_EMPLOYEES[user_id]["break_type"]

    await bot.send_message(
        ADMIN_ID, 
        f"🔎 **Verification Needed**\n"
        f"👤 Employee: {username}\n"
        f"⏳ Break: {break_type}\n"
        f"📝 Reason: {reason}\n\n"
        f"✅ Approve: `/verify @{username} {reason}`\n"
        f"❌ Reject: `/reject @{username}`"
    )

    await callback_query.answer("✅ Your reason has been sent to the admin.", show_alert=True)

@dp.message(Command("verify"))
async def verify_reason(message: types.Message):
    """Admin verifies the reason (no fine applied)."""
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply("⚠️ Usage: /verify @username reason")
        return
    
    username = parts[1].lstrip("@")
    for user_id, data in LATE_EMPLOYEES.items():
        if data["username"] == username:
            del LATE_EMPLOYEES[user_id]
            await message.reply(f"✅ Reason for {username} is verified. No fine applied.")
            return

    await message.reply("⚠️ No late record found for this user.")

@dp.message(Command("reject"))
async def reject_reason(message: types.Message):
    """Admin rejects the reason (₹100 fine applied)."""
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ Usage: /reject @username")
        return
    
    username = parts[1].lstrip("@")
    for user_id, data in LATE_EMPLOYEES.items():
        if data["username"] == username:
            break_type = data["break_type"]
            DAILY_STATS[break_type]["fines"] += 1
            del LATE_EMPLOYEES[user_id]

            await bot.send_message(
                message.chat.id, 
                f"❌ {username} was **fined ₹100** for exceeding 15 minutes on {break_type} break!"
            )
            return

    await message.reply("⚠️ No late record found for this user.")

@dp.message(Command("stats"))
async def send_stats(message: types.Message):
    """Show the current daily stats."""
    stats_msg = "\n".join([
        f"🔹 {key}: Started - {value['started']}, Returned - {value['returned']}, Late - {value['late']}, Fines - {value['fines']}"
        for key, value in DAILY_STATS.items()
    ])
    await message.answer(f"📊 **Today's Break Stats:**\n\n{stats_msg}")

async def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("Bot is starting...")
    
    # Start daily stats reset task
    asyncio.create_task(reset_daily_stats())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
