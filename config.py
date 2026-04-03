"""
Конфигурация бота и переменные окружения
"""
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    print("⚠️  TELEGRAM_BOT_TOKEN не найден в переменных окружения!")
    print("💡 Создайте .env файл или установите переменную окружения")
    raise ValueError("❌ TELEGRAM_BOT_TOKEN обязателен для работы бота!")

# База данных
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Используем абсолютный путь для SQLite (в папке data для Railway)
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite+aiosqlite:///{os.path.join(BASE_DIR, "data", "spotify_bot.db")}')

# Web App URL (для авторизации через Telegram)
WEB_APP_URL = os.getenv('WEB_APP_URL', 'http://localhost:5000')
BOT_PUBLIC_URL = os.getenv('BOT_PUBLIC_URL', 'https://t.me')
# Нормализуем URL: если протокол не указан, используем https по умолчанию
if WEB_APP_URL and not WEB_APP_URL.startswith(('http://', 'https://')):
    WEB_APP_URL = f"https://{WEB_APP_URL}"
if WEB_APP_URL == 'http://localhost:5000':
    print("WEB_APP_URL не установлен! Ссылки будут вести на localhost.")
else:
    print(f"WEB_APP_URL установлен: {WEB_APP_URL}")

# Telegram Storage Channel (для хранения музыкальных файлов)
STORAGE_CHANNEL_ID = os.getenv('STORAGE_CHANNEL_ID', '-1003748020768')
print(f"Storage Channel ID: {STORAGE_CHANNEL_ID}")

# Настройки бота
BOT_NAME = "Music Download Bot"
BOT_VERSION = "2.1.0"

# Лимиты
MAX_PLAYLIST_NAME_LENGTH = 100
MAX_TRACKS_PER_PLAYLIST = 500
MAX_SEARCH_RESULTS = 10

# Сообщения
WELCOME_MESSAGE = """
🎵 <b>Добро пожаловать в Music Download Bot!</b>

Я автоматически скачиваю музыку из Spotify!

<b>Как использовать:</b>
1. Откройте Spotify и найдите трек
2. Нажмите "Поделиться" → "Копировать ссылку"
3. Отправьте мне ссылку
4. Получите MP3 файл!

<b>Пример ссылки:</b>
<code>https://open.spotify.com/track/...</code>

<b>Команды:</b>
/start - Главное меню
/help - Помощь
/myplaylists - Мои плейлисты

Просто отправьте ссылку Spotify! 🎶
"""

HELP_MESSAGE = """
📖 <b>Справка по использованию бота</b>

<b>🎵 Как скачать музыку:</b>

1. Откройте Spotify (приложение или браузер)
2. Найдите нужный трек
3. Нажмите "Поделиться" → "Копировать ссылку"
4. Отправьте ссылку мне

<b>Пример:</b>
<code>https://open.spotify.com/track/3n3Ppam7vgaVa1iaRUc9Lp</code>

Бот автоматически:
✅ Извлечёт название и исполнителя
✅ Найдёт трек на YouTube
✅ Скачает и отправит MP3

<b>📋 Плейлисты:</b>
Сохраняйте треки в плейлисты:
• /myplaylists - Посмотреть плейлисты
• /createplaylist - Создать новый

<b>💡 Особенности:</b>
• Работает БЕЗ Spotify API
• Автоматическое скачивание
• Качество: 192 kbps MP3
• Обложки треков

<b>⚠️ Важно:</b>
• Скачивание занимает 10-30 секунд
• Некоторые треки могут быть недоступны
• Поддерживаются только отдельные треки

Нужна помощь? Напишите /start
"""

print(f"✅ Конфигурация загружена: {BOT_NAME} v{BOT_VERSION}")
print("ℹ️  Бот работает БЕЗ Spotify API - автоматическое скачивание")
