"""
Главный файл Music Download бота
"""
import logging
import asyncio
import threading
import re
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)

# Импорты модулей
import config
from database import DatabaseManager
from services import SpotifyService, DownloadService
from services.telegram_storage_service import TelegramStorageService
from services.db_backup_service import DatabaseBackupService
from handlers import (
    start_command,
    help_command,
    handle_spotify_link,
    search_command,
    handle_text_search,
    my_playlists_command,
    create_playlist_command,
    handle_callback
)
from handlers.playlist import (
    receive_playlist_name,
    receive_playlist_description,
    cancel_playlist_creation,
    add_to_playlist_callback,
    select_playlist_callback,
    create_playlist_for_track_callback,
    cancel_playlist_selection_callback,
    WAITING_PLAYLIST_NAME,
    WAITING_PLAYLIST_DESCRIPTION
)
# Новые обработчики (Функции 3, 5, 8, 18)
from handlers.history import history_command, clear_history_command
from handlers.settings import (
    settings_command,
    quality_settings_callback,
    set_quality_callback,
    language_settings_callback,
    set_language_callback,
    toggle_autodelete_callback,
    format_settings_callback,
    set_format_callback,
    toggle_notifications_callback,
    settings_back_callback,
    settings_close_callback
)
# Обработчик кнопок меню
from handlers.menu import handle_menu_buttons

async def post_init(application: Application) -> None:
    """Инициализация после запуска (после pre-startup в startup.py)."""
    try:
        # БД уже восстановлена и инициализирована в startup.py
        db = DatabaseManager()
        await db.init_db()
        application.bot_data['db'] = db
        
        # Настройка сервиса бэкапов для периодической работы
        storage_service = TelegramStorageService()
        db_path = config.DATABASE_URL.replace('sqlite+aiosqlite:///', '')
        backup_service = DatabaseBackupService(
            storage_service=storage_service,
            db_path=db_path,
            db_manager=db
        )
        
        # Подключаем менеджер БД к сервису бэкапов для персистентной очистки
        backup_service.db = db
        
        # 3. Инициализация остальных сервисов
        spotify = SpotifyService()
        application.bot_data['spotify'] = spotify
        
        download_service = DownloadService()
        application.bot_data['download_service'] = download_service
        
        # 4. Запускаем периодический backup
        application.bot_data['backup_service'] = backup_service
        asyncio.create_task(backup_service.start_periodic_backup(interval=300))
        print("✅ Periodic database backup started (every 5 minutes)")
        
        logger.info("✅ Бот успешно инициализирован")
        
    except Exception as e:
        print(f"❌ Critical initialization error: {e}")
        import traceback
        traceback.print_exc()
        # Попробуем хотя бы базовую инициализацию, если это возможно
        if 'db' not in application.bot_data:
            db = DatabaseManager()
            await db.init_db()
            application.bot_data['db'] = db

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def post_shutdown(application: Application):
    """Очистка при остановке бота"""
    # 1. Делаем финальный бэкап
    backup_service = application.bot_data.get('backup_service')
    if backup_service:
        print("🛑 Shutting down... Creating final database backup...", flush=True)
        await backup_service.backup_to_telegram(force=True)

    # 2. Закрываем соединение с БД
    db = application.bot_data.get('db')
    if db:
        await db.close()
    logger.info("👋 Бот остановлен")


def main():
    """Главная функция запуска бота"""
    print(f"""
╔══════════════════════════════════════╗
║   🎵 Music Download Bot v2.0.0      ║
║      (БЕЗ Spotify API)              ║
╚══════════════════════════════════════╝

🚀 Запуск бота...
""")
    
    # Создаем приложение
    application = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
    # ========== ОБРАБОТЧИКИ КОМАНД ==========
    
    # Команда /start
    application.add_handler(CommandHandler("start", start_command))
    
    # Команда /login (для веба)
    from handlers.start import login_command
    application.add_handler(CommandHandler("login", login_command))
    
    # Команда /help
    application.add_handler(CommandHandler("help", help_command))
    
    # Команда /search
    application.add_handler(CommandHandler("search", search_command))
    
    # Команда /myplaylists
    application.add_handler(CommandHandler("myplaylists", my_playlists_command))
    
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("clearhistory", clear_history_command))
    application.add_handler(CommandHandler("settings", settings_command))
    
    # ========== CONVERSATION HANDLER ДЛЯ СОЗДАНИЯ ПЛЕЙЛИСТА ==========
    
    create_playlist_conv = ConversationHandler(
        entry_points=[
            CommandHandler("createplaylist", create_playlist_command),
            CallbackQueryHandler(create_playlist_command, pattern=r'^create_playlist$'),
            CallbackQueryHandler(create_playlist_for_track_callback, pattern=r'^plnew_')
        ],
        states={
            WAITING_PLAYLIST_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_playlist_name)
            ],
            WAITING_PLAYLIST_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_playlist_description)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_playlist_creation)],
        per_message=True,
    )
    application.add_handler(create_playlist_conv)
    
    # ========== ОБРАБОТЧИКИ СООБЩЕНИЙ ==========
    
    # Обработчик кнопок главного меню (должен быть ПЕРЕД Spotify ссылками)
    from utils.strings import STRINGS
    all_buttons = []
    for l in STRINGS:
        all_buttons.extend([
            STRINGS[l]["btn_settings"],
            STRINGS[l]["btn_history"],
            STRINGS[l]["btn_my_playlists"],
            STRINGS[l]["btn_help"],
            STRINGS[l]["btn_search"],
            STRINGS[l]["btn_back"]
        ])
    
    # Убираем дубликаты и создаем regex
    unique_buttons = list(set(all_buttons))
    btn_regex = f"^({'|'.join([re.escape(b) for b in unique_buttons])})$"
    
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(btn_regex), handle_menu_buttons))
    
    # Обработчик Spotify ссылок
    spotify_link_filter = filters.TEXT & filters.Regex(r'(https?://)?(open\.)?spotify\.com/(track|album|playlist|artist)/[a-zA-Z0-9]+')
    application.add_handler(MessageHandler(spotify_link_filter, handle_spotify_link))
    
    # Обработчик общего текстового поиска (не ссылка и не кнопка меню)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(btn_regex) & ~spotify_link_filter, handle_text_search))
    
    # ========== ОБРАБОТЧИКИ CALLBACK ЗАПРОСОВ ==========
    
    # Callback'и для настроек (Функция 3, 18)
    application.add_handler(CallbackQueryHandler(quality_settings_callback, pattern=r'^settings_quality$'))
    application.add_handler(CallbackQueryHandler(set_quality_callback, pattern=r'^quality_'))
    application.add_handler(CallbackQueryHandler(language_settings_callback, pattern=r'^settings_language$'))
    application.add_handler(CallbackQueryHandler(set_language_callback, pattern=r'^lang_'))
    application.add_handler(CallbackQueryHandler(toggle_autodelete_callback, pattern=r'^settings_autodelete$'))
    application.add_handler(CallbackQueryHandler(format_settings_callback, pattern=r'^settings_format$'))
    application.add_handler(CallbackQueryHandler(set_format_callback, pattern=r'^format_'))
    application.add_handler(CallbackQueryHandler(toggle_notifications_callback, pattern=r'^settings_notifications$'))
    application.add_handler(CallbackQueryHandler(settings_back_callback, pattern=r'^settings_back$'))
    application.add_handler(CallbackQueryHandler(settings_close_callback, pattern=r'^settings_close$'))
    
    # Callback'и для плейлистов (Добавление треков)
    application.add_handler(CallbackQueryHandler(add_to_playlist_callback, pattern=r'^addto_'))
    application.add_handler(CallbackQueryHandler(select_playlist_callback, pattern=r'^pladd_'))
    application.add_handler(CallbackQueryHandler(cancel_playlist_selection_callback, pattern=r'^plcancel_'))
    
    # Общий обработчик callback'ов (для остальных)
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # ========== ЗАПУСК БОТА ==========
    
    print(f"""
✅ Бот запущен и готов к работе!

📊 Статус:
   • Telegram Bot: ✅ Подключен
   • Spotify: ✅ Парсинг HTML (БЕЗ API)
   • База данных: ✅ SQLite
   • Скачивание: ✅ yt-dlp + YouTube

💡 Используйте Ctrl+C для остановки
""")
    
    # Запускаем polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        print(f"\n❌ Ошибка: {e}")
