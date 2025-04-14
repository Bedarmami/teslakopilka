import os
import logging
import asyncpg
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID = os.getenv("TELEGRAM_USER_ID")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add(KeyboardButton("+10 зл"), KeyboardButton("+50 зл"), KeyboardButton("+100 зл"))
keyboard.add(KeyboardButton("Баланс"), KeyboardButton("Сбросить прогресс"))

async def create_pool():
    return await asyncpg.create_pool(DATABASE_URL)

async def get_balance(conn, user_id):
    row = await conn.fetchrow("SELECT total FROM balances WHERE user_id = $1", str(user_id))
    if row:
        return row["total"]
    else:
        await conn.execute("INSERT INTO balances (user_id, total, last_update) VALUES ($1, 0, $2)", str(user_id), datetime.utcnow())
        return 0

async def update_balance(conn, user_id, amount):
    current = await get_balance(conn, user_id)
    new_total = current + amount
    await conn.execute("UPDATE balances SET total = $1, last_update = $2 WHERE user_id = $3", new_total, datetime.utcnow(), str(user_id))
    return new_total

async def reset_balance(conn, user_id):
    await conn.execute("UPDATE balances SET total = 0, last_update = $1 WHERE user_id = $2", datetime.utcnow(), str(user_id))

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    if str(message.from_user.id) != str(ALLOWED_USER_ID):
        return await message.reply("⛔ Доступ запрещён.")
    await message.reply("🚗 Добро пожаловать в Tesla Copilka!", reply_markup=keyboard)

@dp.message_handler(lambda message: message.text.startswith("+"))
async def handle_add(message: types.Message):
    if str(message.from_user.id) != str(ALLOWED_USER_ID):
        return
    try:
        amount = int(message.text.replace("+", "").replace(" зл", "").strip())
        async with db_pool.acquire() as conn:
            total = await update_balance(conn, message.from_user.id, amount)
            await message.reply(f"✅ Добавлено {amount} зл. Баланс: {total} зл.")
    except:
        await message.reply("⚠️ Ошибка обработки суммы.")

@dp.message_handler(lambda message: message.text == "Баланс")
async def handle_balance(message: types.Message):
    if str(message.from_user.id) != str(ALLOWED_USER_ID):
        return
    async with db_pool.acquire() as conn:
        total = await get_balance(conn, message.from_user.id)
        await message.reply(f"💰 Текущий баланс: {total} зл.\nЦель: 120000 зл.\nОсталось: {120000 - total} зл.")

@dp.message_handler(lambda message: message.text == "Сбросить прогресс")
async def handle_reset(message: types.Message):
    if str(message.from_user.id) != str(ALLOWED_USER_ID):
        return
    async with db_pool.acquire() as conn:
        await reset_balance(conn, message.from_user.id)
        await message.reply("🔄 Прогресс сброшен.")

# Автоотчёт
async def send_weekly_report():
    async with db_pool.acquire() as conn:
        total = await get_balance(conn, ALLOWED_USER_ID)
        remaining = 120000 - total
        await bot.send_message(ALLOWED_USER_ID, f"🗓 Еженедельный отчёт:\nТы накопил {total} зл из 120000.\nОсталось: {remaining} зл.")

scheduler = AsyncIOScheduler()
scheduler.add_job(send_weekly_report, "cron", day_of_week="mon", hour=10)

# Новый запуск с asyncio
if __name__ == "__main__":
    import asyncio

    async def main():
        global db_pool
        db_pool = await create_pool()
        scheduler.start()
        await dp.start_polling()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
