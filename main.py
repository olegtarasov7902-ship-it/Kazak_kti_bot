import os
import asyncio
import random
from datetime import datetime, timedelta

# ---------- ИЗМЕНЕНИЕ 1: правильный импорт Command и фильтров ----------
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command         # <-- теперь корректно
from dotenv import load_dotenv

# ---------- ИЗМЕНЕНИЕ 2: новая библиотека Google ----------
from google import genai                     # <-- вместо google.generativeai

# Загружаем переменные из локального .env (для тестов на своём ПК)
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "Ты — дружелюбный пират.")
REPLY_CHANCE = float(os.getenv("REPLY_CHANCE", "0.2"))

# ---------- ИЗМЕНЕНИЕ 3: новый способ настройки Gemini ----------
# Создаём клиент (ключ передаём явно, как у тебя было в переменной)
client = genai.Client(api_key=GEMINI_API_KEY)

# Хранилище истории диалогов (ключ: chat_id, значение: список сообщений)
conversations = {}

# Время последнего ответа для флуд-контроля
last_reply_time = {}

# Функция получения ответа от Gemini с учётом истории и system prompt
async def get_gemini_response(chat_id: int, text: str) -> str:
    if chat_id not in conversations:
        conversations[chat_id] = []

    # Добавляем сообщение пользователя в историю
    conversations[chat_id].append({"role": "user", "parts": [text]})

    # Оставляем только последние 20 сообщений, чтобы не перегружать модель
    history = conversations[chat_id][-20:]

    # ---------- ИЗМЕНЕНИЕ 4: вызов через client.models.generate_content ----------
    response = client.models.generate_content(
        model="gemini-2.0-flash",            # актуальная бесплатная модель
        contents=history,
        config={
            "system_instruction": SYSTEM_PROMPT   # характер задаётся здесь
        }
    )
    reply = response.text

    # Сохраняем ответ бота в истории
    conversations[chat_id].append({"role": "model", "parts": [reply]})
    return reply

# Создаём бота и диспетчер
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Команда /start для личных сообщений (можно использовать для проверки)
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Здравствуйте, ребят.Казак на связи. Задавайте вопросы, только не всё сразу – это вам не школа, тут думать надо.")

# Основной обработчик для групп
@dp.message(F.text, F.chat.type.in_({"group", "supergroup"}))
async def group_message_random(message: types.Message):
    # 1. Игнорируем сообщения от любых ботов
    if message.from_user.is_bot:
        return

    # 2. Проверка флуд-контроля: не чаще одного ответа в 30 секунд
    now = datetime.now()
    chat_id = message.chat.id
    if chat_id in last_reply_time:
        if now - last_reply_time[chat_id] < timedelta(seconds=30):
            return  # ещё рано

    # 3. Случайный шанс ответа (по умолчанию 20%)
    if random.random() > REPLY_CHANCE:
        return

    # 4. Мы будем отвечать — фиксируем время
    last_reply_time[chat_id] = now

    # Отправляем индикатор "печатает" (опционально, но приятно)
    await bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        reply = await get_gemini_response(chat_id, message.text)
        await message.reply(reply)
    except Exception as e:
        await message.reply(f"Ой, кажется шквал помешал: {type(e).__name__}")

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())