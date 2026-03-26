"""
Скрипт для детальной проверки image_url в треках
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import DatabaseManager
from sqlalchemy import select
from database.models import Track

async def check_image_urls():
    """Проверить реальные значения image_url"""
    db = DatabaseManager()
    
    async with db.async_session() as session:
        result = await session.execute(select(Track).limit(10))
        tracks = result.scalars().all()
        
        print(f"📊 Проверка image_url для первых 10 треков:\n")
        
        for track in tracks:
            has_image = bool(track.image_url and track.image_url.strip())
            status = "✅" if has_image else "❌"
            
            print(f"{status} {track.artist} - {track.name}")
            print(f"   image_url: {track.image_url}")
            print(f"   spotify_url: {track.spotify_url}")
            print()

if __name__ == "__main__":
    asyncio.run(check_image_urls())
