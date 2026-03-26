import asyncio
import os
import sys
from datetime import datetime

# Add the project root to sys.path
sys.path.append(os.getcwd())

from database.db_manager import DatabaseManager
from services.telegram_storage_service import TelegramStorageService
from services.db_backup_service import DatabaseBackupService

async def main():
    print("🧪 Testing Database Backup Optimization...")
    db_manager = DatabaseManager()
    await db_manager.init_db()  # Создаем таблицы если их нет
    storage = TelegramStorageService()
    backup_service = DatabaseBackupService(storage, "spotify_bot.db", db_manager)
    
    # Триггерим бэкап вручную
    print("💾 Triggering manual database backup...")
    success = await backup_service.backup_to_telegram()
    
    if success:
        print("✅ Backup process initiated successfully!")
        print("ℹ️ Check your Telegram channel for:")
        print("   1. A new .db file.")
        print("   2. No 'Pinned message' service notification (should be auto-deleted).")
        print("   3. Total .db files in the channel should be 2 (if you had backups before).")
    else:
        print("❌ Backup failed!")

if __name__ == "__main__":
    asyncio.run(main())
