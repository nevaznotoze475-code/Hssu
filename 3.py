import os
import shutil
import time
from datetime import datetime

DB_PATH = "database.db"
BACKUP_DIR = "backups"
BACKUP_LIMIT = 5
INTERVAL = 1800

os.makedirs(BACKUP_DIR, exist_ok=True)

def create_backup():
    """Создает бэкап базы данных и удаляет старые бэкапы."""
    if not os.path.exists(DB_PATH):
        print("Файл базы данных не найден!")
        return
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_filename = f"backup_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    shutil.copy(DB_PATH, backup_path)
    print(f"Бэкап сохранён: {backup_filename}")
    
    backups = sorted(os.listdir(BACKUP_DIR))
    backups = [os.path.join(BACKUP_DIR, b) for b in backups if b.startswith("backup_")]
    
    if len(backups) > BACKUP_LIMIT:
        for old_backup in backups[:len(backups) - BACKUP_LIMIT]:
            os.remove(old_backup)
            print(f"Удалён старый бэкап: {old_backup}")

if __name__ == "__main__":
    while True:
        create_backup()
        time.sleep(INTERVAL)
