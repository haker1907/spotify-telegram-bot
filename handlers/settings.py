"""
Обработчики настроек (Функция 3, 18)
"""
from telegram import Update
from telegram.ext import ContextTypes
from utils.keyboards import (
    get_settings_keyboard,
    get_quality_keyboard,
    get_language_keyboard,
    get_format_keyboard
)
from utils.strings import get_string


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню настроек"""
    user_id = update.effective_user.id
    db = context.bot_data.get('db')
    
    if not db:
        await update.message.reply_text("❌ База данных недоступна")
        return
    
    try:
        user = await db.get_or_create_user(user_id, update.effective_user)
        lang = user.language
        
        message = get_string(
            "settings_title", lang
        ) + "\n\n" + get_string(
            "settings_quality", lang, quality=user.preferred_quality
        ) + "\n" + get_string(
            "settings_lang", lang, lang=get_string(f"lang_name_{user.language}", lang)
        ) + "\n" + get_string(
            "settings_autodelete", lang, status=get_string("status_on" if user.auto_delete else "status_off", lang)
        ) + "\n" + get_string(
            "settings_format", lang, format=user.format.upper()
        ) + "\n" + get_string(
            "settings_notifications", lang, status=get_string("status_on" if user.notifications else "status_off", lang)
        ) + "\n\n" + get_string("settings_choose", lang)
        
        keyboard = get_settings_keyboard(lang)
        await update.message.reply_text(
            message.strip(),
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
    except Exception as e:
        print(f"❌ Ошибка получения настроек: {e}")
        await update.message.reply_text("❌ Ошибка при получении настроек")


async def quality_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройка качества MP3"""
    query = update.callback_query
    user_id = update.effective_user.id
    db = context.bot_data.get('db')
    user = await db.get_or_create_user(user_id, update.effective_user)
    lang = user.language
    
    message = get_string("quality_title", lang) + "\n\n" + \
              get_string("quality_128_desc", lang) + "\n" + \
              get_string("quality_192_desc", lang) + "\n" + \
              get_string("quality_320_desc", lang) + "\n" + \
              get_string("quality_info", lang)
    
    keyboard = get_quality_keyboard(lang, current=user.preferred_quality, file_format=user.format)
    await query.edit_message_text(
        message.strip(),
        parse_mode='HTML',
        reply_markup=keyboard
    )


async def set_quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить качество MP3"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    quality = query.data.replace('quality_', '')
    db = context.bot_data.get('db')
    
    if not db:
        await query.answer("❌ База данных недоступна", show_alert=True)
        return
    
    try:
        await db.update_user_setting(user_id, 'preferred_quality', quality)
        
        user = await db.get_or_create_user(user_id, update.effective_user)
        lang = user.language
        
        # Формируем текст подтверждения
        quality_label = quality if int(quality) <= 320 else f"{quality} kbps (Hi-Res)"
        await query.answer(get_string("quality_success", lang, quality=quality_label), show_alert=True)
        
        # Обновляем сообщение с настройками
        await show_main_settings(query, user, lang)
        
    except Exception as e:
        print(f"❌ Ошибка установки качества: {e}")
        await query.answer("❌ Ошибка", show_alert=True)


async def language_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройка языка"""
    query = update.callback_query
    user_id = update.effective_user.id
    db = context.bot_data.get('db')
    user = await db.get_or_create_user(user_id, update.effective_user)
    lang = user.language
    
    keyboard = get_language_keyboard(lang)
    await query.edit_message_text(
        get_string("lang_title", lang),
        parse_mode='HTML',
        reply_markup=keyboard
    )


async def set_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить язык"""
    query = update.callback_query
    language = query.data.replace('lang_', '')
    user_id = update.effective_user.id
    db = context.bot_data.get('db')
    
    if not db:
        await query.answer("❌ База данных недоступна", show_alert=True)
        return
    
    await query.answer()
    
    try:
        await db.update_user_setting(user_id, 'language', language)
        
        # Перезагружаем пользователя с новым языком
        user = await db.get_or_create_user(user_id, update.effective_user)
        lang = user.language
        
        lang_name = get_string(f"lang_name_{lang}", lang)
        await query.answer(get_string("lang_success", lang, lang=lang_name), show_alert=True)
        
        # Обновляем сообщение с настройками
        await show_main_settings(query, user, lang)
        
    except Exception as e:
        print(f"❌ Ошибка установки языка: {e}")
        await query.answer("❌ Ошибка", show_alert=True)


async def toggle_autodelete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключить автоудаление"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = context.bot_data.get('db')
    user = await db.get_or_create_user(user_id, update.effective_user)
    
    new_value = not user.auto_delete
    await db.update_user_setting(user_id, 'auto_delete', new_value)
    
    user = await db.get_or_create_user(user_id, update.effective_user)
    lang = user.language
    status_text = get_string("status_on" if new_value else "status_off", lang)
    
    await query.answer(f"Auto-delete {status_text}" if lang == "en" else f"Автоудаление {status_text}", show_alert=True)
    await show_main_settings(query, user, lang)


async def format_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройка формата файлов"""
    query = update.callback_query
    user_id = update.effective_user.id
    db = context.bot_data.get('db')
    user = await db.get_or_create_user(user_id, update.effective_user)
    lang = user.language
    
    message = get_string("format_title", lang) + "\n\n" + \
              get_string("format_mp3_desc", lang) + "\n" + \
              get_string("format_flac_desc", lang)
    
    keyboard = get_format_keyboard(lang, current=user.format)
    await query.edit_message_text(
        message.strip(),
        parse_mode='HTML',
        reply_markup=keyboard
    )


async def set_format_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить формат файлов"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    file_format = query.data.replace('format_', '')
    db = context.bot_data.get('db')
    
    try:
        await db.update_user_setting(user_id, 'format', file_format)
        
        # Автоматически обновляем качество на совместимое
        user = await db.get_or_create_user(user_id, update.effective_user)
        if file_format == 'flac':
            if user.preferred_quality not in ['1411', '4600', '9200']:
                await db.update_user_setting(user_id, 'preferred_quality', '1411')
        else:
            if user.preferred_quality not in ['128', '192', '320']:
                await db.update_user_setting(user_id, 'preferred_quality', '320')
        
        user = await db.get_or_create_user(user_id, update.effective_user)
        lang = user.language
        
        await query.answer(get_string("format_success", lang, format=file_format.upper()), show_alert=True)
        await show_main_settings(query, user, lang)
        
    except Exception as e:
        print(f"❌ Ошибка установки формата: {e}")
        await query.answer("❌ Ошибка", show_alert=True)


async def toggle_notifications_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключить уведомления"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = context.bot_data.get('db')
    user = await db.get_or_create_user(user_id, update.effective_user)
    
    new_value = not user.notifications
    await db.update_user_setting(user_id, 'notifications', new_value)
    
    user = await db.get_or_create_user(user_id, update.effective_user)
    lang = user.language
    status_text = get_string("status_on" if new_value else "status_off", lang)
    
    await query.answer(get_string("notifications_success", lang, status=status_text), show_alert=True)
    await show_main_settings(query, user, lang)


async def settings_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в главное меню настроек"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = context.bot_data.get('db')
    user = await db.get_or_create_user(user_id, update.effective_user)
    
    await show_main_settings(query, user, user.language)


async def show_main_settings(query, user, lang):
    """Вспомогательная функция для показа главного меню настроек"""
    quality = user.preferred_quality
    if user.format == 'mp3':
        quality_display = f"{quality} kbps"
    else:
        quality_display = f"{quality} kbps (Hi-Res)" if int(quality) > 1411 else (f"{quality} kbps (CD)" if quality == '1411' else "Lossless")
    
    message = get_string(
        "settings_title", lang
    ) + "\n\n" + get_string(
        "settings_quality", lang, quality=quality_display
    ) + "\n" + get_string(
        "settings_lang", lang, lang=get_string(f"lang_name_{user.language}", lang)
    ) + "\n" + get_string(
        "settings_autodelete", lang, status=get_string("status_on" if user.auto_delete else "status_off", lang)
    ) + "\n" + get_string(
        "settings_format", lang, format=user.format.upper()
    ) + "\n" + get_string(
        "settings_notifications", lang, status=get_string("status_on" if user.notifications else "status_off", lang)
    ) + "\n\n" + get_string("settings_choose", lang)
    
    keyboard = get_settings_keyboard(lang)
    await query.edit_message_text(
        message.strip(),
        parse_mode='HTML',
        reply_markup=keyboard
    )


async def settings_close_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Закрыть меню настроек"""
    query = update.callback_query
    await query.answer()
    await query.delete_message()
