"""
Клавиатуры для Telegram бота
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from .strings import get_string
import config


class KeyboardBuilder:
    """Класс для создания клавиатур (с поддержкой локализации)"""
    
    @staticmethod
    def main_menu(lang: str = "ru"):
        """Главное меню"""
        keyboard = [
            [KeyboardButton(get_string("btn_search", lang))],
            [KeyboardButton(get_string("btn_history", lang)), KeyboardButton(get_string("btn_my_playlists", lang))],
            [KeyboardButton(get_string("btn_favorites", lang))],
            [KeyboardButton(get_string("btn_settings", lang)), KeyboardButton(get_string("btn_help", lang))]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    @staticmethod
    def back_button(lang: str = "ru"):
        """Кнопка назад"""
        keyboard = [[KeyboardButton(get_string("btn_back", lang))]]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    @staticmethod
    def user_playlists(playlists, lang: str = "ru"):
        """Клавиатура со списком плейлистов пользователя"""
        keyboard = []
        for playlist in playlists:
            keyboard.append([InlineKeyboardButton(
                f"📁 {playlist.name}", 
                callback_data=f"view_playlist_{playlist.id}"
            )])
        keyboard.append([InlineKeyboardButton("➕ Create Playlist" if lang == "en" else "➕ Создать плейлист", callback_data="create_playlist")])
        keyboard.append([InlineKeyboardButton(get_string("btn_back", lang), callback_data="back_to_menu")])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def playlist_selection(playlists, track_id: str, lang: str = "ru"):
        """Клавиатура выбора плейлиста для добавления трека"""
        keyboard = []
        for playlist in playlists:
            keyboard.append([InlineKeyboardButton(
                f"📁 {playlist.name}", 
                callback_data=f"pladd_{track_id}_{playlist.id}"
            )])
        
        keyboard.append([InlineKeyboardButton("➕ New Playlist" if lang == "en" else "➕ Новый плейлист", callback_data=f"plnew_{track_id}")])
        keyboard.append([InlineKeyboardButton(get_string("btn_back", lang), callback_data=f"plcancel_{track_id}")])
        
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def playlist_tracks(playlist_id, tracks, lang: str = "ru"):
        """Клавиатура со списком треков в плейлисте"""
        keyboard = []
        for track in tracks:
            keyboard.append([InlineKeyboardButton(
                f"🎵 {track.name} - {track.artist}", 
                callback_data=f"track_in_playlist_{track.id}_{playlist_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🗑 Delete Playlist" if lang == "en" else "🗑 Удалить плейлист", callback_data=f"delete_playlist_{playlist_id}")])
        keyboard.append([InlineKeyboardButton(get_string("btn_back", lang), callback_data="menu_playlists")])
        
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def track_in_playlist_actions(track_id, playlist_id, lang: str = "ru"):
        """Действия с треком внутри плейлиста"""
        keyboard = [
            [InlineKeyboardButton("⬇️ Download" if lang == "en" else "⬇️ Скачать", callback_data=f"download_{track_id}")],
            [InlineKeyboardButton("❌ Remove" if lang == "en" else "❌ Удалить из плейлиста", callback_data=f"remove_from_playlist_{track_id}_{playlist_id}")],
            [InlineKeyboardButton(get_string("btn_back", lang), callback_data=f"view_playlist_{playlist_id}")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def confirm_action(action: str, target_id: str, lang: str = "ru"):
        """Клавиатура подтверждения действия (удаление плейлиста)"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes" if lang == "en" else "✅ Да", callback_data=f"confirm_{action}_{target_id}"),
                InlineKeyboardButton("❌ No" if lang == "en" else "❌ Нет", callback_data=f"view_playlist_{target_id}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)


def get_quality_keyboard(lang: str = "ru", current: str = "192", file_format: str = "mp3") -> InlineKeyboardMarkup:
    """Клавиатура выбора качества звука (Функция 3)"""
    if file_format == 'flac':
        keyboard = [
            [
                InlineKeyboardButton(f"💿 1411 kbps (CD){' ✅' if current == '1411' else ''}", callback_data="quality_1411"),
                InlineKeyboardButton(f"✨ 2300 kbps (48kHz/24bit){' ✅' if current == '2300' else ''}", callback_data="quality_2300"),
            ],
            [
                InlineKeyboardButton(f"🔥 4600 kbps (96kHz/24bit){' ✅' if current == '4600' else ''}", callback_data="quality_4600"),
                InlineKeyboardButton(f"💎 9200 kbps (192kHz/24bit){' ✅' if current == '9200' else ''}", callback_data="quality_9200"),
            ],
            [InlineKeyboardButton(get_string("btn_back", lang), callback_data="settings_back")]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton(f"🎵 128 kbps{' ✅' if current == '128' else ''}", callback_data="quality_128"),
                InlineKeyboardButton(f"🎵 192 kbps{' ✅' if current == '192' else ''}", callback_data="quality_192"),
                InlineKeyboardButton(f"🎵 320 kbps{' ✅' if current == '320' else ''}", callback_data="quality_320"),
            ],
            [InlineKeyboardButton(get_string("btn_back", lang), callback_data="settings_back")]
        ]
    return InlineKeyboardMarkup(keyboard)


def get_track_actions_keyboard(track_id: str, is_favorite: bool = False, lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура действий с треком"""
    keyboard = []
    
    # Первая строка: Скачать снова
    keyboard.append([InlineKeyboardButton("🔄 Скачать снова" if lang == "ru" else "🔄 Download again", callback_data=f"redownload_{track_id}")])
    
    # Вторая строка: Плейлисты
    keyboard.append([InlineKeyboardButton("➕ В плейлист" if lang == "ru" else "➕ Add to playlist", callback_data=f"addto_{track_id}")])

    if is_favorite:
        keyboard.append([InlineKeyboardButton("💔 Убрать из избранного" if lang == "ru" else "💔 Remove favorite", callback_data=f"unfav_{track_id}")])
    else:
        keyboard.append([InlineKeyboardButton("⭐ В избранное" if lang == "ru" else "⭐ Add to favorites", callback_data=f"fav_{track_id}")])

    share_url = f"https://t.me/share/url?url={config.BOT_PUBLIC_URL}&text={get_string('share_text', lang)}"
    keyboard.append([InlineKeyboardButton(get_string("btn_share_bot", lang), url=share_url)])
    
    return InlineKeyboardMarkup(keyboard)


def get_settings_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура настроек (Функция 18)"""
    keyboard = [
        [InlineKeyboardButton(get_string("btn_set_quality", lang), callback_data="settings_quality")],
        [InlineKeyboardButton(get_string("btn_set_lang", lang), callback_data="settings_language")],
        [InlineKeyboardButton(get_string("btn_set_autodelete", lang), callback_data="settings_autodelete")],
        [InlineKeyboardButton(get_string("btn_set_format", lang), callback_data="settings_format")],
        [InlineKeyboardButton(get_string("btn_set_notifications", lang), callback_data="settings_notifications")],
        [InlineKeyboardButton(get_string("btn_close", lang), callback_data="settings_close")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_language_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура выбора языка"""
    keyboard = [
        [
            InlineKeyboardButton(f"{get_string('lang_name_ru', lang)}{' ✅' if lang == 'ru' else ''}", callback_data="lang_ru"),
            InlineKeyboardButton(f"{get_string('lang_name_en', lang)}{' ✅' if lang == 'en' else ''}", callback_data="lang_en"),
        ],
        [InlineKeyboardButton(get_string("btn_back", lang), callback_data="settings_back")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_format_keyboard(lang: str = "ru", current: str = "mp3") -> InlineKeyboardMarkup:
    """Клавиатура выбора формата (Функция 18)"""
    keyboard = [
        [
            InlineKeyboardButton(f"MP3{' ✅' if current == 'mp3' else ''}", callback_data="format_mp3"),
            InlineKeyboardButton(f"FLAC{' ✅' if current == 'flac' else ''}", callback_data="format_flac"),
        ],
        [InlineKeyboardButton(get_string("btn_back", lang), callback_data="settings_back")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_search_results_keyboard(results: list) -> InlineKeyboardMarkup:
    """Клавиатура результатов поиска (Функция 4)"""
    keyboard = []
    
    for i, result in enumerate(results[:5]):  # Максимум 5 результатов
        track_name = result.get('name', 'Unknown')
        artist = result.get('artist', 'Unknown')
        track_id = result.get('id', '')
        
        button_text = f"🎵 {track_name} - {artist}"[:64]  # Telegram лимит
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"download_{track_id}")])
    
    return InlineKeyboardMarkup(keyboard)


def get_collection_keyboard(results: list, collection_type: str, collection_id: str, lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура коллекции + кнопка пакетного скачивания."""
    keyboard = get_search_results_keyboard(results).inline_keyboard
    batch_text = f"⬇️ Скачать все ({min(len(results), 10)})" if lang == "ru" else f"⬇️ Download all ({min(len(results), 10)})"
    keyboard.append([InlineKeyboardButton(batch_text, callback_data=f"batchdl_{collection_type}_{collection_id}")])
    return InlineKeyboardMarkup(keyboard)


def get_spotify_playlist_search_keyboard(playlists: list, lang: str = "ru") -> InlineKeyboardMarkup:
    """Результаты поиска плейлистов Spotify: сначала плейлисты, затем переход к поиску треков."""
    keyboard = []
    for p in playlists[:8]:
        name = (p.get("name") or "Playlist").replace("\n", " ").strip()
        owner = (p.get("owner") or "").replace("\n", " ").strip()
        ntot = p.get("total_tracks")
        extra = ""
        if isinstance(ntot, int):
            extra = f" · {ntot}"
        if owner:
            label = f"📀 {name} — {owner}{extra}"
        else:
            label = f"📀 {name}{extra}"
        label = label[:64]
        keyboard.append([InlineKeyboardButton(label, callback_data=f"spl_{p['id']}")])
    keyboard.append([
        InlineKeyboardButton(
            "🎵 Искать треки" if lang == "ru" else "🎵 Search tracks instead",
            callback_data="show_spotify_track_search",
        ),
    ])
    return InlineKeyboardMarkup(keyboard)


def get_single_spotify_playlist_keyboard(playlist: dict, lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура для одиночной ссылки на плейлист: одна кнопка открыть плейлист."""
    pl_id = playlist.get("id") or ""
    name = (playlist.get("name") or "Playlist").replace("\n", " ").strip()
    owner = (playlist.get("owner") or "").replace("\n", " ").strip()
    ntot = playlist.get("total_tracks")
    extra = f" · {ntot}" if isinstance(ntot, int) else ""
    if owner:
        label = f"📀 {name} — {owner}{extra}"
    else:
        label = f"📀 {name}{extra}"
    label = label[:64]
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=f"spl_{pl_id}")]])


def get_playlist_tracks_browse_keyboard(
    tracks: list,
    collection_type: str,
    collection_id: str,
    page: int,
    per_page: int = 10,
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    """Страница треков плейлиста (пагинация) + пакетное скачивание первых 10 из всего плейлиста."""
    total = len(tracks)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    chunk = tracks[page * per_page : (page + 1) * per_page]
    keyboard = []
    for t in chunk:
        tid = t.get("id") or ""
        name = (t.get("name") or "?")[:32]
        artist = (t.get("artist") or "")[:24]
        btn = f"🎵 {name} — {artist}"[:64]
        keyboard.append([InlineKeyboardButton(btn, callback_data=f"download_{tid}")])
    first_n = min(10, total)
    batch_text = (
        f"⬇️ Скачать первые ({first_n})" if lang == "ru" else f"⬇️ Download first ({first_n})"
    )
    keyboard.append([InlineKeyboardButton(batch_text, callback_data=f"batchdl_{collection_type}_{collection_id}")])
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=f"splp_{collection_id}_{page - 1}"))
    nav_row.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"splp_{collection_id}_{page + 1}"))
    keyboard.append(nav_row)
    return InlineKeyboardMarkup(keyboard)


def get_pagination_keyboard(page: int, total_pages: int, prefix: str) -> InlineKeyboardMarkup:
    """Клавиатура пагинации"""
    keyboard = []
    
    row = []
    if page > 1:
        row.append(InlineKeyboardButton("◀️ Назад", callback_data=f"{prefix}_page_{page-1}"))
    
    row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    
    if page < total_pages:
        row.append(InlineKeyboardButton("Вперёд ▶️", callback_data=f"{prefix}_page_{page+1}"))
    
    keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)
