import sqlite3

def init_db():
    conn = sqlite3.connect("chemistry.db")
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            notifications_enabled INTEGER DEFAULT 1
        )
    ''')
    
    # Таблица веществ
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS substances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            formula TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'Общее'
        )
    ''')
    
    # Таблица прогресса
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS progress (
            user_id INTEGER,
            substance_id INTEGER,
            correct_streak INTEGER DEFAULT 0,
            total_attempts INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, substance_id)
        )
    ''')
    
    conn.commit()
    conn.close()

def add_user(user_id, full_name, username):
    conn = sqlite3.connect("chemistry.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, full_name, username) VALUES (?, ?, ?)",
        (user_id, full_name, username)
    )
    conn.commit()
    conn.close()

def add_substance(formula, name, category="Общее"):
    conn = sqlite3.connect("chemistry.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO substances (formula, name, category) VALUES (?, ?, ?)",
        (formula, name, category)
    )
    conn.commit()
    conn.close()

def get_all_substances():
    conn = sqlite3.connect("chemistry.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, formula, name, category FROM substances")
    rows = cursor.fetchall()
    conn.close()
    return rows

init_db()
