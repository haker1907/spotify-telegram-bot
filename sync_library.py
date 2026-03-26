
import asyncio
import os
import sys
from datetime import datetime
from sqlalchemy import select, or_

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import DatabaseManager
from database.models import Track, TrackCache, TelegramFile
from services.telegram_storage_service import TelegramStorageService

async def sync_discovery():
    print("🔄 Starting Discovery Sync...")
    db = DatabaseManager()
    await db.init_db()
    
    storage = TelegramStorageService()
    
    async with db.async_session() as session:
        # 1. Находим все треки из legacy кэша
        result = await session.execute(
            select(Track).where(Track.telegram_file_id != None)
        )
        tracks_with_legacy_id = result.scalars().all()
        print(f"🔍 Found {len(tracks_with_legacy_id)} tracks with legacy telegram_file_id")
        
        for track in tracks_with_legacy_id:
            tg_check = await session.get(TelegramFile, track.id)
            if not tg_check:
                print(f"➕ Adding {track.artist} - {track.name} to TelegramFile from legacy ID")
                new_file = TelegramFile(
                    track_id=track.id,
                    file_id=track.telegram_file_id,
                    artist=track.artist,
                    track_name=track.name,
                    uploaded_at=track.cached_at or track.created_at or datetime.utcnow()
                )
                session.add(new_file)
        
        # 2. Проверяем TrackCache
        result = await session.execute(select(TrackCache))
        cache_entries = result.scalars().all()
        print(f"🔍 Found {len(cache_entries)} cache entries")
        
        for entry in cache_entries:
            tg_check = await session.get(TelegramFile, entry.track_id)
            if not tg_check:
                track = await session.get(Track, entry.track_id)
                if track:
                    print(f"➕ Adding {track.artist} - {track.name} to TelegramFile from cache")
                    new_file = TelegramFile(
                        track_id=entry.track_id,
                        file_id=entry.telegram_file_id,
                        artist=track.artist,
                        track_name=track.name,
                        uploaded_at=entry.created_at or datetime.utcnow()
                    )
                    session.add(new_file)
        
        await session.commit()
        
        # 3. Верификация существующих записей в Telegram Channel
        # Мы проверяем, что файлы реально доступны в Telegram
        result = await session.execute(select(TelegramFile))
        all_files = result.scalars().all()
        print(f"🧐 Verifying {len(all_files)} files in Telegram Storage...")
        
        deleted_count = 0
        for tg_file in all_files:
            if not storage.file_exists(tg_file.file_id):
                print(f"🗑️ Removing orphaned record (file not in channel): {tg_file.artist} - {tg_file.track_name}")
                await session.delete(tg_file)
                deleted_count += 1
        
        await session.commit()
        print(f"✅ Discovery Sync complete! Cleaned up {deleted_count} orphaned records.")
        
        # Финальный отчет
        result = await session.execute(select(TelegramFile))
        final_files = result.scalars().all()
        print(f"📊 Total valid tracks in Discover: {len(final_files)}")

if __name__ == "__main__":
    asyncio.run(sync_discovery())

if __name__ == "__main__":
    asyncio.run(sync_discovery())
