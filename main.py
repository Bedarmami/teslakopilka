import os
import logging
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID = os.getenv("TELEGRAM_USER_ID")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add(
    KeyboardButton("+10 зл"), KeyboardButton("+50 зл"), KeyboardButton("+100 зл"),
    KeyboardButton("Баланс"), KeyboardButton("Сбросить прогресс")
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

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    await message.reply("👋 Привет! Я твоя Tesla-копилка. Готов считать злоты!", reply_markup=keyboard)

@dp.message_handler(lambda message: message.text == "Баланс")
async def handle_balance(message: types.Message):
    async with db_pool.acquire() as conn:
        total = await get_balance(conn, message.from_user.id)
        await message.reply(f"💰 Баланс: {total} зл.
Цель: {TARGET_AMOUNT} зл.")

@dp.message_handler(lambda message: message.text == "Сбросить прогресс")
async def handle_reset(message: types.Message):
    async with db_pool.acquire() as conn:
        await reset_balance(conn, message.from_user.id)
        await message.reply("🔄 Баланс сброшен.")

@dp.message_handler()
async def handle_custom_amount(message: types.Message):
    try:
        amount = int(message.text.replace(" зл", "").strip())
        async with db_pool.acquire() as conn:
            new_total = await update_balance(conn, message.from_user.id, amount)
            await message.reply(f"✅ Добавлено {amount} зл. Новый баланс: {new_total} зл.")
    except:
        await message.reply("⚠️ Введите сумму в формате +100 или -50")

if __name__ == "__main__":
    import asyncio

    async def main():
        print("🚀 Бот запущен.")
        global db_pool
        db_pool = await create_pool()
        scheduler = AsyncIOScheduler()
        scheduler.start()
        await dp.start_polling()

    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except Exception as e:
        print("❌ Ошибка запуска:", e)
