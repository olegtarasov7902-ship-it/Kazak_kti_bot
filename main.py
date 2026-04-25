import os, asyncio, random, threading
from datetime import datetime, timedelta
from flask import Flask
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "Ты — дружелюбный пират.")
REPLY_CHANCE = float(os.getenv("REPLY_CHANCE", "0.2"))

groq_client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)

# Инициализация ИИ и бота
groq_client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY")
)
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

# Инициализация Groq клиента (сделайте это ДО определения функции, где-нибудь после загрузки переменных)
groq_client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY")
)

async def get_groq_response(chat_id: int, text: str) -> str:
    if chat_id not in conversations:
        conversations[chat_id] = []

    # Добавляем сообщение пользователя в историю
    conversations[chat_id].append({"role": "user", "content": text})

    # Берём последние 20 сообщений контекста
    history = conversations[chat_id][-20:]

    # Формируем messages с системным промптом в начале
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",   # Отличная бесплатная модель, понимает русский
        messages=messages,
        temperature=0.7,
        max_tokens=100                      # Чтобы ответы были короткими, как вы любите
    )
    reply = response.choices[0].message.content

    # Сохраняем ответ бота в историю
    conversations[chat_id].append({"role": "assistant", "content": reply})
    return reply

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Здравствуйте")

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
        reply = await get_groq_response(chat_id, message.text)
        await message.reply(reply)
    except Exception as e:
        import traceback
        full_trace = traceback.format_exc()
        short_err = str(e)[:300]
        await message.reply(
            f"❌ Ошибка: {type(e).__name__}\n"
            f"📄 Текст: {short_err}\n"
            f"🔧 Первые 100 символов трейсбека:\n{full_trace[:100]}"
        )

# --- ТОЧКА ВХОДА ---
async def main():
    # Запускаем HTTP-сервер в отдельном потоке, чтобы он не мешал боту
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Запускаем поллинг бота (это работает в основном потоке)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
