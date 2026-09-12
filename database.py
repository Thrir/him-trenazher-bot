import os
import random
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL")

# Базовый набор веществ для авто-заполнения
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

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    if not DATABASE_URL:
        print("DATABASE_URL не задана!")
        return

    conn = get_connection()
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT
        )
    ''')
    
    # Таблица веществ
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS substances (
            id SERIAL PRIMARY KEY,
            formula TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL
        )
    ''')
    
    # Таблица попыток
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attempts (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            substance_id INTEGER,
            is_correct BOOLEAN,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()

    # Проверяем, пустая ли база веществ
    cursor.execute('SELECT COUNT(*) FROM substances')
    count = cursor.fetchone()[0]
    
    if count == 0:
        for formula, name, category in DEFAULT_SUBSTANCES:
            cursor.execute(
                'INSERT INTO substances (formula, name, category) VALUES (%s, %s, %s)',
                (formula, name, category)
            )
        conn.commit()
        print("База автоматически заполнена стартовыми веществами!")
        
    cursor.close()
    conn.close()

def add_user(user_id, username, first_name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, username, first_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO NOTHING
    ''', (user_id, username, first_name))
    conn.commit()
    cursor.close()
    conn.close()

def add_substance(formula, name, category):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO substances (formula, name, category)
        VALUES (%s, %s, %s)
    ''', (formula, name, category))
    conn.commit()
    cursor.close()
    conn.close()

def get_categories():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT category FROM substances ORDER BY category')
    categories = [r[0] for r in cursor.fetchall()]
    cursor.close()
    conn.close()
    return categories

def get_substance_by_id(substance_id):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT id, formula, name, category FROM substances WHERE id = %s', (substance_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return dict(row) if row else None

def get_random_question(category=None):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    if category and category != "все":
        cursor.execute(
            'SELECT id, formula, name, category FROM substances WHERE category = %s ORDER BY RANDOM() LIMIT 1',
            (category,)
        )
    else:
        cursor.execute('SELECT id, formula, name, category FROM substances ORDER BY RANDOM() LIMIT 1')
        
    target = cursor.fetchone()
    
    if not target:
        cursor.close()
        conn.close()
        return None, []
        
    target_dict = dict(target)
    
    # Берем 3 случайных неправильных ответа
    cursor.execute('SELECT DISTINCT name FROM substances WHERE id != %s ORDER BY RANDOM() LIMIT 3', (target_dict['id'],))
    wrong_options = [r[0] for r in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    options = wrong_options + [target_dict['name']]
    random.shuffle(options)
    
    return target_dict, options

def record_attempt(user_id, substance_id, is_correct):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO attempts (user_id, substance_id, is_correct)
        VALUES (%s, %s, %s)
    ''', (user_id, substance_id, is_correct))
    conn.commit()
    cursor.close()
    conn.close()

def get_user_stats(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM attempts WHERE user_id = %s', (user_id,))
    total_attempts = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM attempts WHERE user_id = %s AND is_correct = TRUE', (user_id,))
    correct_attempts = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()
    
    percent = round((correct_attempts / total_attempts * 100)) if total_attempts > 0 else 0
    return total_attempts, correct_attempts, percent

def reset_user_stats(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM attempts WHERE user_id = %s', (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
