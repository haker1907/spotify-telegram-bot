
import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from services.telegram_storage_service import TelegramStorageService
from services.db_backup_service import DatabaseBackupService

async def check_status():
    print(f"🔍 Checking Telegram Storage (Channel: {config.STORAGE_CHANNEL_ID})...")
    storage = TelegramStorageService()
    
    pinned = storage.get_pinned_message()
    if pinned:
        print(f"✅ Found pinned message! ID: {pinned.get('message_id')}")
        if pinned.get('document'):
            doc = pinned['document']
            print(f"📄 Document: {doc.get('file_name')} ({doc.get('file_size')} bytes)")
            print(f"📅 Date: {pinned.get('date')}")
        else:
            print("⚠️ Pinned message is NOT a document.")
    else:
        print("❌ No pinned message found in the storage channel.")
    
    db_path = config.DATABASE_URL.replace('sqlite+aiosqlite:///', '')
    if os.path.exists(db_path):
        size = os.path.getsize(db_path)
        print(f"💾 Local DB exists: {db_path} ({size} bytes)")
    else:
        print(f"❌ Local DB NOT found: {db_path}")

if __name__ == "__main__":
    asyncio.run(check_status())
