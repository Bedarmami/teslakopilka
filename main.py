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

keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add(KeyboardButton("+10 зл"), KeyboardButton("+50 зл"), KeyboardButton("+100 зл"))
keyboard.add(KeyboardButton("Баланс"), KeyboardButton("Сбросить прогресс"))

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
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {round(percent * 100, 1)}%"

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    if str(message.from_user.id) != str(ALLOWED_USER_ID):
        return await message.reply("⛔ Доступ запрещён.")
    await message.reply("🚗 Добро пожаловать в Tesla Copilka!", reply_markup=keyboard)

@dp.message_handler(commands=["help"])
async def help_handler(message: types.Message):
    await message.reply("""Привет! 👋 Это твоя Tesla-копилка.

🟢 Кнопки:
+10 / +50 / +100 — пополнить
Баланс — показать баланс
Сбросить прогресс — обнулить

💬 Команды:
/set <сумма> — установить баланс вручную
/target — прогресс к цели
/debug — тех. информация
Можно писать вручную +123 или -50""")

@dp.message_handler(commands=["debug"])
async def debug_handler(message: types.Message):
    async with db_pool.acquire() as conn:
        total = await get_balance(conn, message.from_user.id)
        await message.reply(f"[DEBUG]\nID: {message.from_user.id}\nБаланс: {total} зл.")

@dp.message_handler(commands=["target"])
async def target_handler(message: types.Message):
    async with db_pool.acquire() as conn:
        total = await get_balance(conn, message.from_user.id)
        left = TARGET_AMOUNT - total
        bar = generate_progress_bar(total)
        await message.reply(f"📊 Накоплено: {total} зл\nОсталось: {left} зл\nПрогресс:\n{bar}")

@dp.message_handler(commands=["set"])
async def set_handler(message: types.Message):
    try:
        value = int(message.get_args())
        async with db_pool.acquire() as conn:
            await set_balance(conn, message.from_user.id, value)
            await message.reply(f"✅ Баланс установлен: {value} зл.")
    except:
        await message.reply("⚠️ Используй: /set 12345")

@dp.message_handler(lambda message: message.text == "Баланс")
async def handle_balance(message: types.Message):
    async with db_pool.acquire() as conn:
        total = await get_balance(conn, message.from_user.id)
        bar = generate_progress_bar(total)
        await message.reply(f"💰 Баланс: {total} зл\nЦель: {TARGET_AMOUNT} зл\nОсталось: {TARGET_AMOUNT - total} зл\n{bar}")

@dp.message_handler(lambda message: message.text == "Сбросить прогресс")
async def handle_reset(message: types.Message):
    async with db_pool.acquire() as conn:
        await reset_balance(conn, message.from_user.id)
        await message.reply("🔄 Прогресс сброшен.")

@dp.message_handler()
async def handle_manual_input(message: types.Message):
    text = message.text.strip().replace(" зл", "")
    try:
        amount = int(text)
        async with db_pool.acquire() as conn:
            new_total = await update_balance(conn, message.from_user.id, amount)
            bar = generate_progress_bar(new_total)
            if amount >= 0:
                await message.reply(f"✅ Добавлено {amount} зл.\nБаланс: {new_total} зл.\n{bar}")
            else:
                await message.reply(f"💸 Списано {abs(amount)} зл.\nБаланс: {new_total} зл.\n{bar}")
    except:
        pass

# Отчёт за неделю и месяц (упрощённый)
async def send_weekly_report():
    async with db_pool.acquire() as conn:
        current_total = await get_balance(conn, ALLOWED_USER_ID)
        weekly_gain = current_total
        monthly_gain = current_total
        left = TARGET_AMOUNT - current_total
        bar = generate_progress_bar(current_total)

        await bot.send_message(ALLOWED_USER_ID, f"""🗓 Отчёт:
📅 За неделю: +{weekly_gain} зл
🗓 За месяц: +{monthly_gain} зл
🎯 Осталось до цели: {left} зл
{bar}
""")

scheduler = AsyncIOScheduler()
scheduler.add_job(send_weekly_report, "cron", day_of_week="mon", hour=10)

if __name__ == "__main__":
    import asyncio

    async def main():
        global db_pool
        db_pool = await create_pool()
        scheduler.start()
        await dp.start_polling()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
