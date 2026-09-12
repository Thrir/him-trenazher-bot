import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import database as db

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 980227176  # Твой Telegram ID

bot = Bot(token=TOKEN)
dp = Dispatcher()

student_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🧪 Тренажёр"), KeyboardButton(text="📊 Мой прогресс")],
        [KeyboardButton(text="📚 Список веществ"), KeyboardButton(text="⚙️ Настройки")]
    ],
    resize_keyboard=True
)

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    db.add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    welcome_text = (
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Добро пожаловать в **ХимТренажёр**.\n"
        "Здесь ты сможешь легко выучить тривиальные названия химических веществ!"
    )
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=student_kb)

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ только для репетитора.")
        return
    
    admin_text = (
        "🛠 **Панель Репетитора**\n\n"
        "Чтобы добавить вещества массово, отправь сообщение списком в формате:\n"
        "`Формула | Название | Категория`\n\n"
        "Пример:\n"
        "`H2SO4 | Серная кислота | Кислоты`\n"
        "`NaOH | Едкий натр | Основания`"
    )
    await message.answer(admin_text, parse_mode="Markdown")

@dp.message(F.text.contains("|"))
async def bulk_add_substances(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
        
    lines = message.text.strip().split("\n")
    added_count = 0
    for line in lines:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2:
            formula = parts[0]
            name = parts[1]
            category = parts[2] if len(parts) > 2 else "Общее"
            db.add_substance(formula, name, category)
            added_count += 1
            
    await message.answer(f"✅ Успешно добавлено веществ: **{added_count}**", parse_mode="Markdown")

@dp.message(F.text == "📚 Список веществ")
async def list_substances(message: types.Message):
    substances = db.get_all_substances()
    if not substances:
        await message.answer("База веществ пока пуста. Репетитор еще не добавил карточки.")
        return
        
    text = "📚 **База химических веществ:**\n\n"
    for item in substances:
        text += f"• **{item[1]}** — {item[2]} _({item[3]})_\n"
    
    await message.answer(text, parse_mode="Markdown")

async def main():
    db.init_db()
    print("ХимТренажёр запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
