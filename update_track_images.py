"""
Скрипт для обновления существующих треков изображениями из Spotify
"""
import asyncio
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import DatabaseManager
from services.spotify_service import SpotifyService
from sqlalchemy import select
from database.models import Track

async def update_track_images():
    """Обновить изображения для всех треков без image_url"""
    db = DatabaseManager()
    spotify = SpotifyService()
    
    async with db.async_session() as session:
        # Получаем все треки без изображений
        result = await session.execute(
            select(Track).where(
                (Track.image_url == None) | (Track.image_url == '')
            )
        )
        tracks_without_images = result.scalars().all()
        
        print(f"📊 Найдено треков без изображений: {len(tracks_without_images)}")
        
        updated_count = 0
        for track in tracks_without_images:
            try:
                # Пытаемся получить информацию из Spotify
                if track.spotify_url and 'spotify.com/track/' in track.spotify_url:
                    # Если есть прямая ссылка на трек
                    track_info = spotify.get_track_info_from_url(track.spotify_url)
                    if track_info and track_info.get('image_url'):
                        track.image_url = track_info['image_url']
                        if track_info.get('album'):
                            track.album = track_info['album']
                        if track_info.get('duration_ms'):
                            track.duration_ms = track_info['duration_ms']
                        updated_count += 1
                        print(f"✅ Обновлен: {track.artist} - {track.name}")
                
            except Exception as e:
                print(f"⚠️ Ошибка для {track.artist} - {track.name}: {e}")
                continue
        
        # Сохраняем изменения
        await session.commit()
        
        print(f"\n🎉 Обновлено треков: {updated_count} из {len(tracks_without_images)}")
        print(f"⏭️ Остальные треки обновятся автоматически при следующем воспроизведении")

if __name__ == "__main__":
    print("🔄 Начинаем обновление изображений треков...")
    asyncio.run(update_track_images())
    print("✅ Готово!")
