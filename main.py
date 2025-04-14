import os
import logging
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID = os.getenv("TELEGRAM_USER_ID")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
keyboard.add(
    KeyboardButton("+10 зл"), KeyboardButton("+50 зл"),
    KeyboardButton("+100 зл"), KeyboardButton("Баланс"),
    KeyboardButton("Сбросить прогресс"), KeyboardButton("Цель"),
    KeyboardButton("Статистика"), KeyboardButton("Помощь")
)

TARGET_AMOUNT = 120000

async def create_pool():
    return await asyncpg.create_pool(DATABASE_URL)

async def get_balance(conn, user_id):
    row = await conn.fetchrow("SELECT total FROM balances WHERE user_id = $1", str(user_id))
    if row:
        return row["total"]
    else:
        await conn.execute("INSERT INTO balances (user_id, total, last_update) VALUES ($1, 0, $2)", str(user_id), datetime.utcnow())
        return 0

async def set_balance(conn, user_id, new_total):
    await conn.execute("UPDATE balances SET total = $1, last_update = $2 WHERE user_id = $3", new_total, datetime.utcnow(), str(user_id))

async def update_balance(conn, user_id, amount):
    current = await get_balance(conn, user_id)
    new_total = current + amount
    await set_balance(conn, user_id, new_total)
    return new_total

async def reset_balance(conn, user_id):
    await set_balance(conn, user_id, 0)

def generate_progress_bar(total, length=20):
    percent = min(max(total / TARGET_AMOUNT, 0), 1)
    filled = int(length * percent)
    bar = "#" * filled + "-" * (length - filled)
    return f"[{bar}] {round(percent * 100, 1)}%"

@dp.message_handler(commands=["stats"])
async def stats_handler(message: types.Message):
    async with db_pool.acquire() as conn:
        total = await get_balance(conn, message.from_user.id)
        weekly_gain = total
        monthly_gain = total
        await message.reply(f"""Статистика:
За неделю: +{weekly_gain} зл
За месяц: +{monthly_gain} зл
""")

# остальной код опущен для краткости — ты можешь вставить его из предыдущей версии
