import sqlite3
from datetime import datetime, timedelta
import asyncio
import random
from settings import WIN_CHANCE, MAX_REF_REWARD, MIN_REF_REWARD, CLICK_MAX_REWARD, CLICK_MIN_REWARD
import time
import sqlite3
from datetime import datetime, timedelta
import asyncio
import random
from settings import WIN_CHANCE, MAX_REF_REWARD, MIN_REF_REWARD, CLICK_MAX_REWARD, CLICK_MIN_REWARD
from io import BytesIO
import matplotlib.pyplot as plt

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def check_and_create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    tables_to_create = {
        'users': '''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                stars REAL DEFAULT 0.0,
                count_refs INTEGER DEFAULT 0,
                referral_id INTEGER DEFAULT NULL,
                withdrawn REAL DEFAULT 0.0,
                lang TEXT NOT NULL,
                ref_rewarded INTEGER DEFAULT 0,
                second_level_rewards REAL DEFAULT 0.0,
                last_click_time TEXT DEFAULT NULL,
                last_gift_time TEXT DEFAULT NULL,
                click_count INTEGER DEFAULT 0,
                gift_count INTEGER DEFAULT 0,
                registration_time TEXT NOT NULL,
                special_ref TEXT DEFAULT NULL,
                completed_onboarding INTEGER DEFAULT 0
            )
        ''',
        'channels': '''
            CREATE TABLE IF NOT EXISTS channels (
                channel_id INTEGER PRIMARY KEY,
                delete_time INTEGER
            )
        ''',
        'tasks': '''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                reward REAL NOT NULL,
                active INTEGER DEFAULT 1,
                completed_count INTEGER DEFAULT 0,
                max_completions INTEGER NOT NULL,
                requires_subscription INTEGER DEFAULT 0,
                task_type TEXT DEFAULT 'sub'
            )
        ''',
        'config': '''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT,
                value TEXT
            )
        ''',
        'completed_tasks': '''
            CREATE TABLE IF NOT EXISTS completed_tasks (
                user_id INTEGER,
                task_id INTEGER,
                last_reward TIMESTAMP,
                PRIMARY KEY (user_id, task_id)
            )
        ''',
        'used_promocodes': '''
            CREATE TABLE IF NOT EXISTS used_promocodes (
                user_id INTEGER,
                promocode TEXT,
                used_at TEXT,
                PRIMARY KEY (user_id, promocode)
            )
        ''',
        'promocodes': '''
            CREATE TABLE IF NOT EXISTS promocodes (
                promocode TEXT PRIMARY KEY,
                reward REAL NOT NULL,
                max_uses INTEGER DEFAULT 0,
                min_referrals INTEGER DEFAULT 0
            )
        ''',
        'block_status': '''
            CREATE TABLE IF NOT EXISTS block_status (
                user_id INTEGER PRIMARY KEY,
                is_blocked INTEGER DEFAULT 0,
                blocked_at TEXT DEFAULT NULL,
                unblocked_at TEXT DEFAULT NULL
            )
        ''',
        'custom_rewards': '''
            CREATE TABLE IF NOT EXISTS custom_rewards (
                user_id INTEGER PRIMARY KEY,
                min_reward REAL NOT NULL,
                max_reward REAL NOT NULL,
                min_f_reward REAL NOT NULL,
                max_f_reward REAL NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''',
        'withdraw_requests': '''
            CREATE TABLE IF NOT EXISTS withdraw_requests (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                amount REAL NOT NULL,
                status TEXT,
                request_time TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''',
        'special_links': '''
            CREATE TABLE IF NOT EXISTS special_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                special_code TEXT NOT NULL UNIQUE,
                unique_visits INTEGER DEFAULT 0,
                verified_signups INTEGER DEFAULT 0,
                total_visits INTEGER DEFAULT 0,
                completed_onboarding INTEGER DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''',
        'special_link_visits': '''
            CREATE TABLE IF NOT EXISTS special_link_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                special_code TEXT NOT NULL,
                FOREIGN KEY(special_code) REFERENCES special_links(special_code)
            )
        ''',
        'robberies': '''
            CREATE TABLE IF NOT EXISTS robberies (
                user_id INTEGER NOT NULL,
                target_user_id INTEGER NOT NULL,
                robbery_time TEXT NOT NULL,
                PRIMARY KEY (user_id, target_user_id)
            )
        ''',
        'sponsor_buttons': '''
            CREATE TABLE IF NOT EXISTS sponsor_buttons (
                chat_id INTEGER,
                name TEXT,
                url TEXT
            )
        ''',
        'spent_stars': '''
            CREATE TABLE IF NOT EXISTS spent_stars (
                id INTEGER PRIMARY KEY,
                amount REAL NOT NULL,
                date TEXT NOT NULL,
                chat_id INTEGER,
                FOREIGN KEY(chat_id) REFERENCES sponsor_buttons(chat_id)
            )
        '''
    }

    for table_name, create_query in tables_to_create.items():
        cursor.execute(create_query)
        print(f'Запрос для таблицы {table_name} выполнен.')

    conn.commit()
    conn.close()


check_and_create_tables()

def add_missing_columns():
    conn = get_db_connection()
    cursor = conn.cursor()

    table_columns = {
        'users': [
            ('click_count', 'INTEGER DEFAULT 0'),
            ('gift_count', 'INTEGER DEFAULT 0'),
            ('referral_id', 'INTEGER DEFAULT NULL'),
            ('special_ref', 'TEXT DEFAULT NULL'),
            ('completed_onboarding', 'INTEGER DEFAULT 0')
        ],
        'tasks': [
            ('completed_count', 'INTEGER DEFAULT 0'),
            ('max_completions', 'INTEGER DEFAULT 0'),
            ('task_type', "TEXT DEFAULT 'sub'"),
            ('requires_subscription', 'INTEGER DEFAULT 0')
        ],
        'promocodes': [
            ('max_uses', 'INTEGER DEFAULT 0'),
            ('min_referrals', 'INTEGER DEFAULT 0')
        ],
        'channels': [
            ('delete_time', 'INTEGER')
        ],
        'special_links': [
            ('user_id', 'INTEGER NOT NULL'),
            ('special_code', 'TEXT NOT NULL UNIQUE'),
            ('unique_visits', 'INTEGER DEFAULT 0'),
            ('verified_signups', 'INTEGER DEFAULT 0'),
            ('total_visits', 'INTEGER DEFAULT 0'),
            ('completed_onboarding', 'INTEGER DEFAULT 0')
        ]
    }

    for table_name, columns in table_columns.items():
        for column_name, column_definition in columns:
            add_column_if_not_exists(cursor, table_name, column_name, column_definition)

    conn.commit()
    conn.close()

def add_column_if_not_exists(cursor, table_name, column_name, column_definition):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [column['name'] for column in cursor.fetchall()]
    if column_name not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
        print(f"Добавлена колонка {column_name} в таблицу {table_name}")


check_and_create_tables()
add_missing_columns()


def add_column_if_not_exists(cursor, table_name, column_name, column_definition):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [column[1] for column in cursor.fetchall()]

    if column_name not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
        print(f'Столбец {column_name} добавлен в таблицу {table_name}.')

check_and_create_tables()
add_missing_columns()


def remove_user(user_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

def increment_click_count(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET click_count = click_count + 1 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_user_registration_time(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT registration_time FROM users WHERE id = ?", (user_id,))
    registration_time = cursor.fetchone()

    conn.close()

    if registration_time:
        return registration_time[0]
    else:
        return None

def is_user_blocked(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT is_blocked FROM block_status WHERE user_id = ?', (user_id,))
    block_status = cursor.fetchone()
    conn.close()

    return block_status and block_status[0] == 1

def increment_gift_count(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET gift_count = gift_count + 1 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

def add_promocode(promocode, reward, max_uses, min_referrals):
    """Добавляет промокод с наградой, максимальным числом активаций и минимальным числом рефералов."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
    INSERT OR REPLACE INTO promocodes (promocode, reward, max_uses, min_referrals) 
    VALUES (?, ?, ?, ?)
    ''', (promocode, reward, max_uses, min_referrals))

    conn.commit()
    conn.close()

def decrement_promocode_uses(promocode):
    """Уменьшает число доступных активаций промокода, удаляет его при достижении 0."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("UPDATE promocodes SET max_uses = max_uses - 1 WHERE promocode = ?", (promocode,))
    cursor.execute("DELETE FROM promocodes WHERE max_uses <= 0")

    conn.commit()
    conn.close()

def add_user_stars(user_id, amount):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("UPDATE users SET stars = stars + ? WHERE id = ?", (amount, user_id))
    
    conn.commit()
    conn.close()

def use_promocode(user_id, promocode):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()


    if check_promocode_usage(user_id, promocode):
        conn.close()
        return False, "❌ Вы уже использовали этот промокод."


    can_use, reward_or_error = can_use_promocode(user_id, promocode)
    if not can_use:
        conn.close()
        return False, reward_or_error


    cursor.execute("INSERT INTO used_promocodes (user_id, promocode, used_at) VALUES (?, ?, ?)",
                   (user_id, promocode, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))


    cursor.execute("UPDATE promocodes SET current_uses = current_uses + 1 WHERE promocode = ?", (promocode,))

    cursor.execute("SELECT max_uses, current_uses FROM promocodes WHERE promocode = ?", (promocode,))
    promo_data = cursor.fetchone()
    if promo_data and promo_data[1] >= promo_data[0]:
        delete_promo(promocode)

    conn.commit()
    conn.close()
    return True, f"✅ Промокод {promocode} активирован! Вы получили {reward_or_error}⭐️."

def can_use_promocode(user_id, promocode):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT reward, max_uses, current_uses, min_referrals FROM promocodes WHERE promocode = ?", (promocode,))
    promo_data = cursor.fetchone()

    if not promo_data:
        conn.close()
        return False, "❌ Промокод не найден или уже исчерпан."

    reward, max_uses, current_uses, min_referrals = promo_data

    cursor.execute("SELECT referrals FROM users WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()

    if not user_data:
        conn.close()
        return False, "❌ Пользователь не найден."

    referrals = user_data[0]

    if referrals < min_referrals:
        conn.close()
        return False, f"❌ Вам нужно хотя бы {min_referrals} рефералов для активации этого промокода."

    if current_uses >= max_uses:
        conn.close()
        return False, "❌ Этот промокод уже исчерпал лимит использований."

    conn.close()
    return True, reward

def set_custom_reward_in_db(user_id, min_reward, max_reward):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO custom_rewards (user_id, min_reward, max_reward)
    VALUES (?, ?, ?)
    """, (user_id, min_reward, max_reward))

    conn.commit()
    conn.close()

def get_custom_reward_from_db(user_id):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='custom_rewards';")
        table_exists = cursor.fetchone()

        if not table_exists:
            check_and_create_tables()

        cursor.execute("""
        SELECT min_reward, max_reward FROM custom_rewards WHERE user_id = ?
        """, (user_id,))

        result = cursor.fetchone()

        conn.close()

        return result if result else (CLICK_MIN_REWARD, CLICK_MAX_REWARD)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return (CLICK_MIN_REWARD, CLICK_MAX_REWARD)

def delete_promo(promocode):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
    DELETE FROM promocodes WHERE promocode = ?
    ''', (promocode,))

    conn.commit()
    conn.close()

def get_all_promocodes():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''SELECT promocode, reward FROM promocodes''')
    promocodes = cursor.fetchall()

    conn.close()
    return promocodes

def get_user_balance(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute('SELECT SUM(amount) FROM stars WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    return result[0] if result[0] is not None else 0.0

def delete_user(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

def add_user(user_id, username, referral_id=None, lang='ru', special_ref=None):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO users (id, username, stars, count_refs, referral_id, lang, click_count, gift_count, registration_time, special_ref)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, 1.0, 0, referral_id, lang, 0, 0, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), special_ref))

    conn.commit()
    conn.close()


def get_user_data(user_id):
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, referral_id FROM users WHERE id = ?', (user_id,))
        return cursor.fetchone()

        user_data = get_user_data(user_id)
        print(f"Данные пользователя в базе: {user_data}")


def update_user_lang(user_id, lang):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET lang = ? WHERE id = ?', (lang, user_id))
    conn.commit()
    conn.close()

def get_click_top():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    query = """
    SELECT id, click_count
    FROM users
    ORDER BY click_count DESC
    LIMIT 10
    """
    top_clicks = cursor.execute(query).fetchall()
    conn.close()

    return top_clicks

def get_user_lang(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute('SELECT lang FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if result:
        return result[0]
    return 'ru'

def get_user(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    return user_data

def user_exists(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return bool(result)

async def get_user_info(user_id):
    loop = asyncio.get_event_loop()
    user_info = await loop.run_in_executor(None, fetch_user_info, user_id)
    return user_info

def fetch_user_info(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            id, username, stars, count_refs, referral_id, withdrawn,
            lang, ref_rewarded, second_level_rewards, last_click_time,
            last_gift_time, click_count, gift_count
        FROM users
        WHERE id = ?
    ''', (user_id,))
    user_info = cursor.fetchone()
    conn.close()
    return user_info

def increment_stars(user_id, stars):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET stars = stars + ? WHERE id = ?', (stars, user_id))
    conn.commit()
    conn.close()

def withdraw_stars(user_id, stars_to_withdraw):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET stars = stars - ?, withdrawn = withdrawn + ? WHERE id = ?', (stars_to_withdraw, stars_to_withdraw, user_id))
    conn.commit()
    conn.close()

def increment_referrals(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET count_refs = count_refs + 1 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_user_count():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute('SELECT COUNT(*) FROM users').fetchone()
    conn.close()
    return result[0] if result else 0

def get_next_withdraw_request_id():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT MAX(id) FROM withdraw_requests")
    max_id = cursor.fetchone()[0]

    if max_id is None:
        return 1
    return max_id + 1

def delete_user_from_db(user_id: int):
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    connection.commit()
    connection.close()

def get_user_counts():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users;")
    total_users = cursor.fetchone()[0]

    today_start = (datetime.now() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    cursor.execute("SELECT COUNT(*) FROM users WHERE registration_time >= ?", (today_start.strftime('%Y-%m-%d %H:%M:%S'),))
    daily_users = cursor.fetchone()[0]

    month_start = (datetime.now() - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    cursor.execute("SELECT COUNT(*) FROM users WHERE registration_time >= ?", (month_start.strftime('%Y-%m-%d %H:%M:%S'),))
    monthly_users = cursor.fetchone()[0]

    conn.close()

    return {
        "total": total_users,
        "daily": daily_users,
        "monthly": monthly_users
    }

def get_total_withdrawn():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute('SELECT SUM(withdrawn) FROM users').fetchone()
    conn.close()
    return result[0] if result else 0.0

def get_user(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return result

def get_users():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute('SELECT * FROM users').fetchall()
    conn.close()
    return result

def add_channel_db(channel_id: int, delete_time: int):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()


    cursor.execute("SELECT COUNT(*) FROM channels WHERE channel_id = ?", (channel_id,))
    existing_channel_count = cursor.fetchone()[0]

    if existing_channel_count == 0:

        cursor.execute("INSERT INTO channels (channel_id, delete_time) VALUES (?, ?)", 
                       (channel_id, int(time.time()) + delete_time * 3600))
        print(f"Канал {channel_id} был добавлен в базу данных с временем удаления через {delete_time} часа.")
    else:

        cursor.execute("UPDATE channels SET delete_time = ? WHERE channel_id = ?", 
                       (int(time.time()) + delete_time * 3600, channel_id))
        print(f"Время удаления канала {channel_id} было обновлено.")

    conn.commit()
    conn.close()

def delete_channel_db(channel_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM channels WHERE channel_id = ?', (channel_id,))
    conn.commit()
    conn.close()

def get_channels_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute('SELECT channel_id FROM channels').fetchall()
    conn.close()
    return [r[0] for r in result]

def remove_channel_db(channel_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM channels WHERE channel_id = ?', (channel_id,))
    conn.commit()
    conn.close()

def add_task(channel_id, reward, max_completions, requires_subscription=True):
    if max_completions is None:
        raise ValueError("max_completions не может быть None")

    task_type = "sub" if requires_subscription else "no_check"

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO tasks (channel_id, reward, completed_count, max_completions, active, requires_subscription, task_type) VALUES (?, ?, 0, ?, 1, ?, ?)',
        (channel_id, reward, max_completions, int(requires_subscription), task_type)
    )
    conn.commit()
    conn.close()

def remove_task(channel_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE channel_id = ?', (channel_id,))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

def check_promocode_usage(user_id, promocode):
    """Проверка, был ли использован промокод пользователем."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM used_promocodes WHERE user_id = ? AND promocode = ?", (user_id, promocode))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def add_promocode_usage(user_id, promocode):
    """Добавляет запись о том, что промокод был использован пользователем."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO used_promocodes (user_id, promocode, used_at) VALUES (?, ?, ?)",
                   (user_id, promocode, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()


def get_tasks():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute(
        'SELECT id, channel_id, reward, completed_count, max_completions FROM tasks WHERE active=1'
    ).fetchall()
    conn.close()
    return result

def mark_task_completed(user_id, task_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO completed_tasks (user_id, task_id) VALUES (?, ?)', (user_id, task_id))
    conn.commit()
    conn.close()

def user_completed_task(user_id, task_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute('SELECT * FROM completed_tasks WHERE user_id=? AND task_id=?', (user_id, task_id)).fetchone()
    conn.close()
    return bool(result)

def set_lucky_time(start, duration=60):
    end = start + timedelta(minutes=duration)
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO config (key, value) VALUES ("lucky_start", ?)', (start.isoformat(),))
    cursor.execute('INSERT OR REPLACE INTO config (key, value) VALUES ("lucky_end", ?)', (end.isoformat(),))
    conn.commit()
    conn.close()

def is_lucky_time_now():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    lucky_start = cursor.execute('SELECT value FROM config WHERE key="lucky_start"').fetchone()
    lucky_end = cursor.execute('SELECT value FROM config WHERE key="lucky_end"').fetchone()
    conn.close()

    if lucky_start and lucky_end:
        start = datetime.fromisoformat(lucky_start[0])
        end = datetime.fromisoformat(lucky_end[0])
        now = datetime.utcnow()
        return start <= now <= end
    return False

def is_lucky_time_database():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    lucky_start = cursor.execute('SELECT value FROM config WHERE key="lucky_start"').fetchone()
    lucky_end = cursor.execute('SELECT value FROM config WHERE key="lucky_end"').fetchone()
    conn.close()

    if lucky_start and lucky_end:
        start = datetime.fromisoformat(lucky_start[0])
        end = datetime.fromisoformat(lucky_end[0])
        now = datetime.utcnow()
        return start <= now <= end
    return False
def set_config_value(key, value):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?,?)', (key, value))
    conn.commit()
    conn.close()

def update_user_ref_rewarded(user_id, rewarded):
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET ref_rewarded = ? WHERE id = ?", (int(rewarded), user_id))
        conn.commit()


def increment_second_level_rewards(user_id, amount):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET second_level_rewards = second_level_rewards + ? WHERE id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def get_last_click_time(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute('SELECT last_click_time FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return result[0] if result else None

def update_last_click_time(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET last_click_time = ? WHERE id = ?', (datetime.utcnow().isoformat(), user_id))
    conn.commit()
    conn.close()

def add_stars(user_id, stars=CLICK_MIN_REWARD):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET stars = stars + ? WHERE id = ?', (stars, user_id))
    conn.commit()
    conn.close()

def subtract_stars(user_id, stars=CLICK_MIN_REWARD):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET stars = stars - ? WHERE id = ?', (stars, user_id))
    conn.commit()
    conn.close()

def get_last_gift(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute('SELECT last_gift_time FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return result[0] if result else None

def update_last_gift(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET last_gift_time = ? WHERE id = ?', (datetime.utcnow().isoformat(), user_id))
    conn.commit()
    conn.close()

def increase_referral_count(referral_id):
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()
    cursor.execute("UPDATE users SET count_refs = count_refs + 1 WHERE id = ?", (referral_id,))
    connection.commit()
    connection.close()

def get_referral_count(user_id):
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referral_id=?", (user_id,))
    result = cursor.fetchone()
    connection.close()
    return result[0]

def update_user_language(user_id, new_lang):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET lang = ? WHERE user_id = ?", (new_lang, user_id))
    conn.commit()
    conn.close()

import sqlite3

def get_referral_top():
    query = """
    SELECT referral_id, COUNT(*) as referral_count
    FROM users
    GROUP BY referral_id
    ORDER BY referral_count DESC
    LIMIT 10
    """
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    top_referrals = cursor.execute(query).fetchall()
    conn.close()
    return top_referrals

def get_referrals(user_id):
    query = """
    SELECT id, username, stars
    FROM users
    WHERE referral_id = ?
    """
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    referrals = cursor.execute(query, (user_id,)).fetchall()
    conn.close()
    return referrals

def get_referrals_count(user_id):
    query = """
    SELECT COUNT(*)
    FROM users
    WHERE referral_id = ?
    """
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(query, (user_id,))
    referrals_count = cursor.fetchone()[0]
    conn.close()
    return referrals_count

def get_total_combined():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute('SELECT SUM(stars), SUM(withdrawn) FROM users').fetchone()
    conn.close()
    total_stars = result[0] if result[0] is not None else 0.0
    total_withdrawn = result[1] if result[1] is not None else 0.0
    return total_stars + total_withdrawn

def get_total_combined_string():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute('SELECT SUM(stars), SUM(withdrawn) FROM users').fetchone()
    conn.close()
    total_stars = result[0] if result[0] is not None else 0.0
    total_withdrawn = result[1] if result[1] is not None else 0.0
    return f"{total_stars:.2f}-{total_withdrawn:.2f}"

def get_total_withdrawn():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute('SELECT SUM(withdrawn) FROM users').fetchone()
    conn.close()
    total_withdrawn = result[0] if result[0] is not None else 0.0
    return total_withdrawn

def get_top_users():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute(
        'SELECT username, (stars + withdrawn) AS total_stars FROM users ORDER BY total_stars DESC LIMIT 10'
    ).fetchall()
    conn.close()

    result = [(username, round(total_stars, 2)) for username, total_stars in result]
    return result


def get_promocode_reward(promocode):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT reward FROM promocodes WHERE promocode = ?", (promocode,))
    result = cursor.fetchone()

    conn.close()

    if result:
        return result[0]
    else:
        return None

def block_user_in_db(user_id):
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM block_status WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()

        if user:
            if user[1] == 1:
                return False
            cursor.execute('UPDATE block_status SET is_blocked = 1, blocked_at = ? WHERE user_id = ?',
                           (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        else:
            cursor.execute('INSERT INTO block_status (user_id, is_blocked, blocked_at) VALUES (?, 1, ?)',
                           (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка при блокировке пользователя {user_id}: {e}")
        return False

def unblock_user_in_db(user_id):
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM block_status WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()

        if user:
            if user[1] == 0:
                return False
            cursor.execute('UPDATE block_status SET is_blocked = 0, unblocked_at = ? WHERE user_id = ?',
                           (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        else:
            cursor.execute('INSERT INTO block_status (user_id, is_blocked, unblocked_at) VALUES (?, 0, ?)',
                           (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка при разблокировке пользователя {user_id}: {e}")
        return False

def play_game(user_id, bet_amount, win_coefficient):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT stars FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        return "Пользователь не найден."

    current_stars = user["stars"]

    if current_stars < bet_amount:
        return "У вас недостаточно звёзд для этой ставки."

    win = random.randint(1, 100) <= WIN_CHANCE

    if win:
        win_amount = bet_amount * win_coefficient
        new_stars = current_stars + win_amount - bet_amount
        cursor.execute("UPDATE users SET stars = ? WHERE id = ?", (new_stars, user_id))
        conn.commit()
        conn.close()
        return f"🎉 Вы выиграли! Ваш выигрыш: {win_amount:.1f} ⭐ (коэффициент: {win_coefficient})"
    else:
        new_stars = current_stars - bet_amount
        cursor.execute("UPDATE users SET stars = ? WHERE id = ?", (new_stars, user_id))
        conn.commit()
        conn.close()
        return "😞 К сожалению, вы проиграли. Попробуйте ещё раз!"

def get_user_username(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''SELECT username FROM users WHERE id = ?''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def update_user_username(user_id, new_username):
    if new_username:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''UPDATE users SET username = ? WHERE id = ?''', (new_username, user_id))
        conn.commit()
        conn.close()

def get_referral_id(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT referral_id FROM users WHERE id = ?', (user_id,))
    referral_id = cursor.fetchone()
    conn.close()
    return referral_id[0] if referral_id else None

def get_referral_reward_range(user_id):
    """
    Получает кастомный диапазон наград за рефералов для заданного user_id.
    Если кастомных значений нет, возвращает стандартный диапазон.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT min_f_reward, max_f_reward FROM custom_rewards WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if result:
            min_f_reward, max_f_reward = result
            return min_f_reward, max_f_reward
        else:
            return MIN_REF_REWARD, MAX_REF_REWARD
    finally:
        conn.close()


def set_ref_reward(user_id, min_f_reward, max_f_reward):
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        print(f"Проверяю наличие user_id: {user_id}")
        cursor.execute("SELECT 1 FROM custom_rewards WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone()

        if exists:
            print(f"Обновляю запись для user_id: {user_id}, min: {min_f_reward}, max: {max_f_reward}")
            cursor.execute("""
                UPDATE custom_rewards
                SET min_f_reward = ?, max_f_reward = ?
                WHERE user_id = ?
            """, (min_f_reward, max_f_reward, user_id))
        else:
            print(f"Создаю новую запись для user_id: {user_id}, min: {min_f_reward}, max: {max_f_reward}")
            cursor.execute("""
                INSERT INTO custom_rewards (user_id, min_f_reward, max_f_reward)
                VALUES (?, ?, ?)
            """, (user_id, min_f_reward, max_f_reward))

        conn.commit()
        print(f"Награда для user_id {user_id} успешно установлена.")
    except sqlite3.Error as e:
        print(f"Ошибка базы данных: {e}")
    finally:
        conn.close()

def get_referral_top_by_period(period):
    """
    Получение топа рефералов за указанный период.
    :param period: Период времени ('day', 'week', 'month')
    :return: Список рефералов [(user_id, count_refs), ...]
    """
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    now = datetime.now()

    if period == 'day':
        time_threshold = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        time_threshold = now - timedelta(weeks=1)
    elif period == 'month':
        time_threshold = now - timedelta(days=30)
    else:
        raise ValueError("Некорректный период времени.")

    query = '''
        SELECT referral_id, COUNT(*)
        FROM users
        WHERE referral_id IS NOT NULL AND registration_time >= ?
        GROUP BY referral_id
        ORDER BY COUNT(*) DESC
    '''

    cursor.execute(query, (time_threshold.strftime('%Y-%m-%d %H:%M:%S'),))
    result = cursor.fetchall()

    conn.close()
    return result

from datetime import datetime, timedelta
import sqlite3

def get_referrals_count_week(user_id):
    today = datetime.utcnow()

    start_of_week = today - timedelta(days=today.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=1, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)

    start_of_week_str = start_of_week.strftime("%Y-%m-%d %H:%M:%S")
    end_of_week_str = end_of_week.strftime("%Y-%m-%d %H:%M:%S")

    print(f"🔍 Проверяем рефералов с {start_of_week_str} по {end_of_week_str}")

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) 
        FROM users 
        WHERE referral_id = ? 
        AND registration_time BETWEEN ? AND ?
    """, (user_id, start_of_week_str, end_of_week_str))

    count = cursor.fetchone()[0]
    conn.close()

    return count

def get_total_tasks():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM tasks")
    total_tasks = cursor.fetchone()[0]

    conn.close()
    return total_tasks

def get_active_tasks():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE active = 1")
    active = cursor.fetchone()[0]
    conn.close()
    return active

def get_completed_tasks():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE completed_count > 0")
    completed = cursor.fetchone()[0]
    conn.close()
    return completed

def get_total_promocodes():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM promocodes")
    total = cursor.fetchone()[0]
    conn.close()
    return total

def get_active_promocodes():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM promocodes WHERE max_uses > 0")
    active = cursor.fetchone()[0]
    conn.close()
    return active

def get_total_channels():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM channels")
    total = cursor.fetchone()[0]
    conn.close()
    return total

def get_active_channels():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM channels WHERE delete_time IS NULL OR delete_time > ?", (int(time.time()),))
    active = cursor.fetchone()[0]
    conn.close()
    return active

def update_verified_signups(special_code):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE special_links SET verified_signups = verified_signups + 1 WHERE special_code = ?",
        (special_code,)
    )
    
    conn.commit()
    conn.close()

async def mark_onboarding_completed(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    print(f"Updating completed_onboarding for user {user_id}")

    cursor.execute("UPDATE users SET completed_onboarding = 1 WHERE id = ?", (user_id,))
    
    cursor.execute("SELECT special_ref FROM users WHERE id = ?", (user_id,))
    special_ref = cursor.fetchone()

    if special_ref and special_ref[0]:
        print(f"User {user_id} registered via special_ref: {special_ref[0]}")
        cursor.execute("""
            UPDATE special_links 
            SET completed_onboarding = completed_onboarding + 1 
            WHERE special_code = ?
        """, (special_ref[0],))
    
    conn.commit()

    cursor.execute("SELECT completed_onboarding FROM users WHERE id = ?", (user_id,))
    updated_value = cursor.fetchone()
    print(f"Updated user onboarding status: {updated_value}")

    if special_ref and special_ref[0]:
        cursor.execute("SELECT completed_onboarding FROM special_links WHERE special_code = ?", (special_ref[0],))
        updated_link_value = cursor.fetchone()
        print(f"Updated special link onboarding count: {updated_link_value}")

    conn.close()

def update_special_links_onboarding():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE special_links 
        SET completed_onboarding = (
            SELECT COUNT(*) FROM users 
            WHERE users.special_ref = special_links.special_code 
            AND users.completed_onboarding = 1
        )
    """)
    
    conn.commit()
    conn.close()

def get_user_referrals(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, username, registration_time 
        FROM users 
        WHERE referral_id = ? 
        ORDER BY registration_time DESC
    """, (user_id,))
    referrals = cursor.fetchall()

    total_refs = len(referrals)

    today = datetime.utcnow()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_week_str = start_of_week.strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        SELECT COUNT(*) FROM users 
        WHERE referral_id = ? 
        AND registration_time >= ?
    """, (user_id, start_of_week_str))
    weekly_refs = cursor.fetchone()[0]

    conn.close()
    return referrals, total_refs, weekly_refs

def add_sponsor_button(chat_id, name, url):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sponsor_buttons (chat_id, name, url) VALUES (?, ?, ?)", (chat_id, name, url))
    conn.commit()
    conn.close()

def remove_sponsor_button(chat_id, name, url):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sponsor_buttons WHERE chat_id = ? AND name = ? AND url = ?", (chat_id, name, url))
    conn.commit()
    conn.close()

def get_sponsor_buttons():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT name, url FROM sponsor_buttons")
    buttons = cursor.fetchall()

    conn.close()
    return buttons

def complete_task(user_id, task_id, reward):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO completed_tasks (user_id, task_id) VALUES (?, ?)", (user_id, task_id))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, user_id))
    conn.commit()
    conn.close()

def reset_user_balances():
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET stars = 0.0")
        conn.commit()

def give_stars_to_all(amount: float):
    print(f"Начинаем начисление {amount}⭐ всем пользователям...")

    try:
        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            if total_users == 0:
                print("⚠️ В базе нет пользователей, начисление звёзд отменено.")
                return
            cursor.execute("UPDATE users SET stars = stars + ?", (amount,))
            conn.commit()
            print(f"✅ Успешно начислено {amount}⭐ {cursor.rowcount} пользователям.")
    except Exception as e:
        print(f"❌ Ошибка при начислении звёзд: {e}")


def record_spent_stars(amount):
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        current_date = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("INSERT INTO spent_stars (amount, date) VALUES (?, ?)", (amount, current_date))
        conn.commit()

def get_spent_stars_for_day():
    today = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(amount) FROM spent_stars WHERE date = ?", (today,))
        result = cursor.fetchone()
        return result[0] if result[0] else 0.0

def get_spent_stars_for_week():
    today = datetime.now()
    week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(amount) FROM spent_stars WHERE date >= ?", (week_start,))
        result = cursor.fetchone()
        return result[0] if result[0] else 0.0

def get_spent_stars_for_month():
    first_day_of_month = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(amount) FROM spent_stars WHERE date >= ?", (first_day_of_month,))
        result = cursor.fetchone()
        return result[0] if result[0] else 0.0
    
def get_unique_users_count():
    connection = sqlite3.connect('database.db')
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM custom_rewards")
    result = cursor.fetchone()
    return result[0] if result else 0

async def get_random_user():
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()
    cursor.execute("SELECT id, stars FROM users ORDER BY RANDOM() LIMIT 1")
    random_user = cursor.fetchone()
    connection.close()
    if random_user:
        return random_user
    else:
        return None
    
async def update_user_balance(user_id, new_balance):
    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()

    cursor.execute("UPDATE users SET stars = ? WHERE id = ?", (new_balance, user_id))
    connection.commit()
    connection.close()

def get_users_balance(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute('SELECT stars FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return result[0] if result and result[0] is not None else 0.0
