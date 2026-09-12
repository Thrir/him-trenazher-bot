import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

import database as db

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 980227176

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

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
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав администратора.")
        return
    
    await message.answer(
        "🛠 **Панель Репетитора**\n\n"
        "Чтобы добавить вещества массово, отправь сообщение списком в формате:\n"
        "`Формула | Название | Категория`\n\n"
        "Пример:\n"
        "`H2SO4 | Серная кислота | Кислоты`\n"
        "`NaOH | Едкий натр | Основания`",
        parse_mode="Markdown"
    )

@dp.message(F.text.contains("|"))
async def process_bulk_input(message: types.Message):
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
            
    if count > 0:
        await message.answer(f"✅ Успешно добавлено веществ: {count}", reply_markup=get_main_keyboard())

@dp.message(F.text == "🧪 Тренажёр")
async def choose_category(message: types.Message):
    categories = db.get_categories()
    
    buttons = [[InlineKeyboardButton(text="🎯 Все категории", callback_data="cat_все")]]
    for cat in categories:
        buttons.append([InlineKeyboardButton(text=f"🔬 {cat}", callback_data=f"cat_{cat}")])
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выбери категорию веществ для тренировки:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("cat_"))
async def start_quiz_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.split("cat_")[1]
    await state.update_data(current_category=category)
    await send_next_question(callback.message, state)

async def send_next_question(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category = data.get("current_category", "все")
    
    substance, options = db.get_random_question(category)
    if not substance:
        await message.answer("В этой категории пока нет веществ!")
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
    
    await send_next_question(callback.message, state)

@dp.message(F.text == "📊 Мой прогресс")
async def show_progress(message: types.Message):
    total, correct, percent = db.get_user_stats(message.from_user.id)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔄 Сбросить прогресс", callback_data="reset_stats")]]
    )
    
    await message.answer(
        f"📊 **Ваша статистика**\n\n"
        f"🎯 Всего ответов: {total}\n"
        f"✅ Правильных: {correct}\n"
        f"📈 Точность: {percent}%",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "reset_stats")
async def reset_stats_handler(callback: types.CallbackQuery):
    db.reset_user_stats(callback.from_user.id)
    await callback.answer("Статистика сброшена!")
    await callback.message.edit_text("🔄 Ваша статистика была успешно сброшена.")

async def handle_ping(request):
    return web.Response(text="Bot is active")

async def main():
    db.init_db()
    
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
