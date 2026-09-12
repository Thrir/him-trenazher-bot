import os
import random
import asyncpg
import ssl

DATABASE_URL = os.getenv("DATABASE_URL")

# Базовый набор веществ для автоматического заполнения пустой базы
DEFAULT_SUBSTANCES = [
    ("H2SO4", "Серная кислота", "Кислоты"),
    ("NaOH", "Едкий натр", "Основания"),
    ("C6H12O6", "Глюкоза", "Углеводы"),
    ("NaCl", "Поваренная соль", "Соли"),
    ("NaHCO3", "Пищевая сода", "Соли"),
    ("CaO", "Негашёная известь", "Оксиды"),
    ("Ca(OH)2", "Гашёная известь", "Основания"),
    ("HCl", "Соляная кислота", "Кислоты"),
    ("HNO3", "Азотная кислота", "Кислоты"),
    ("NH3", "Аммиак", "Водородные соединения"),
    ("CO2", "Углекислый газ", "Оксиды"),
    ("H2O2", "Перекись водорода", "Оксиды"),
    ("KMnO4", "Марганцовка", "Соли"),
    ("CH3COOH", "Уксусная кислота", "Кислоты"),
    ("Fe2O3", "Ржавчина / Гематит", "Оксиды")
]

async def get_connection():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return await asyncpg.connect(DATABASE_URL, ssl=ctx, statement_cache_size=0)

async def init_db():
    if not DATABASE_URL:
        print("DATABASE_URL не задана!")
        return

    conn = await get_connection()
    try:
        # Таблица пользователей
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT
            )
        ''')
        
        # Таблица веществ
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS substances (
                id SERIAL PRIMARY KEY,
                formula TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL
            )
        ''')
        
        # Таблица попыток
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS attempts (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                substance_id INTEGER,
                is_correct BOOLEAN,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Проверяем и автоматически заполняем стартовыми веществами
        count = await conn.fetchval('SELECT COUNT(*) FROM substances')
        if count == 0:
            for formula, name, category in DEFAULT_SUBSTANCES:
                await conn.execute(
                    'INSERT INTO substances (formula, name, category) VALUES ($1, $2, $3)',
                    formula, name, category
                )
            print("База автоматически заполнена стартовыми веществами!")
    finally:
        await conn.close()

async def add_user(user_id, username, first_name):
    conn = await get_connection()
    try:
        await conn.execute('''
            INSERT INTO users (user_id, username, first_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO NOTHING
        ''', user_id, username, first_name)
    finally:
        await conn.close()

async def add_substance(formula, name, category):
    conn = await get_connection()
    try:
        await conn.execute('''
            INSERT INTO substances (formula, name, category)
            VALUES ($1, $2, $3)
        ''', formula, name, category.strip())
    finally:
        await conn.close()

async def get_categories():
    conn = await get_connection()
    try:
        rows = await conn.fetch('SELECT DISTINCT category FROM substances ORDER BY category')
        return [r['category'] for r in rows]
    finally:
        await conn.close()

async def get_substance_by_id(substance_id):
    conn = await get_connection()
    try:
        row = await conn.fetchrow('SELECT id, formula, name, category FROM substances WHERE id = $1', substance_id)
        return dict(row) if row else None
    finally:
        await conn.close()

async def get_random_question(category=None):
    conn = await get_connection()
    try:
        if category and category != "все":
            target = await conn.fetchrow(
                'SELECT id, formula, name, category FROM substances WHERE TRIM(LOWER(category)) = TRIM(LOWER($1)) ORDER BY RANDOM() LIMIT 1',
                category
            )
        else:
            target = await conn.fetchrow('SELECT id, formula, name, category FROM substances ORDER BY RANDOM() LIMIT 1')
            
        if not target:
            return None, []
            
        target_dict = dict(target)
        
        wrong_rows = await conn.fetch(
            '''
            SELECT name FROM (
                SELECT DISTINCT name FROM substances WHERE id != $1
            ) as sub ORDER BY RANDOM() LIMIT 3
            ''',
            target_dict['id']
        )
        wrong_options = [r['name'] for r in wrong_rows]
        
        options = wrong_options + [target_dict['name']]
        random.shuffle(options)
        
        return target_dict, options
    finally:
        await conn.close()

async def record_attempt(user_id, substance_id, is_correct):
    conn = await get_connection()
    try:
        await conn.execute('''
            INSERT INTO attempts (user_id, substance_id, is_correct)
            VALUES ($1, $2, $3)
        ''', user_id, substance_id, is_correct)
    finally:
        await conn.close()

async def get_user_stats(user_id):
    conn = await get_connection()
    try:
        total = await conn.fetchval('SELECT COUNT(*) FROM attempts WHERE user_id = $1', user_id)
        correct = await conn.fetchval('SELECT COUNT(*) FROM attempts WHERE user_id = $1 AND is_correct = TRUE', user_id)
        
        percent = round((correct / total * 100)) if total and total > 0 else 0
        return total or 0, correct or 0, percent
    finally:
        await conn.close()

async def reset_user_stats(user_id):
    conn = await get_connection()
    try:
        await conn.execute('DELETE FROM attempts WHERE user_id = $1', user_id)
    finally:
        await conn.close()
