"""
Скрипт для проверки состояния треков в базе данных
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import DatabaseManager
from sqlalchemy import select, func
from database.models import Track

async def check_tracks():
    """Проверить состояние треков в БД"""
    db = DatabaseManager()
    
    async with db.async_session() as session:
        # Общее количество треков
        total_result = await session.execute(select(func.count(Track.id)))
        total_count = total_result.scalar()
        
        # Треки с изображениями
        with_images_result = await session.execute(
            select(func.count(Track.id)).where(
                (Track.image_url != None) & (Track.image_url != '')
            )
        )
        with_images = with_images_result.scalar()
        
        # Треки без изображений
        without_images = total_count - with_images
        
        print(f"📊 Статистика треков в БД:")
        print(f"   Всего треков: {total_count}")
        print(f"   С изображениями: {with_images}")
        print(f"   Без изображений: {without_images}")
        print()
        
        # Показываем несколько примеров треков без изображений
        if without_images > 0:
            result = await session.execute(
                select(Track).where(
                    (Track.image_url == None) | (Track.image_url == '')
                ).limit(5)
            )
            tracks = result.scalars().all()
            
            print("🎵 Примеры треков без изображений:")
            for track in tracks:
                print(f"   - {track.artist} - {track.name}")
                print(f"     Spotify URL: {track.spotify_url}")
                print(f"     Image URL: {track.image_url}")
                print()

if __name__ == "__main__":
    asyncio.run(check_tracks())
