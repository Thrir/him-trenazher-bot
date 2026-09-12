import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

import database as db

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 980227176  # Твой Telegram ID

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Машины состояний
class AdminStates(StatesGroup):
    waiting_for_bulk_input = State()

class QuizStates(StatesGroup):
    answering = State()

# Клавиатуры
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧪 Тренажёр"), KeyboardButton(text="📊 Мой прогресс")]
        ],
        resize_keyboard=True
    )

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    db.add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n\n"
        "Добро пожаловать в ХимТренажёр.\n"
        "Здесь ты сможешь легко выучить тривиальные названия химических веществ!",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав администратора.")
        return
    
    await state.set_state(AdminStates.waiting_for_bulk_input)
    await message.answer(
        "🛠 **Панель Репетитора**\n\n"
        "Чтобы добавить вещества массово, отправь сообщение списком в формате:\n"
        "`Формула | Название | Категория`\n\n"
        "Пример:\n"
        "`H2SO4 | Серная кислота | Кислоты`\n"
        "`NaOH | Едкий натр | Основания`",
        parse_mode="Markdown"
    )

@dp.message(AdminStates.waiting_for_bulk_input)
async def process_bulk_input(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    lines = message.text.strip().split('\n')
    count = 0
    for line in lines:
        parts = [p.strip() for p in line.split('|')]
        if len(parts) == 3:
            formula, name, category = parts
            db.add_substance(formula, name, category)
            count += 1
            
    await state.clear()
    await message.answer(f"✅ Успешно добавлено веществ: {count}", reply_markup=get_main_keyboard())

@dp.message(F.text == "🧪 Тренажёр")
async def start_quiz(message: types.Message, state: FSMContext):
    substance, options = db.get_random_question(message.from_user.id)
    if not substance:
        await message.answer("База знаний пока пуста или ты уже выучил все вещества!")
        return

    await state.update_data(correct_id=substance['id'])
    
    buttons = [
        [InlineKeyboardButton(text=opt, callback_data=f"ans_{opt}")] for opt in options
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.answer(
        f"🧪 Какое тривиальное название у вещества: **{substance['formula']}**?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("ans_"))
async def handle_answer(callback: types.CallbackQuery, state: FSMContext):
    user_answer = callback.data.split("ans_")[1]
    data = await state.get_data()
    correct_id = data.get("correct_id")
    
    substance = db.get_substance_by_id(correct_id)
    if not substance:
        await callback.answer("Ошибка вопроса.")
        return

    is_correct = (user_answer == substance['name'])
    db.record_attempt(callback.from_user.id, correct_id, is_correct)
    
    if is_correct:
        await callback.message.edit_text(f"✅ Верно! **{substance['formula']}** — это **{substance['name']}**.", parse_mode="Markdown")
    else:
        await callback.message.edit_text(f"❌ Неправильно. Правильный ответ: **{substance['name']}**.", parse_mode="Markdown")
    
    await start_quiz(callback.message, state)

# Фейковый веб-сервер для ублажения Render Web Service
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def main():
    db.init_db()
    
    # Запуск веб-сервера на порту от Render
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
