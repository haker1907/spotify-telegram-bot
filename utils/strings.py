"""
Словарь строк интерфейса для локализации (RU/EN)
"""

STRINGS = {
    "ru": {
        # Главное меню (Текстовые кнопки)
        "btn_search": "🔍 Поиск музыки",
        "btn_history": "📜 История",
        "btn_favorites": "⭐ Избранное",
        "btn_settings": "⚙️ Настройки",
        "btn_help": "ℹ️ Помощь",
        "btn_back": "◀️ Назад",
        "btn_my_playlists": "📋 Плейлисты",
        
        # Настройки
        "settings_title": "⚙️ <b>Настройки</b>",
        "settings_quality": "🎵 <b>Качество звука:</b> {quality}",
        "settings_lang": "🌍 <b>Язык:</b> {lang}",
        "settings_autodelete": "🗑️ <b>Автоудаление:</b> {status}",
        "settings_format": "📁 <b>Формат:</b> {format}",
        "settings_notifications": "🔔 <b>Уведомления:</b> {status}",
        "settings_choose": "Выберите настройку для изменения:",
        
        "status_on": "Вкл",
        "status_off": "Выкл",
        "lang_name_ru": "Русский",
        "lang_name_en": "English",
        
        # Кнопки настроек
        "btn_set_quality": "🎵 Качество звука",
        "btn_set_lang": "🌍 Язык",
        "btn_set_autodelete": "🗑️ Автоудаление сообщений",
        "btn_set_format": "📁 Формат файлов",
        "btn_set_notifications": "🔔 Уведомления",
        "btn_close": "❌ Закрыть",
        
        # Качество
        "quality_title": "🎵 <b>Качество звука</b>\n\nВыберите битрейт для скачивания:",
        "quality_128_desc": "• <b>128 kbps</b> — Экономия места (~3 MB)",
        "quality_192_desc": "• <b>192 kbps</b> — Оптимально (~5 MB)",
        "quality_320_desc": "• <b>320 kbps</b> — Максимум MP3 (~8 MB)",
        "quality_1411_desc": "• <b>CD Quality</b> (44.1kHz/16bit) — ~1411 kbps",
        "quality_4600_desc": "• <b>Hi-Res</b> (96kHz/24bit) — ~4600 kbps",
        "quality_9200_desc": "• <b>Ultra Hi-Res</b> (192kHz/24bit) — ~9200 kbps",
        "quality_info": "\n💡 <i>Для FLAC рекомендуется CD Quality или выше. MP3 ограничен 320 kbps.</i>",
        "quality_success": "✅ Качество установлено: {quality}",
        
        # Язык
        "lang_title": "🌍 <b>Язык интерфейса</b>\n\nВыберите язык:",
        "lang_success": "✅ Язык установлен: {lang}",
        
        # Формат
        "format_title": "📁 <b>Формат файла</b>\n\nВыберите желаемый формат:",
        "format_mp3_desc": "• <b>MP3</b> — Универсальный формат, читается везде.",
        "format_flac_desc": "• <b>FLAC</b> — Lossless (без потерь), высокое качество (до 9000+ kbps), большой размер.",
        "format_success": "✅ Формат установлен: {format}",
        
        # Уведомления
        "notifications_title": "🔔 <b>Уведомления</b>",
        "notifications_success": "✅ Уведомления {status}",
        
        # Поиск
        "search_welcome": "🔍 <b>Поиск музыки</b>\n\nОтправьте мне ссылку на трек из Spotify, и я скачаю его для вас!\n\nПример:\n<code>https://open.spotify.com/track/...</code>",
        "downloading": "📥 <b>Загрузка...</b>\n\n<i>{name} - {artist}</i>\n\nПожалуйста, подождите.",
        "searching": "🔍 Ищу информацию о треке...",
        "from_cache": "📤 Отправляю из кэша...",
        "uploading": "📤 Загружаю файл в Telegram...",
        "error_download": "❌ Ошибка при скачивании трека. Попробуйте еще раз позже.",
        "error_file_too_large": "⚠️ <b>Файл слишком большой!</b>\n\nРазмер: {size} MB\nЛимит Telegram: 50 MB\n\n💡 Пожалуйста, выберите качество ниже (например, 320 kbps или CD) в /settings, чтобы файл прошел по размеру.",
        "track_caption": "🎵 <b>{name}</b>\n👤 {artist}\n\n🎧 {quality} kbps",
        
        # Callbacks & Playlists
        "action_cancelled": "❌ Действие отменено",
        "playlist_creation_title": "📋 <b>Создание нового плейлиста</b>",
        "playlist_creation_info": "Используйте команду /createplaylist для создания плейлиста",
        "playlists_my": "📋 <b>Мои плейлисты:</b>",
        "playlists_empty": "📋 <b>Мои плейлисты</b>\n\nУ вас пока нет плейлистов.\nСоздайте свой первый плейлист!",
        "playlist_not_found": "❌ Плейлист не найден",
        "track_not_found": "❌ Трек не найден",
        "preview_unavailable": "❌ Превью недоступно для этого трека",
        "preview_caption": "🎵 Превью: <b>{name}</b> - {artist}",
        "add_to_playlist_choose": "📋 <b>Выберите плейлист:</b>",
        "add_to_playlist_success": "✅ <b>Трек добавлен в плейлист!</b>\n\n🎵 {track}\n📋 Плейлист: {playlist}",
        "add_to_playlist_exists": "⚠️ Этот трек уже есть в плейлисте",
        "delete_playlist_confirm": "⚠️ <b>Удалить плейлист?</b>\n\n📋 {name}\n\nЭто действие нельзя отменить!",
        "delete_playlist_success": "✅ Плейлист удален",
        "remove_from_playlist_success": "✅ Трек удален из плейлиста",
        "playlist_tracks_count": "({count} треков)",
        "playlist_empty_info": "Плейлист пуст. Добавьте треки!",
        
        # История и избранное
        "history_empty": "📜 История скачиваний пуста",
        "favorites_empty": "⭐ У вас пока нет избранных треков",
        "history_title": "📜 <b>История скачиваний (последние {count}):</b>\n\n",
        "btn_clear_history": "🗑️ Очистить историю",
        "history_cleared": "✅ История скачиваний очищена",
        
        # Общие кнопки
        "btn_cancel": "❌ Отмена",
        "btn_skip": "➡️ Пропустить",
        "btn_done": "✅ Готово",
    },
    "en": {
        # Main Menu (Reply Buttons)
        "btn_search": "🔍 Music Search",
        "btn_history": "📜 History",
        "btn_favorites": "⭐ Favorites",
        "btn_settings": "⚙️ Settings",
        "btn_help": "ℹ️ Help",
        "btn_back": "◀️ Back",
        "btn_my_playlists": "📋 Playlists",
        
        # Settings
        "settings_title": "⚙️ <b>Settings</b>",
        "settings_quality": "🎵 <b>Audio Quality:</b> {quality}",
        "settings_lang": "🌍 <b>Language:</b> {lang}",
        "settings_autodelete": "🗑️ <b>Auto-delete:</b> {status}",
        "settings_format": "📁 <b>Format:</b> {format}",
        "settings_notifications": "🔔 <b>Notifications:</b> {status}",
        "settings_choose": "Choose a setting to change:",
        
        "status_on": "On",
        "status_off": "Off",
        "lang_name_ru": "Russian",
        "lang_name_en": "English",
        
        # Settings Buttons
        "btn_set_quality": "🎵 Audio Quality",
        "btn_set_lang": "🌍 Language",
        "btn_set_autodelete": "🗑️ Auto-delete messages",
        "btn_set_format": "📁 File format",
        "btn_set_notifications": "🔔 Notifications",
        "btn_close": "❌ Close",
        
        # Quality
        "quality_title": "🎵 <b>Audio Quality</b>\n\nChoose bitrate for download:",
        "quality_128_desc": "• <b>128 kbps</b> — Space saving (~3 MB)",
        "quality_192_desc": "• <b>192 kbps</b> — Optimal (~5 MB)",
        "quality_320_desc": "• <b>320 kbps</b> — Max MP3 (~8 MB)",
        "quality_1411_desc": "• <b>CD Quality</b> (44.1kHz/16bit) — ~1411 kbps",
        "quality_4600_desc": "• <b>Hi-Res</b> (96kHz/24bit) — ~4600 kbps",
        "quality_9200_desc": "• <b>Ultra Hi-Res</b> (192kHz/24bit) — ~9200 kbps",
        "quality_info": "\n💡 <i>For FLAC, CD Quality or higher is recommended. MP3 is capped at 320 kbps.</i>",
        "quality_success": "✅ Quality set: {quality}",
        
        # Language
        "lang_title": "🌍 <b>Interface Language</b>\n\nChoose your language:",
        "lang_success": "✅ Language set: {lang}",
        
        # Format
        "format_title": "📁 <b>File Format</b>\n\nChoose desired format:",
        "format_mp3_desc": "• <b>MP3</b> — Universal format, works everywhere.",
        "format_flac_desc": "• <b>FLAC</b> — Lossless quality (up to 9000+ kbps), large file size.",
        "format_success": "✅ Format set: {format}",
        
        # Notifications
        "notifications_title": "🔔 <b>Notifications</b>",
        "notifications_success": "✅ Notifications {status}",
        
        # Search
        "search_welcome": "🔍 <b>Music Search</b>\n\nSend me a Spotify track link, and I'll download it for you!\n\nExample:\n<code>https://open.spotify.com/track/...</code>",
        "downloading": "📥 <b>Downloading...</b>\n\n<i>{name} - {artist}</i>\n\nPlease wait.",
        "searching": "🔍 Searching for track info...",
        "from_cache": "📤 Sending from cache...",
        "uploading": "📤 Uploading file to Telegram...",
        "error_download": "❌ Error downloading track. Please try again later.",
        "error_file_too_large": "⚠️ <b>File too large!</b>\n\nSize: {size} MB\nTelegram Limit: 50 MB\n\n💡 Please choose a lower quality (e.g., 320 kbps or CD) in /settings so the file can be sent.",
        "track_caption": "🎵 <b>{name}</b>\n👤 {artist}\n\n🎧 {quality} kbps",

        # Callbacks & Playlists
        "action_cancelled": "❌ Action cancelled",
        "playlist_creation_title": "📋 <b>Creating new playlist</b>",
        "playlist_creation_info": "Use /createplaylist command to create a playlist",
        "playlists_my": "📋 <b>My Playlists:</b>",
        "playlists_empty": "📋 <b>My Playlists</b>\n\nYou don't have any playlists yet.\nCreate your first playlist!",
        "playlist_not_found": "❌ Playlist not found",
        "track_not_found": "❌ Track not found",
        "preview_unavailable": "❌ Preview unavailable for this track",
        "preview_caption": "🎵 Preview: <b>{name}</b> - {artist}",
        "add_to_playlist_choose": "📋 <b>Choose a playlist:</b>",
        "add_to_playlist_success": "✅ <b>Track added to playlist!</b>\n\n🎵 {track}\n📋 Playlist: {playlist}",
        "add_to_playlist_exists": "⚠️ This track is already in the playlist",
        "delete_playlist_confirm": "⚠️ <b>Delete playlist?</b>\n\n📋 {name}\n\nThis action cannot be undone!",
        "delete_playlist_success": "✅ Playlist deleted",
        "remove_from_playlist_success": "✅ Track removed from playlist",
        "playlist_tracks_count": "({count} tracks)",
        "playlist_empty_info": "Playlist is empty. Add tracks!",
        
        # History & Favorites
        "history_empty": "📜 Download history is empty",
        "favorites_empty": "⭐ You don't have any favorite tracks yet",
        "history_title": "📜 <b>Download history (last {count}):</b>\n\n",
        "btn_clear_history": "🗑️ Clear history",
        "history_cleared": "✅ Download history cleared",
        
        # Common Buttons
        "btn_cancel": "❌ Cancel",
        "btn_skip": "➡️ Skip",
        "btn_done": "✅ Done",
    }
}


def get_string(key: str, language: str = "ru", **kwargs) -> str:
    """
    Получить локализованную строку по ключу.
    
    Args:
        key: Ключ строки
        language: Код языка (ru/en)
        **kwargs: Параметры для форматирования строки
        
    Returns:
        Локализованная и отформатированная строка
    """
    # Если язык не поддерживается, используем русский
    if language not in STRINGS:
        language = "ru"
        
    # Если ключа нет в выбранном языке, пробуем найти в русском
    text = STRINGS[language].get(key) or STRINGS["ru"].get(key, key)
    
    # Форматируем, если переданы параметры
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError, IndexError):
            return text
            
    return text
