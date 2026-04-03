"""
Обработчики для избранных треков (Функция 8)
"""
from telegram import Update
from telegram.ext import ContextTypes
from utils.keyboards import get_track_actions_keyboard
from utils.strings import get_string


async def favorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать избранные треки"""
    user_id = update.effective_user.id
    db = context.bot_data.get('db')
    
    if not db:
        await update.message.reply_text("❌ Database error")
        return
    
    # Получаем пользователя
    user = await db.get_or_create_user(user_id, update.effective_user)
    lang = user.language
    
    try:
        favorites = await db.get_favorites(user_id)
        
        if not favorites:
            await update.message.reply_text(
                get_string("favorites_empty", lang),
                parse_mode='HTML'
            )
            return
        
        # Формируем сообщение
        title = get_string("favorites_title", lang)
        count_text = get_string("favorites_total", lang, count=len(favorites))
        message = f"{title}\n\n{count_text}\n\n"
        
        for i, fav in enumerate(favorites[:10], 1):  # Показываем первые 10
            track = fav['track']
            added_at = fav['added_at'].strftime('%d.%m.%Y')
            added_text = get_string("favorites_added", lang)
            
            message += f"{i}. 🎵 <b>{track['name']}</b>\n"
            message += f"   👤 {track['artist']}\n"
            message += f"   📅 {added_text}: {added_at}\n\n"
        
        if len(favorites) > 10:
            more_text = get_string("favorites_more", lang, count=len(favorites) - 10)
            message += f"\n... и {more_text}"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        print(f"❌ Ошибка получения избранного: {e}")
        await update.message.reply_text("❌ Error getting favorites" if lang == "en" else "❌ Ошибка при получении избранного")


async def add_to_favorites_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить трек в избранное (callback)"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    track_id = query.data.replace('fav_', '')
    db = context.bot_data.get('db')
    
    if not db:
        return
    
    user = await db.get_or_create_user(user_id, update.effective_user)
    lang = user.language
    
    try:
        await db.add_to_favorites(user_id, track_id)
        
        msg = get_string("favorites_added_ok", lang)
        await query.answer(msg, show_alert=True)
        
        # Обновляем клавиатуру
        keyboard = get_track_actions_keyboard(track_id, is_favorite=True, lang=lang)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        
    except Exception as e:
        print(f"❌ Ошибка добавления в избранное: {e}")
        await query.answer("❌ Error" if lang == "en" else "❌ Ошибка", show_alert=True)


async def remove_from_favorites_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить трек из избранного (callback)"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    track_id = query.data.replace('unfav_', '')
    db = context.bot_data.get('db')
    
    if not db:
        return
        
    user = await db.get_or_create_user(user_id, update.effective_user)
    lang = user.language
    
    try:
        await db.remove_from_favorites(user_id, track_id)
        
        msg = get_string("favorites_removed_ok", lang)
        await query.answer(msg, show_alert=True)
        
        # Обновляем клавиатуру
        keyboard = get_track_actions_keyboard(track_id, is_favorite=False, lang=lang)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        
    except Exception as e:
        print(f"❌ Ошибка удаления из избранного: {e}")
        await query.answer("❌ Error" if lang == "en" else "❌ Ошибка", show_alert=True)
