"""
Клавиатуры для Telegram бота
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from .strings import get_string


class KeyboardBuilder:
    """Класс для создания клавиатур (с поддержкой локализации)"""
    
    @staticmethod
    def main_menu(lang: str = "ru"):
        """Главное меню"""
        keyboard = [
            [KeyboardButton(get_string("btn_search", lang))],
            [KeyboardButton(get_string("btn_history", lang)), KeyboardButton(get_string("btn_my_playlists", lang))],
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


def get_track_actions_keyboard(track_id: str, is_favorite: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура действий с треком (без Избранного)"""
    keyboard = []
    
    # Первая строка: Скачать снова
    keyboard.append([InlineKeyboardButton("🔄 Скачать снова", callback_data=f"redownload_{track_id}")])
    
    # Вторая строка: Плейлисты
    keyboard.append([InlineKeyboardButton("➕ В плейлист", callback_data=f"addto_{track_id}")])
    
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
