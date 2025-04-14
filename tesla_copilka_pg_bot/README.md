# Tesla Copilka Bot на Python (Render + PostgreSQL)

## 🔧 Установка
1. Установи зависимости:
```
pip install -r requirements.txt
```

2. Создай `.env` файл и вставь:
```
TELEGRAM_TOKEN=токен_бота
TELEGRAM_USER_ID=твой_telegram_id
DATABASE_URL=postgresql://user:password@host:5432/teslakopilka
```

3. Запусти бота:
```
python main.py
```

## 🚀 Деплой на Render
1. Создай PostgreSQL-базу и скопируй `DATABASE_URL`
2. Запушь этот проект на GitHub
3. Создай Web Service:
   - Build command: `pip install -r requirements.txt`
   - Start command: `python main.py`
   - Добавь переменные окружения из `.env`
4. Готово!
