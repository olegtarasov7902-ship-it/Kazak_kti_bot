import os
import asyncio
import random
import threading
from datetime import datetime, timedelta

# Классический HTTP-сервер на Flask для проверки порта
from flask import Flask
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from dotenv import load_dotenv
from google import genai

# Загружаем переменные окружения
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "Ты — дружелюбный пират.")
REPLY_CHANCE = float(os.getenv("REPLY_CHANCE", "0.2"))

# Инициализация ИИ и бота
client = genai.Client(api_key=GEMINI_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Переменные для диалогов
conversations = {}
last_reply_time = {}

# --- МИНИ-СЕРВЕР ДЛЯ RENDER ---
# Теперь при запуске любого GET-запроса на этот сервер он будет отвечать "OK".
# Это нужно только для того, чтобы Render видел открытый порт.
server = Flask(__name__)

@server.route('/')
def index():
    return 'Дедушка Казак на связи!', 200

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    server.run(host="0.0.0.0", port=port)

# --- ЛОГИКА БОТА (без изменений) ---
async def get_gemini_response(chat_id: int, text: str) -> str:
    if chat_id not in conversations:
        conversations[chat_id] = []

    conversations[chat_id].append({"role": "user", "parts": [text]})
    history = conversations[chat_id][-20:]

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=history,
        config={
            "system_instruction": SYSTEM_PROMPT
        }
    )
    reply = response.text
    conversations[chat_id].append({"role": "model", "parts": [reply]})
    return reply

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Здравствуйте, ребят.Казак на связи. Задавайте вопросы, только не всё сразу – это вам не школа, тут думать надо.")

@dp.message(F.text, F.chat.type.in_({"group", "supergroup"}))
async def group_message_random(message: types.Message):
    if message.from_user.is_bot:
        return

    now = datetime.now()
    chat_id = message.chat.id
    if chat_id in last_reply_time:
        if now - last_reply_time[chat_id] < timedelta(seconds=30):
            return

    if random.random() > REPLY_CHANCE:
        return

    last_reply_time[chat_id] = now
    await bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        reply = await get_gemini_response(chat_id, message.text)
        await message.reply(reply)
    except Exception as e:
        await message.reply(f"Ой, кажется шквал помешал: {type(e).__name__}")

# --- ТОЧКА ВХОДА ---
async def main():
    # Запускаем HTTP-сервер в отдельном потоке, чтобы он не мешал боту
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Запускаем поллинг бота (это работает в основном потоке)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
