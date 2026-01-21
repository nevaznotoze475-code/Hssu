import sqlite3

def clear_database():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = OFF;')

    tables_to_clear = [
        'users', 'custom_rewards', 'tasks', 'used_promocodes', 'promocodes',
        'completed_tasks', 'channels', 'block_status', 'config',
        'withdraw_requests', 'special_links', 'special_link_visits',
        'robberies', 'sponsor_buttons', 'spent_stars'
    ]

    for table in tables_to_clear:
        cursor.execute(f'DELETE FROM {table};')

    cursor.execute('DELETE FROM sqlite_sequence;')
    cursor.execute('PRAGMA foreign_keys = ON;')

    conn.commit()
    conn.close()

    print("База данных очищена!")

clear_database()
