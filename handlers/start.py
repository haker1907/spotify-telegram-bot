"""
Обработчики команд /start и /help
"""
from telegram import Update
from telegram.ext import ContextTypes
from utils.keyboards import KeyboardBuilder
from utils.strings import get_string


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_obj = update.effective_user
    db = context.bot_data.get('db')
    
    # Получаем/создаем пользователя и его настройки
    lang = "ru"
    if db:
        user_db = await db.get_or_create_user(
            user_id=user_obj.id,
            username=user_obj.username,
            first_name=user_obj.first_name,
            last_name=user_obj.last_name
        )
        lang = user_db.language
    
    # Реферальный deeplink: /start ref_<telegram_user_id>
    if db and context.args:
        ref_arg = str(context.args[0]).strip()
        if ref_arg.startswith("ref_"):
            try:
                referrer_id = int(ref_arg.replace("ref_", ""))
                if referrer_id != user_obj.id and hasattr(db, "save_referral"):
                    await db.save_referral(user_obj.id, referrer_id)
            except ValueError:
                pass

    # Отправляем приветственное сообщение
    keyboard = KeyboardBuilder.main_menu(lang)
    welcome_text = get_string("welcome_message", lang)
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    user_id = update.effective_user.id
    db = context.bot_data.get('db')
    lang = "ru"
    if db:
        user = await db.get_or_create_user(user_id, update.effective_user)
        lang = user.language
        
    keyboard = KeyboardBuilder.back_button(lang)
    
    help_text = get_string("help_message", lang)
                    
    await update.message.reply_text(
        help_text,
        reply_markup=keyboard,
        parse_mode='HTML',
        disable_web_page_preview=True
    )

async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация ссылки для входа в веб-интерфейс"""
    user_id = update.effective_user.id
    db = context.bot_data.get('db')
    # Сначала гарантируем, что пользователь создан в БД (т.к. токен имеет Foreign Key на User.id)
    if db:
        await db.get_or_create_user(
            user_id=user_id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name
        )
        
    # Генерируем токен (теперь создается один раз на всё время)
    import secrets
    token = secrets.token_urlsafe(32)
    
    # Сохраняем или получаем существующий токен в БД
    if db:
        auth_token_obj = await db.create_auth_token(user_id, token)
        token = auth_token_obj.token
    
    # Ссылка на веб-интерфейс
    web_url = config.WEB_APP_URL
    auth_url = f"{web_url}/?auth={token}"
    
    text = f"🔗 <b>Ваша персональная ссылка</b>\n\n" \
           f"Это ваша постоянная ссылка для входа в веб-интерфейс:\n" \
           f"<code>{auth_url}</code>\n\n" \
           f"🌟 <b>Особенности:</b>\n" \
           f"• Одна ссылка на всю жизнь\n" \
           f"• Не нужно логиниться заново\n" \
           f"• Просто добавьте её в закладки\n\n" \
           f"<i>⚠️ Внимание: ни в коем случае не передавайте эту ссылку посторонним!</i>"
            
    await update.message.reply_text(text, parse_mode='HTML', disable_web_page_preview=True)
