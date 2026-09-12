import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

import database as db

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 980227176

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

WEBHOOK_SERVER_HOST = "https://him-trenazher-bot.onrender.com"
WEBHOOK_PATH = f"/bot/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_SERVER_HOST}{WEBHOOK_PATH}"

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧪 Тренажёр"), KeyboardButton(text="📊 Мой прогресс")]
        ],
        resize_keyboard=True
    )

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    logger.info(f"Получена команда /start от пользователя {message.from_user.id}")
    await db.add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
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
            await db.add_substance(formula, name, category)
            count += 1
              
    if count > 0:
        await message.answer(f"✅ Успешно добавлено веществ: {count}", reply_markup=get_main_keyboard())

@dp.message(F.text == "🧪 Тренажёр")
async def choose_category(message: types.Message):
    logger.info(f"Пользователь {message.from_user.id} нажал кнопку '🧪 Тренажёр'")
    categories = await db.get_categories()
    logger.info(f"Получены категории из БД: {categories}")
      
    buttons = [[InlineKeyboardButton(text="🎯 Все категории", callback_data="cat_все")]]
    for cat in categories:
        buttons.append([InlineKeyboardButton(text=f"🔬 {cat}", callback_data=f"cat_{cat}")])
          
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выбери категорию веществ для тренировки:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("cat_"))
async def start_quiz_category(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    category = callback.data.split("cat_", 1)[1]
    logger.info(f"CALLBACK cat_: Пользователь {callback.from_user.id} выбрал категорию -> '{category}'")
    
    await state.update_data(current_category=category)
    
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение с категориями: {e}")
        
    await send_next_question_by_user(callback.bot, callback.from_user.id, state)

async def send_next_question_by_user(bot_instance: Bot, user_id: int, state: FSMContext):
    data = await state.get_data()
    category = data.get("current_category", "все")
      
    try:
        substance, options = await db.get_random_question(category)
        logger.info(f"БД вернула вопрос для категории '{category}': substance={substance}, options={options}")
    except Exception as e:
        logger.error(f"Ошибка при запросе get_random_question: {e}")
        await bot_instance.send_message(user_id, f"❌ Ошибка базы данных: {e}")
        return

    if not substance:
        await bot_instance.send_message(user_id, f"⚠️ В категории '{category}' пока нет веществ!")
        return

    await state.update_data(correct_id=substance['id'])
      
    buttons = [
        [InlineKeyboardButton(text=opt, callback_data=f"ans_{opt}")] for opt in options
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
      
    await bot_instance.send_message(
        user_id,
        f"🧪 Какое тривиальное название у вещества: **{substance['formula']}**?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("ans_"))
async def handle_answer(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    user_answer = callback.data.split("ans_")[1]
    data = await state.get_data()
    correct_id = data.get("correct_id")
    
    logger.info(f"CALLBACK ans_: Пользователь {callback.from_user.id} ответил '{user_answer}', правильный ID={correct_id}")
      
    try:
        substance = await db.get_substance_by_id(correct_id)
    except Exception as e:
        logger.error(f"Ошибка get_substance_by_id: {e}")
        substance = None

    if not substance:
        await callback.bot.send_message(callback.from_user.id, "❌ Ошибка: вопрос устарел.")
        await send_next_question_by_user(callback.bot, callback.from_user.id, state)
        return

    is_correct = (user_answer == substance['name'])
    
    try:
        await db.record_attempt(callback.from_user.id, correct_id, is_correct)
    except Exception as e:
        logger.error(f"Ошибка record_attempt: {e}")
      
    try:
        if is_correct:
            await callback.message.edit_text(f"✅ Верно! **{substance['formula']}** — это **{substance['name']}**.", parse_mode="Markdown")
        else:
            await callback.message.edit_text(f"❌ Неправильно. Правильный ответ: **{substance['name']}**.", parse_mode="Markdown")
    except Exception:
        pass
      
    await send_next_question_by_user(callback.bot, callback.from_user.id, state)

@dp.message(F.text == "📊 Мой прогресс")
async def show_progress(message: types.Message):
    logger.info(f"Пользователь {message.from_user.id} запросил прогресс")
    try:
        total, correct, percent = await db.get_user_stats(message.from_user.id)
    except Exception as e:
        logger.error(f"Ошибка get_user_stats: {e}")
        total, correct, percent = 0, 0, 0
      
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
    await callback.answer("Статистика сброшена!")
    try:
        await db.reset_user_stats(callback.from_user.id)
    except Exception as e:
        logger.error(f"Ошибка reset_stats: {e}")
        
    try:
        await callback.message.edit_text("🔄 Ваша статистика была успешно сброшена.")
    except Exception:
        pass

async def handle_ping(request):
    return web.Response(text="Bot is active")

async def on_startup(bot: Bot):
    logger.info("Установка вебхука...")
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Вебхук успешно установлен на адрес: {WEBHOOK_URL}")

async def main():
    await db.init_db()
    logger.info("База данных инициализирована.")
      
    app = web.Application()
    app.router.add_get('/', handle_ping)
      
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
      
    app.on_startup.append(lambda app: on_startup(bot))
      
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Сервер запущен на порту {port}")
      
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
