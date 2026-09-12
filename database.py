import sqlite3

DB_NAME = "chemistry.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT
        )
    ''')
    
    # Таблица веществ
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS substances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            formula TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL
        )
    ''')
    
    # Таблица попыток ответов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            substance_id INTEGER,
            is_correct BOOLEAN,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def add_user(user_id, username, first_name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
    ''', (user_id, username, first_name))
    conn.commit()
    conn.close()

def add_substance(formula, name, category):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO substances (formula, name, category)
        VALUES (?, ?, ?)
    ''', (formula, name, category))
    conn.commit()
    conn.close()

def get_substance_by_id(substance_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, formula, name, category FROM substances WHERE id = ?', (substance_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {'id': row[0], 'formula': row[1], 'name': row[2], 'category': row[3]}
    return None

def get_random_question(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Берем случайное вещество
    cursor.execute('SELECT id, formula, name, category FROM substances ORDER BY RANDOM() LIMIT 1')
    target = cursor.fetchone()
    
    if not target:
        conn.close()
        return None, []
        
    target_dict = {'id': target[0], 'formula': target[1], 'name': target[2], 'category': target[3]}
    
    # Берем 3 случайных неправильных ответа
    cursor.execute('SELECT DISTINCT name FROM substances WHERE id != ? ORDER BY RANDOM() LIMIT 3', (target[0],))
    wrong_options = [r[0] for r in cursor.fetchall()]
    
    conn.close()
    
    options = wrong_options + [target_dict['name']]
    import random
    random.shuffle(options)
    
    return target_dict, options

def record_attempt(user_id, substance_id, is_correct):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO attempts (user_id, substance_id, is_correct)
        VALUES (?, ?, ?)
    ''', (user_id, substance_id, is_correct))
    conn.commit()
    conn.close()
