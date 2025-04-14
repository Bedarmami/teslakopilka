import os
import logging
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
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
Баланс — текущий баланс
Сбросить прогресс — обнулить
Цель — прогресс к цели
Статистика — приросты

💬 Команды:
/set <сумма> — установить баланс вручную
/goal <сумма> — изменить цель
/reset — обнулить баланс
/target — прогресс к цели
/debug — ID и баланс
/stats — приросты

Можно писать вручную: +123 или -50""")

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

@dp.message_handler(commands=["reset"])
async def reset_handler(message: types.Message):
    async with db_pool.acquire() as conn:
        await reset_balance(conn, message.from_user.id)
        await message.reply("🔄 Прогресс сброшен.")

@dp.message_handler(commands=["goal"])
async def goal_handler(message: types.Message):
    global TARGET_AMOUNT
    try:
        new_goal = int(message.get_args())
        TARGET_AMOUNT = new_goal
        await message.reply(f"🎯 Новая цель установлена: {TARGET_AMOUNT} зл")
    except:
        await message.reply("⚠️ Используй: /goal 150000")

@dp.message_handler(commands=["stats"])
async def stats_handler(message: types.Message):
    async with db_pool.acquire() as conn:
        total = await get_balance(conn, message.from_user.id)
        weekly_gain = total
        monthly_gain = total
        await message.reply(
            f"📈 Статистика:
"
            f"За неделю: +{weekly_gain} зл
"
            f"За месяц: +{monthly_gain} зл"
        )

@dp.message_handler(lambda message: message.text in ["Баланс", "Цель", "Сбросить прогресс", "Статистика", "Помощь"])
async def handle_buttons(message: types.Message):
    if message.text == "Баланс":
        await target_handler(message)
    elif message.text == "Цель":
        await target_handler(message)
    elif message.text == "Сбросить прогресс":
        await reset_handler(message)
    elif message.text == "Статистика":
        await stats_handler(message)
    elif message.text == "Помощь":
        await help_handler(message)

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
