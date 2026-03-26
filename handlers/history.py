"""
Обработчики для истории скачиваний (Функция 5)
"""
import os
from telegram import Update
from telegram.ext import ContextTypes
from utils.keyboards import get_track_actions_keyboard, get_pagination_keyboard
from utils.strings import get_string


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать историю скачиваний"""
    user_id = update.effective_user.id
    db = context.bot_data.get('db')
    
    if not db:
        await update.message.reply_text("❌ Database error")
        return
    
    # Получаем язык пользователя
    user = await db.get_or_create_user(user_id, update.effective_user)
    lang = user.language
    
    # Получаем историю из БД
    try:
        # TODO: Реализовать метод get_download_history в db_manager
        history = await db.get_download_history(user_id, limit=10)
        
        if not history:
            await update.message.reply_text(
                get_string("history_empty", lang),
                parse_mode='HTML'
            )
            return
        
        # Формируем сообщение
        message = get_string("history_title", lang, count=len(history))
        
        for i, item in enumerate(history, 1):
            track = item['track']
            downloaded_at = item['downloaded_at'].strftime('%d.%m.%Y %H:%M')
            quality = item['quality']
            
            message += f"{i}. 🎵 <b>{track['name']}</b>\n"
            message += f"   👤 {track['artist']}\n"
            message += f"   📅 {downloaded_at} | {quality}\n\n"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        print(f"❌ Ошибка получения истории: {e}")
        await update.message.reply_text("❌ Error getting history" if lang == "en" else "❌ Ошибка при получении истории")


async def clear_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистить историю скачиваний"""
    user_id = update.effective_user.id
    db = context.bot_data.get('db')
    
    if not db:
        await update.message.reply_text("❌ Database error")
        return
        
    user = await db.get_or_create_user(user_id, update.effective_user)
    lang = user.language
    
    try:
        # TODO: Реализовать метод clear_download_history в db_manager
        await db.clear_download_history(user_id)
        
        await update.message.reply_text(
            get_string("history_cleared", lang),
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"❌ Ошибка очистки истории: {e}")
        await update.message.reply_text("❌ Error" if lang == "en" else "❌ Ошибка")
