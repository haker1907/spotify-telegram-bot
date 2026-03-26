"""
Обработчик текстовых кнопок главного меню
"""
from telegram import Update
from telegram.ext import ContextTypes
from handlers.history import history_command
from handlers.playlist import my_playlists_command
from handlers.settings import settings_command
from handlers.start import help_command


from utils.strings import get_string


async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых кнопок главного меню"""
    text = update.message.text
    user_id = update.effective_user.id
    db = context.bot_data.get('db')
    
    lang = "ru"
    if db:
        user = await db.get_or_create_user(user_id, update.effective_user)
        lang = user.language
    
    # Сравниваем с русскими и английскими кнопками
    if text in [get_string("btn_settings", "ru"), get_string("btn_settings", "en")]:
        await settings_command(update, context)
    elif text in [get_string("btn_history", "ru"), get_string("btn_history", "en")]:
        await history_command(update, context)
    elif text in [get_string("btn_my_playlists", "ru"), get_string("btn_my_playlists", "en")]:
        await my_playlists_command(update, context)
    elif text in [get_string("btn_help", "ru"), get_string("btn_help", "en")]:
        await help_command(update, context)
    elif text in [get_string("btn_search", "ru"), get_string("btn_search", "en")]:
        await update.message.reply_text(
            get_string("search_welcome", lang),
            parse_mode='HTML'
        )
    elif text in [get_string("btn_back", "ru"), get_string("btn_back", "en")]:
        # Возврат в главное меню
        from handlers.start import start_command
        await start_command(update, context)
