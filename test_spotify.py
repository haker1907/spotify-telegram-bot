"""
Тест парсинга Spotify ссылки
"""
import sys
sys.path.insert(0, 'd:/uktamaliyev/hack/1')

from services.spotify_service import SpotifyService

# Тестируем ссылку пользователя
url = "https://open.spotify.com/track/33uCmVJE2HTSnWx8k64TCQ?si=f1a5d59e72114c42"

print("🧪 Тестирование парсинга Spotify ссылки\n")
print(f"URL: {url}\n")

# Создаём сервис
spotify = SpotifyService()

# Парсим URL
print("1️⃣ Парсинг URL...")
parsed = spotify.parse_spotify_url(url)
print(f"   Результат: {parsed}\n")

# Получаем информацию о треке
print("2️⃣ Получение информации о треке...")
import asyncio
track_info = asyncio.run(spotify.get_track_info_from_url(url))

if track_info:
    print("   ✅ Успешно!\n")
    print(f"   🎵 Название: {track_info['name']}")
    print(f"   👤 Исполнитель: {track_info['artist']}")
    print(f"   🖼️  Обложка: {track_info.get('image_url', 'Нет')[:50]}...")
else:
    print("   ❌ Не удалось получить информацию")

# Тестируем плейлист
playlist_url = "https://open.spotify.com/playlist/3nBpNPEsB5cbKUlu6iHVrm?si=JdWs-bLsTFGsfHJJWNoc7g"
print("\n3️⃣ Тестирование плейлиста...")
playlist_info = asyncio.run(spotify.get_playlist_info(playlist_url))

if playlist_info:
    print(f"   ✅ Успешно! Плейлист: {playlist_info['name']}")
    print(f"   📊 Найдено треков: {len(playlist_info['tracks'])}")
    for track in playlist_info['tracks'][:5]:
        print(f"      - {track['artist']} - {track['name']}")
else:
    print("   ❌ Не удалось получить информацию о плейлисте")
