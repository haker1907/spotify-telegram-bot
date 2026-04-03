
import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from services.telegram_storage_service import TelegramStorageService
from services.db_backup_service import DatabaseBackupService
from database.db_manager import DatabaseManager

async def force_restore():
    print(f"🚀 Forcing restoration from Telegram Storage...")
    storage = TelegramStorageService()
    
    db = DatabaseManager()
    db_path = db.get_database_file_path()
    backup_service = DatabaseBackupService(
        storage_service=storage,
        db_path=db_path
    )
    
    # Custom restoration logic that ignores local file size
    print("🔍 Searching for backup...")
    backup_info = await backup_service._find_latest_backup()
    
    if not backup_info:
        print("❌ No backup found in Telegram!")
        return
    
    print(f"📥 Found backup {backup_info['file_id'][:20]}... ({backup_info['file_size']} bytes)")
    print(f"💾 Local DB size: {os.path.getsize(db_path)} bytes")
    
    success = await backup_service._download_backup(backup_info['file_id'])
    
    if success:
        print("✅ SUCCESS! Database forcefully restored from Telegram.")
        print(f"🆕 New local DB size: {os.path.getsize(db_path)} bytes")
    else:
        print("❌ FAILED to restore database.")

if __name__ == "__main__":
    asyncio.run(force_restore())
