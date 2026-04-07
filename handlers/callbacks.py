"""
Обработчики callback-запросов от inline-клавиатур
"""
import os
import html
from telegram import Update
from telegram.ext import ContextTypes
from utils.keyboards import KeyboardBuilder, get_track_actions_keyboard, get_playlist_tracks_browse_keyboard
from services.message_builder import MessageBuilder
from services.download_service import DownloadService
from utils.strings import get_string


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный обработчик всех callback-запросов"""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    # Получаем язык пользователя сразу
    user_id = query.from_user.id
    db = context.bot_data.get('db')
    lang = "ru"
    if db:
        user = await db.get_or_create_user(user_id, query.from_user)
        lang = user.language
    
    # Меню
    if callback_data == "back_to_menu":
        await show_main_menu(query, context, lang)
    elif callback_data == "menu_help":
        await show_help(query, context, lang)
    elif callback_data == "menu_playlists":
        await show_user_playlists(query, context, lang)
    elif callback_data == "menu_search":
        await show_search_help(query, context, lang)
    
    # Действия с треками
    elif callback_data.startswith("preview_"):
        await send_preview(query, context, callback_data, lang)
    elif callback_data.startswith("download_"):
        await download_track(query, context, callback_data, lang)
    elif callback_data.startswith("redownload_"):
        await redownload_track(query, context, callback_data, lang)
    elif callback_data.startswith("open_"):
        await open_in_spotify(query, context, callback_data, lang)
    elif callback_data.startswith("add_to_playlist_"):
        await show_playlist_selection(query, context, callback_data, lang)
    elif callback_data.startswith("batchdl_"):
        await batch_download_collection(query, context, callback_data, lang)
    
    elif callback_data.startswith("splp_"):
        await browse_spotify_playlist_page(query, context, callback_data, lang)
    elif callback_data.startswith("spl_"):
        await open_spotify_playlist_from_search(query, context, callback_data, lang)
    elif callback_data == "show_spotify_track_search":
        await show_spotify_track_search_fallback(query, context, lang)
    
    # Работа с плейлистами
    elif callback_data.startswith("select_playlist_"):
        await add_track_to_playlist(query, context, callback_data, lang)
    elif callback_data.startswith("view_playlist_"):
        await view_playlist(query, context, callback_data, lang)
    elif callback_data.startswith("delete_playlist_"):
        await confirm_delete_playlist(query, context, callback_data, lang)
    elif callback_data.startswith("confirm_delete_"):
        await delete_playlist(query, context, callback_data, lang)
    elif callback_data.startswith("remove_from_playlist_"):
        await remove_track_from_playlist(query, context, callback_data, lang)
    elif callback_data.startswith("track_in_playlist_"):
        await show_track_in_playlist(query, context, callback_data, lang)
    
    # Создание плейлиста (Теперь обрабатывается отдельным Handler в bot.py)
    elif callback_data == "create_playlist":
        pass
    
    # Отмена
    elif callback_data == "cancel":
        await query.message.edit_text(
            get_string("action_cancelled", lang),
            reply_markup=KeyboardBuilder.main_menu(lang)
        )
    
    # Заглушка
    elif callback_data == "noop":
        pass


async def show_main_menu(query, context, lang="ru"):
    """Показать главное меню"""
    keyboard = KeyboardBuilder.main_menu(lang)
    
    welcome_text = get_string("welcome_message", lang)
        
    await query.message.edit_text(
        welcome_text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )


async def show_help(query, context, lang="ru"):
    """Показать справку"""
    keyboard = KeyboardBuilder.back_button(lang)
    
    help_text = get_string("help_message", lang)
                    
    await query.message.edit_text(
        help_text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )


async def show_search_help(query, context, lang="ru"):
    """Показать помощь по поиску"""
    message = get_string("search_welcome", lang)
    keyboard = KeyboardBuilder.back_button(lang)
    await query.message.edit_text(
        message,
        reply_markup=keyboard,
        parse_mode='HTML'
    )


async def send_preview(query, context, callback_data, lang="ru"):
    """Отправить превью трека"""
    track_id = callback_data.replace("preview_", "")
    db = context.bot_data.get('db')
    
    # Получаем трек из БД
    track = await db.get_track(track_id)
    
    if not track or not track.preview_url:
        await query.message.reply_text(
            get_string("preview_unavailable", lang),
            parse_mode='HTML'
        )
        return
    
    # Отправляем аудио превью
    caption = get_string("preview_caption", lang, name=track.name, artist=track.artist)
    await query.message.reply_audio(
        audio=track.preview_url,
        title=track.name,
        performer=track.artist,
        duration=30,
        caption=caption,
        parse_mode='HTML'
    )


async def download_track(query, context, callback_data, lang="ru"):
    """Скачать трек"""
    track_id = callback_data.replace("download_", "")
    db = context.bot_data.get('db')
    download_service: DownloadService = context.bot_data.get('download_service')
    
    if not download_service:
        await query.message.reply_text("❌ Download service unavailable" if lang == "en" else "❌ Сервис скачивания недоступен")
        return
    
    # Получаем информацию о треке
    track = await db.get_track(track_id)
    
    if not track:
        # Если трека нет в базе (например, выбран из списка коллекции), 
        # пробуем получить его инфо через SpotifyService
        spotify_service = context.bot_data.get('spotify')
        if spotify_service:
            print(f"🔍 Track {track_id} not in DB, fetching from Spotify...")
            track_info = await spotify_service.get_track_info(track_id)
            if track_info:
                track = await db.get_or_create_track(track_info)
        
    if not track:
        await query.message.reply_text(get_string("track_not_found", lang))
        return
    
    # Отправляем сообщение о начале скачивания
    status_msg = await query.message.reply_text(
        get_string("downloading", lang, name=track.name, artist=track.artist),
        parse_mode='HTML'
    )
    
    try:
        # Получаем настройки пользователя (Функция 3, 18)
        user = await db.get_or_create_user(query.from_user.id, query.from_user)
        quality = user.preferred_quality
        file_format = user.format
        
        # Проверяем кэш (Функция 10 + Deduplication)
        cached_file_id = await db.get_cached_file_id(track_id, file_format=file_format, quality=quality)
        
        # НОВОЕ: Если в кэше конкретного качества нет, проверяем общее хранилище Telegram Storage
        # Это предотвращает дубликаты в канале (Функция deduplication)
        if not cached_file_id:
            # 1. Пробуем по ID
            telegram_file = await db.get_telegram_file(track_id)
            if telegram_file:
                cached_file_id = telegram_file.file_id
                print(f"✅ Found existing track by ID in Storage (callback): {track_id}")
            else:
                # 2. Пробуем по Имени/Артисту
                telegram_file_by_name = await db.get_telegram_file_by_name(track.artist, track.name)
                if telegram_file_by_name:
                    cached_file_id = telegram_file_by_name.file_id
                    print(f"✅ Found existing track by name in Storage (callback): {track.artist} - {track.name}")

        if cached_file_id:
            await status_msg.edit_text(get_string("from_cache", lang))
            try:
                # Формируем информативный caption для кэша
                quality_display = ""
                # Если мы нашли в общем хранилище, мы не знаем точное качество, пишем "High Quality"
                found_in_cache_specific = await db.get_cached_file_id(track_id, file_format=file_format, quality=quality)
                
                if found_in_cache_specific:
                    if file_format == 'mp3':
                        quality_display = f"{quality} kbps"
                    else:
                        if quality == '1411': quality_display = "1411 kbps (CD)"
                        elif quality == '2300': quality_display = "2300 kbps (48kHz/24bit)"
                        elif quality == '4600': quality_display = "4600 kbps (96kHz/24bit)"
                        elif quality == '9200': quality_display = "9200 kbps (192kHz/24bit)"
                        else: quality_display = "Lossless"
                else:
                    quality_display = "Original Quality"
                
                format_label = file_format.upper() if found_in_cache_specific else "AUDIO"
                caption = f"🎵 <b>{track.name}</b>\n👤 {track.artist}\n\n🎧 {format_label} • {quality_display}\n" + \
                          (f"✨ From library" if lang == "en" else f"✨ Из библиотеки")
                is_fav = await db.is_favorite(query.from_user.id, track_id) if db else False
                keyboard = get_track_actions_keyboard(track_id, is_favorite=is_fav, lang=lang)
                
                # Скачиваем обложку для thumbnail если есть
                thumb_path = None
                if hasattr(track, 'image_url') and track.image_url:
                    thumb_path = await download_service.download_image(track.image_url)
                
                thumb_file = None
                if thumb_path and os.path.exists(thumb_path):
                    thumb_file = open(thumb_path, 'rb')

                try:
                    await query.message.reply_audio(
                        audio=cached_file_id,
                        title=track.name,
                        performer=track.artist,
                        caption=caption,
                        thumbnail=thumb_file,
                        parse_mode='HTML',
                        reply_markup=keyboard,
                        read_timeout=600,
                        write_timeout=600
                    )
                finally:
                    if thumb_file:
                        thumb_file.close()

                await status_msg.delete()
                
                # Записываем в историю
                if db:
                    history_quality = f"{quality} kbps" if file_format == 'mp3' else f"Hi-Res FLAC ({quality} kbps)"
                    await db.add_download_to_history(query.from_user.id, track_id, history_quality, 0)
                    backup_service = context.bot_data.get('backup_service')
                    if backup_service:
                        context.application.create_task(backup_service.backup_to_telegram())
                return
            except Exception as e:
                print(f"❌ Ошибка отправки из кэша: {e}")
                # Если ошибка с кэшем, продолжаем обычное скачивание
        
        # Скачиваем трек
        result = await download_service.search_and_download(
            track.artist, 
            track.name, 
            quality=quality,
            file_format=file_format
        )
        
        if not result or not os.path.exists(result['file_path']):
            error_msg = get_string("error_download", lang)
            await status_msg.edit_text(
                f"{error_msg}\n\nSpotify: {track.spotify_url}",
                parse_mode='HTML'
            )
            return
        
        # Обновляем статус
        await status_msg.edit_text(
            get_string("uploading", lang) + f"\n\n<b>{track.artist} - {track.name}</b>",
            parse_mode='HTML'
        )
        
        # Проверяем размер файла (Лимит Telegram Bot API - 50 MB)
        file_size_mb = result.get('file_size', 0) / (1024 * 1024)
        if file_size_mb > 50:
            await status_msg.edit_text(
                get_string("error_file_too_large", lang, size=f"{file_size_mb:.1f}"),
                parse_mode='HTML'
            )
            download_service.cleanup_file(result['file_path'])
            return

        # Отправляем аудио файл
        try:
            with open(result['file_path'], 'rb') as audio_file:
                # Формируем caption с качеством и форматом
                if file_format == 'mp3':
                    quality_display = f"{quality} kbps"
                else:
                    if quality == '1411': quality_display = "1411 kbps (CD)"
                    elif quality == '2300': quality_display = "2300 kbps (48kHz/24bit)"
                    elif quality == '4600': quality_display = "4600 kbps (96kHz/24bit)"
                    elif quality == '9200': quality_display = "9200 kbps (192kHz/24bit)"
                    else: quality_display = "Lossless"
                format_label = file_format.upper()
                caption = f"🎵 <b>{track.name}</b>\n👤 {track.artist}\n\n🎧 {format_label} • {quality_display}"
                is_fav = await db.is_favorite(query.from_user.id, track_id) if db else False
                keyboard = get_track_actions_keyboard(track_id, is_favorite=is_fav, lang=lang)
                
                # Скачиваем обложку для thumbnail если есть
                thumb_path = None
                if hasattr(track, 'image_url') and track.image_url:
                    thumb_path = await download_service.download_image(track.image_url)
                
                thumb_file = None
                if thumb_path and os.path.exists(thumb_path):
                    thumb_file = open(thumb_path, 'rb')

                try:
                    sent_message = await query.message.reply_audio(
                        audio=audio_file,
                        title=track.name,
                        performer=track.artist,
                        caption=caption,
                        thumbnail=thumb_file,
                        parse_mode='HTML',
                        reply_markup=keyboard,
                        read_timeout=600,
                        write_timeout=600
                    )
                finally:
                    if thumb_file:
                        thumb_file.close()
                
                # Сохраняем в кэш
                if db and sent_message.audio:
                    await db.update_track_cache(
                        track_id, 
                        sent_message.audio.file_id,
                        file_format=file_format,
                        quality=quality
                    )
        except Exception as e:
            print(f"❌ Ошибка отправки аудио: {e}")
            await status_msg.edit_text(
                f"❌ Ошибка отправки: {str(e)}",
                parse_mode='HTML'
            )
            download_service.cleanup_file(result['file_path'])
            return
        
        # Удаляем статусное сообщение
        await status_msg.delete()
        
        # Записываем в историю (Функция 5)
        if db:
            file_size = result.get('file_size', 0)
            history_quality = f"{quality} kbps" if file_format == 'mp3' else "Lossless (FLAC)"
            await db.add_download_to_history(query.from_user.id, track.id, history_quality, file_size)
            backup_service = context.bot_data.get('backup_service')
            if backup_service:
                context.application.create_task(backup_service.backup_to_telegram())
            
        # Удаляем скачанный файл
        download_service.cleanup_file(result['file_path'])
    
    except Exception as e:
        print(f"❌ download_track error: {e}")
        await status_msg.edit_text(
            f"❌ Error during download: {str(e)}\n\nSpotify: {track.spotify_url}",
            parse_mode='HTML'
        )


async def redownload_track(query, context, callback_data, lang="ru"):
    """
    Обёртка для кнопки "Скачать снова".
    По сути повторяет сценарий callback "download_{track_id}".
    """
    # callback_data: redownload_{track_id}
    track_id = callback_data.replace("redownload_", "")
    await download_track(query, context, f"download_{track_id}", lang)


async def open_in_spotify(query, context, callback_data, lang="ru"):
    """Открыть в Spotify"""
    track_id = callback_data.replace("open_", "")
    db = context.bot_data.get('db')
    
    track = await db.get_track(track_id)
    
    if not track:
        await query.message.reply_text(get_string("track_not_found", lang))
        return
    
    title = "📱 <b>Открыть в Spotify:</b>" if lang == "ru" else "📱 <b>Open in Spotify:</b>"
    await query.message.reply_text(
        f"{title}\n\n"
        f"🎵 {track.name}\n"
        f"👤 {track.artist}\n\n"
        f"🔗 {track.spotify_url}",
        parse_mode='HTML',
        disable_web_page_preview=False
    )


async def show_playlist_selection(query, context, callback_data, lang="ru"):
    """Показать выбор плейлиста для добавления трека"""
    track_id = callback_data.replace("add_to_playlist_", "")
    user_id = query.from_user.id
    db = context.bot_data.get('db')
    
    # Получаем плейлисты пользователя
    playlists = await db.get_user_playlists(user_id)
    
    if not playlists:
        await query.message.reply_text(
            get_string("playlists_empty", lang),
            parse_mode='HTML'
        )
        return
    
    keyboard = KeyboardBuilder.playlist_selection(playlists, track_id, lang=lang)
    await query.message.reply_text(
        get_string("add_to_playlist_choose", lang),
        reply_markup=keyboard,
        parse_mode='HTML'
    )


async def add_track_to_playlist(query, context, callback_data, lang="ru"):
    """Добавить трек в плейлист"""
    # Парсим callback_data: select_playlist_{playlist_id}_{track_id}
    parts = callback_data.split('_')
    playlist_id = int(parts[2])
    track_id = parts[3]
    
    db = context.bot_data.get('db')
    user_id = query.from_user.id
    
    # Добавляем трек в плейлист
    success = await db.add_track_to_playlist(user_id, playlist_id, track_id)
    
    if success:
        playlist = await db.get_playlist(playlist_id)
        track = await db.get_track(track_id)
        
        await query.message.edit_text(
            get_string("add_to_playlist_success", lang, track=track.name, playlist=playlist.name),
            parse_mode='HTML',
            reply_markup=KeyboardBuilder.back_button(lang)
        )
        
        # Trigger immediate backup
        backup_service = context.bot_data.get('backup_service')
        if backup_service:
            context.application.create_task(backup_service.backup_to_telegram(force=True))
    else:
        await query.message.edit_text(
            get_string("add_to_playlist_exists", lang),
            parse_mode='HTML',
            reply_markup=KeyboardBuilder.back_button(lang)
        )


async def show_user_playlists(query, context, lang="ru"):
    """Показать плейлисты пользователя"""
    user_id = query.from_user.id
    db = context.bot_data.get('db')
    
    playlists = await db.get_user_playlists(user_id)
    
    if not playlists:
        keyboard = KeyboardBuilder.user_playlists([], lang=lang)
        await query.message.edit_text(
            get_string("playlists_empty", lang),
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        return
    
    message = get_string("playlists_my", lang) + "\n\n"
    
    for i, playlist in enumerate(playlists, 1):
        track_count = await db.get_playlist_track_count(user_id, playlist.id)
        count_text = get_string("playlist_tracks_count", lang, count=track_count)
        message += f"{i}. <b>{playlist.name}</b> {count_text}\n"
    
    keyboard = KeyboardBuilder.user_playlists(playlists, lang=lang)
    
    await query.message.edit_text(
        message,
        reply_markup=keyboard,
        parse_mode='HTML'
    )


async def view_playlist(query, context, callback_data, lang="ru"):
    """Просмотр плейлиста"""
    playlist_id = int(callback_data.replace("view_playlist_", ""))
    db = context.bot_data.get('db')
    user_id = query.from_user.id
    
    playlist = await db.get_playlist(playlist_id)
    tracks = await db.get_playlist_tracks(user_id, playlist_id)
    
    if not playlist:
        await query.message.edit_text(get_string("playlist_not_found", lang))
        return
    
    if not tracks:
        desc = playlist.description or ("No description" if lang == "en" else "Без описания")
        message = f"📋 <b>{playlist.name}</b>\n\n📝 {desc}\n" + \
                  get_string("playlist_tracks_count", lang, count=0) + "\n\n" + \
                  get_string("playlist_empty_info", lang)
        
        keyboard = KeyboardBuilder.back_button("menu_playlists", lang=lang)
        await query.message.edit_text(
            message,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        return
    
    message = MessageBuilder.build_user_playlist_message(playlist, len(tracks), lang=lang)
    keyboard = KeyboardBuilder.playlist_tracks(playlist_id, tracks, lang=lang)
    
    await query.message.edit_text(
        message,
        reply_markup=keyboard,
        parse_mode='HTML'
    )


async def show_track_in_playlist(query, context, callback_data, lang="ru"):
    """Воспроизвести трек при выборе в плейлисте"""
    # Парсим: track_in_playlist_{track_id}_{playlist_id}
    parts = callback_data.split('_')
    track_id = parts[3]
    playlist_id = int(parts[4])
    
    db = context.bot_data.get('db')
    track = await db.get_track(track_id)
    
    if not track:
        await query.message.reply_text(get_string("track_not_found", lang))
        return

    # Запускаем логику скачивания/отправки (аналогично download_track)
    # Это сразу "включит" музыку пользователю
    await download_track(query, context, f"download_{track_id}", lang)
    
    # Кнопки действий мы уже отправляем внутри download_track через MediaGroup логику
    # Но нам нужно, чтобы кнопка "Назад" вела обратно в плейлист, а не в поиск
    # Однако download_track отправляет стандартную клавиатуру.
    # Мы можем либо модифицировать download_track, либо отправить еще одну клавиатуру здесь.
    # Чтобы не усложнять, пока оставим стандартные действия.


async def remove_track_from_playlist(query, context, callback_data, lang="ru"):
    """Удалить трек из плейлиста"""
    # Парсим: remove_from_playlist_{track_id}_{playlist_id}
    parts = callback_data.split('_')
    track_id = parts[3]
    playlist_id = int(parts[4])
    
    db = context.bot_data.get('db')
    user_id = query.from_user.id
    
    success = await db.remove_track_from_playlist(user_id, playlist_id, track_id)
    
    if success:
        await query.message.edit_text(
            get_string("remove_from_playlist_success", lang),
            reply_markup=KeyboardBuilder.back_button(f"view_playlist_{playlist_id}", lang=lang),
            parse_mode='HTML'
        )
        
        # Trigger immediate backup
        backup_service = context.bot_data.get('backup_service')
        if backup_service:
            context.application.create_task(backup_service.backup_to_telegram(force=True))
    else:
        await query.message.edit_text(
            "❌ Error" if lang == "en" else "❌ Не удалось удалить трек",
            parse_mode='HTML'
        )


async def confirm_delete_playlist(query, context, callback_data, lang="ru"):
    """Подтверждение удаления плейлиста"""
    playlist_id_str = callback_data.replace("delete_playlist_", "")
    db = context.bot_data.get('db')
    
    playlist = await db.get_playlist(int(playlist_id_str))
    
    if not playlist:
        await query.message.edit_text(get_string("playlist_not_found", lang))
        return
    
    keyboard = KeyboardBuilder.confirm_action("delete", playlist_id_str, lang=lang)
    await query.message.edit_text(
        get_string("delete_playlist_confirm", lang, name=playlist.name),
        reply_markup=keyboard,
        parse_mode='HTML'
    )


async def delete_playlist(query, context, callback_data, lang="ru"):
    """Удалить плейлист"""
    playlist_id = int(callback_data.replace("confirm_delete_", ""))
    db = context.bot_data.get('db')
    
    success = await db.delete_playlist(playlist_id)
    
    if success:
        await query.message.edit_text(
            get_string("delete_playlist_success", lang),
            reply_markup=KeyboardBuilder.back_button("menu_playlists", lang=lang),
            parse_mode='HTML'
        )
        
        # Trigger immediate backup
        backup_service = context.bot_data.get('backup_service')
        if backup_service:
            context.application.create_task(backup_service.backup_to_telegram(force=True))
    else:
        await query.message.edit_text(
            "❌ Error" if lang == "en" else "❌ Не удалось удалить плейлист",
            parse_mode='HTML'
        )


def _fmt_dur_ms(ms) -> str:
    if not ms:
        return "—"
    s = max(0, int(ms)) // 1000
    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


async def render_playlist_browse_page(message, context, pl_id: str, page: int, lang: str):
    """Текст + клавиатура: все треки плейлиста (с пагинацией по страницам)."""
    cache = context.user_data.get("spotify_pl_browse")
    spotify_service = context.bot_data.get("spotify")
    if not cache or cache.get("id") != pl_id:
        if not spotify_service:
            await message.edit_text(
                "❌ Spotify недоступен" if lang == "ru" else "❌ Spotify unavailable"
            )
            return
        info = await spotify_service.get_playlist_info(
            f"https://open.spotify.com/playlist/{pl_id}"
        )
        if not info or not info.get("tracks"):
            await message.edit_text(
                "❌ Не удалось загрузить плейлист"
                if lang == "ru"
                else "❌ Could not load playlist"
            )
            return
        cache = {
            "id": pl_id,
            "tracks": info["tracks"],
            "name": info.get("name"),
            "owner": info.get("owner", ""),
        }
        context.user_data["spotify_pl_browse"] = cache

    tracks = cache["tracks"]
    per_page = 10
    total_pages = max(1, (len(tracks) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    chunk = tracks[start : start + per_page]

    total_ms = sum((t.get("duration_ms") or 0) for t in tracks if t.get("duration_ms"))
    dur_human = ""
    if total_ms:
        total_sec = total_ms // 1000
        h, r = divmod(total_sec, 3600)
        m, s = divmod(r, 60)
        if lang == "ru":
            dur_human = f" · {h} ч. {m} мин." if h else f" · {m} мин."
        else:
            dur_human = f" · {h}h {m}m" if h else f" · {m} min."

    title = html.escape(str(cache.get("name") or "Playlist"))
    owner = cache.get("owner") or ""
    owner_esc = html.escape(owner) if owner else ""

    lines = [f"📀 <b>{title}</b>"]
    if owner_esc:
        lines.append(f"👤 {owner_esc}")
    cnt_label = "треков" if lang == "ru" else "tracks"
    lines.append(f"🔢 {len(tracks)} {cnt_label}{dur_human}")
    lines.append("")
    page_lbl = "Страница" if lang == "ru" else "Page"
    lines.append(f"<b>{page_lbl} {page + 1}/{total_pages}</b>")

    for i, t in enumerate(chunk, start=start + 1):
        nm = html.escape(str(t.get("name") or "?"))
        ar = html.escape(str(t.get("artist") or ""))
        dur = _fmt_dur_ms(t.get("duration_ms"))
        album = t.get("album")
        line = f"{i}. <b>{nm}</b>\n   {ar} · {dur}"
        if album:
            line += f"\n   💿 <i>{html.escape(str(album))}</i>"
        lines.append(line)

    hint = (
        "\n\nНажмите кнопку ниже, чтобы скачать трек."
        if lang == "ru"
        else "\n\nTap a button below to download a track."
    )
    text = "\n".join(lines) + hint

    kb = get_playlist_tracks_browse_keyboard(
        tracks, "playlist", pl_id, page, per_page=per_page, lang=lang
    )
    await message.edit_text(text, reply_markup=kb, parse_mode="HTML")


async def open_spotify_playlist_from_search(query, context, callback_data, lang="ru"):
    """Открыть плейлист из результатов текстового поиска (колбэк spl_<id>)."""
    pl_id = callback_data[4:]
    if not pl_id:
        return
    spotify_service = context.bot_data.get("spotify")
    if not spotify_service:
        await query.message.reply_text(
            "❌ Spotify недоступен" if lang == "ru" else "❌ Spotify unavailable"
        )
        return

    await query.message.edit_text(get_string("searching", lang), parse_mode="HTML")
    try:
        info = await spotify_service.get_playlist_info(
            f"https://open.spotify.com/playlist/{pl_id}"
        )
        if not info or not info.get("tracks"):
            await query.message.edit_text(
                "❌ Не удалось открыть плейлист"
                if lang == "ru"
                else "❌ Could not open playlist"
            )
            return
        context.user_data["spotify_pl_browse"] = {
            "id": pl_id,
            "tracks": info["tracks"],
            "name": info.get("name"),
            "owner": info.get("owner", ""),
        }
        await render_playlist_browse_page(query.message, context, pl_id, 0, lang)
    except Exception as e:
        await query.message.edit_text(
            f"❌ {'Ошибка' if lang == 'ru' else 'Error'}: {e}"
        )


async def browse_spotify_playlist_page(query, context, callback_data, lang="ru"):
    """Пагинация треков плейлиста (колбэк splp_<id>_<page>)."""
    parts = callback_data.split("_", 2)
    if len(parts) < 3:
        return
    _, pl_id, page_s = parts
    try:
        page = int(page_s)
    except ValueError:
        return
    await render_playlist_browse_page(query.message, context, pl_id, page, lang)


async def show_spotify_track_search_fallback(query, context, lang="ru"):
    """Показать обычный поиск по трекам, если плейлистиров не хватило."""
    from handlers.search import build_track_search_keyboard_and_message

    q = context.user_data.get("last_text_search_query") or ""
    if not q:
        await query.message.edit_text(
            "❌ Нет сохранённого запроса. Введите поиск снова."
            if lang == "ru"
            else "❌ No saved query. Please search again."
        )
        return

    db = context.bot_data.get("db")
    spotify_service = context.bot_data.get("spotify")
    try:
        message, keyboard = await build_track_search_keyboard_and_message(
            q, db, spotify_service, lang
        )
        if not message:
            await query.message.edit_text(
                "❌ По этому запросу треки не найдены."
                if lang == "ru"
                else "❌ No tracks found for this query."
            )
            return
        await query.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        await query.message.edit_text(
            f"❌ {'Ошибка поиска' if lang == 'ru' else 'Search error'}: {e}"
        )


async def batch_download_collection(query, context, callback_data, lang="ru"):
    """Пакетное скачивание первых треков коллекции."""
    parts = callback_data.split("_", 2)
    if len(parts) < 3:
        return
    collection_type, collection_id = parts[1], parts[2]
    spotify_service = context.bot_data.get("spotify")
    if not spotify_service:
        await query.message.reply_text("❌ Spotify service unavailable")
        return

    try:
        if collection_type == "album":
            info = await spotify_service.get_album_info(f"https://open.spotify.com/album/{collection_id}")
        elif collection_type == "playlist":
            info = await spotify_service.get_playlist_info(f"https://open.spotify.com/playlist/{collection_id}")
        else:
            info = await spotify_service.get_artist_info(f"https://open.spotify.com/artist/{collection_id}")

        tracks = (info or {}).get("tracks", [])[:10]
        if not tracks:
            await query.message.reply_text("❌ Нет треков для скачивания" if lang == "ru" else "❌ No tracks to download")
            return

        await query.message.reply_text(
            f"⏳ {'Запускаю пакетное скачивание' if lang == 'ru' else 'Starting batch download'}: {len(tracks)}"
        )
        for t in tracks:
            track_id = t.get("id")
            if not track_id:
                continue
            await download_track(query, context, f"download_{track_id}", lang=lang)
    except Exception as e:
        await query.message.reply_text(f"❌ Batch error: {e}")



