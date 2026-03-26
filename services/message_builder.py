"""
Построитель сообщений для Telegram
"""
from typing import Dict, List
from utils.strings import get_string


class MessageBuilder:
    """Класс для форматирования сообщений бота"""
    
    @staticmethod
    def format_duration(duration_ms: int) -> str:
        """Форматирование длительности из миллисекунд в MM:SS"""
        if not duration_ms:
            return "0:00"
        
        seconds = duration_ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"
    
    @staticmethod
    def build_track_message(track: Dict, lang: str = "ru") -> str:
        """Создать сообщение с информацией о треке"""
        duration = MessageBuilder.format_duration(track.get('duration_ms', 0))
        popularity = track.get('popularity', 0)
        
        artist_label = "Исполнитель" if lang == "ru" else "Artist"
        album_label = "Альбом" if lang == "ru" else "Album"
        duration_label = "Длительность" if lang == "ru" else "Duration"
        popularity_label = "Популярность" if lang == "ru" else "Popularity"
        open_label = "Открыть в Spotify" if lang == "ru" else "Open in Spotify"
        
        message = f"""
🎵 <b>{track['name']}</b>

👤 <b>{artist_label}:</b> {track['artist']}
💿 <b>{album_label}:</b> {track.get('album', 'Unknown')}
⏱ <b>{duration_label}:</b> {duration}
📊 <b>{popularity_label}:</b> {popularity}/100

🔗 <a href="{track['spotify_url']}">{open_label}</a>
"""
        return message.strip()
    
    @staticmethod
    def build_album_message(album: Dict, lang: str = "ru") -> str:
        """Создать сообщение с информацией об альбоме"""
        artist_label = "Исполнитель" if lang == "ru" else "Artist"
        date_label = "Дата выхода" if lang == "ru" else "Release Date"
        tracks_label = "Треков" if lang == "ru" else "Tracks"
        open_label = "Открыть в Spotify" if lang == "ru" else "Open in Spotify"
        
        message = f"""
💿 <b>{album['name']}</b>

👤 <b>{artist_label}:</b> {album['artist']}
📅 <b>{date_label}:</b> {album.get('release_date', 'Unknown' if lang == 'en' else 'Неизвестно')}
🎵 <b>{tracks_label}:</b> {album['total_tracks']}

🔗 <a href="{album['spotify_url']}">{open_label}</a>
"""
        return message.strip()
    
    @staticmethod
    def build_playlist_message(playlist: Dict, lang: str = "ru") -> str:
        """Создать сообщение с информацией о плейлисте"""
        description = playlist.get('description', '')
        if len(description) > 200:
            description = description[:200] + '...'
            
        owner_label = "Автор" if lang == "ru" else "Owner"
        tracks_label = "Треков" if lang == "ru" else "Tracks"
        desc_label = "Описание" if lang == "ru" else "Description"
        open_label = "Открыть в Spotify" if lang == "ru" else "Open in Spotify"
        
        message = f"""
📋 <b>{playlist['name']}</b>

👤 <b>{owner_label}:</b> {playlist['owner']}
🎵 <b>{tracks_label}:</b> {playlist['total_tracks']}
"""
        if description:
            message += f"\n📝 <b>{desc_label}:</b> {description}\n"
        
        message += f"\n🔗 <a href=\"{playlist['spotify_url']}\">{open_label}</a>"
        
        return message.strip()
    
    @staticmethod
    def build_user_playlist_message(playlist: Dict, track_count: int, lang: str = "ru") -> str:
        """Создать сообщение для пользовательского плейлиста"""
        description = playlist.description or ("No description" if lang == "en" else "Нет описания")
        
        tracks_label = "Треков" if lang == "ru" else "Tracks"
        created_label = "Создан" if lang == "ru" else "Created"
        
        message = f"""
📋 <b>{playlist.name}</b>

📝 {description}
🎵 {tracks_label}: {track_count}
📅 {created_label}: {playlist.created_at.strftime('%d.%m.%Y')}
"""
        return message.strip()
    
    @staticmethod
    def build_search_results_message(tracks: List[Dict], lang: str = "ru") -> str:
        """Создать сообщение со списком найденных треков"""
        if not tracks:
            return "❌ Nothing found" if lang == "en" else "❌ Ничего не найдено"
        
        title = "🔍 <b>Результаты поиска:</b>" if lang == "ru" else "🔍 <b>Search results:</b>"
        message = f"{title}\n\n"
        
        for i, track in enumerate(tracks[:10], 1):
            duration = MessageBuilder.format_duration(track.get('duration_ms', 0))
            message += f"{i}. <b>{track['name']}</b>\n"
            message += f"   👤 {track['artist']} • ⏱ {duration}\n\n"
        
        return message.strip()
    
    @staticmethod
    def build_downloading_message(artist: str, track_name: str, lang: str = "ru") -> str:
        """Сообщение о начале скачивания"""
        return get_string("downloading", lang, name=track_name, artist=artist)
    
    @staticmethod
    def build_error_message(error_text: str, lang: str = "ru") -> str:
        """Сообщение об ошибке"""
        label = "Ошибка" if lang == "ru" else "Error"
        return f"❌ <b>{label}:</b> {error_text}"
