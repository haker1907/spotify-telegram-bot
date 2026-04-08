"""
Обработчики поиска и обработки Spotify ссылок
АВТОМАТИЧЕСКОЕ скачивание при получении ссылки
"""
import os
import hashlib
import html
from telegram import Update
from telegram.ext import ContextTypes
from services.spotify_service import SpotifyService
from services.download_service import DownloadService
from services.message_builder import MessageBuilder
from utils.strings import get_string
from utils.keyboards import (
    get_search_results_keyboard,
    get_track_actions_keyboard,
    get_collection_keyboard,
    get_spotify_playlist_search_keyboard,
    get_single_spotify_playlist_keyboard,
)


async def build_track_search_keyboard_and_message(
    query: str,
    db,
    spotify_service: SpotifyService,
    lang: str,
):
    """Собрать текст и клавиатуру поиска по трекам (библиотека + Spotify). Возвращает (message, keyboard) или (None, None)."""
    discover_results = []
    if db:
        discover_results = await db.search_telegram_files(query, limit=5)

    spotify_results = []
    if spotify_service:
        spotify_results = await spotify_service.search_tracks(query, limit=5)

    seen_ids = set()
    final_results = []

    for track in discover_results:
        seen_ids.add(track["id"])
        track = {**track, "name": f"✨ {track['name']}"}
        final_results.append(track)

    for track in spotify_results:
        if track["id"] not in seen_ids:
            final_results.append(track)

    if not final_results:
        return None, None

    safe_q = html.escape(query)
    message = f"🔎 <b>Результаты поиска для:</b> <i>{safe_q}</i>\n\n"
    message += "Выберите трек для скачивания:" if lang == "ru" else "Select a track to download:"
    keyboard = get_search_results_keyboard(final_results)
    return message, keyboard


async def handle_spotify_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик Spotify ссылок
    АВТОМАТИЧЕСКИ парсит ссылку и скачивает трек
    """
    message_text = update.message.text
    spotify_service: SpotifyService = context.bot_data.get('spotify')
    download_service: DownloadService = context.bot_data.get('download_service')
    db = context.bot_data.get('db')
    
    # Получаем язык пользователя сразу (Функция 19)
    user_id = update.effective_user.id
    lang = "ru"
    if db:
        user = await db.get_or_create_user(user_id, update.effective_user)
        lang = user.language
    
    # Парсим URL
    parsed = spotify_service.parse_spotify_url(message_text)
    
    if not parsed:
        await update.message.reply_text(
            "❌ Link not recognized." if lang == "en" else "❌ Не удалось распознать ссылку Spotify.",
            parse_mode='HTML'
        )
        return
    
    # Специальный UX для ссылки на плейлист:
    # сначала показываем только сам найденный плейлист, а треки - после клика.
    if parsed['type'] == 'playlist':
        status_msg = await update.message.reply_text(get_string("searching", lang))
        try:
            info = await spotify_service.get_playlist_info(message_text)
            if not info:
                await status_msg.edit_text("❌ Не удалось получить информацию о плейлисте")
                return

            playlist_item = {
                "id": parsed["id"],
                "name": info.get("name") or "Playlist",
                "owner": info.get("owner", ""),
                "total_tracks": len(info.get("tracks", [])),
            }
            if db:
                await db.save_public_spotify_playlist(
                    spotify_id=parsed["id"],
                    name=playlist_item["name"],
                    owner=playlist_item["owner"],
                    spotify_url=f"https://open.spotify.com/playlist/{parsed['id']}",
                    total_tracks=playlist_item["total_tracks"],
                    added_by_user_id=user_id,
                )
            safe_name = html.escape(str(playlist_item["name"]))
            message = f"📀 <b>{safe_name}</b>\n"
            if playlist_item["owner"]:
                message += f"👤 {html.escape(str(playlist_item['owner']))}\n"
            message += f"🔢 {'Треков' if lang == 'ru' else 'Tracks'}: {playlist_item['total_tracks']}\n\n"
            message += (
                "Нажмите на плейлист, чтобы открыть страницу со всеми треками:"
                if lang == "ru"
                else "Tap the playlist to open page with all tracks:"
            )
            keyboard = get_single_spotify_playlist_keyboard(playlist_item, lang=lang)
            await status_msg.edit_text(message, reply_markup=keyboard, parse_mode='HTML')
            return
        except Exception as e:
            await status_msg.edit_text(f"❌ Ошибка при обработке плейлиста: {str(e)}")
            return

    # Обработка коллекций (album, artist)
    if parsed['type'] in ['album', 'artist']:
        status_msg = await update.message.reply_text(get_string("searching", lang))
        try:
            if parsed['type'] == 'album':
                info = await spotify_service.get_album_info(message_text)
            elif parsed['type'] == 'artist':
                info = await spotify_service.get_artist_info(message_text)
            else: # playlist
                info = await spotify_service.get_playlist_info(message_text)

            if not info or not info.get('tracks'):
                await status_msg.edit_text("❌ Не удалось получить информацию о коллекции")
                return

            # Формируем сообщение и клавиатуру со списком треков
            title_map = {
                'album': "Альбом" if lang == "ru" else "Album",
                'artist': "Топ-треки" if lang == "ru" else "Top Tracks",
                'playlist': "Плейлист" if lang == "ru" else "Playlist"
            }
            
            message = f"📦 <b>{title_map[parsed['type']]}: {info['name']}</b>\n"
            message += f"🔢 Треков: {len(info['tracks'])}\n\n"
            message += "Выберите трек для скачивания:" if lang == "ru" else "Select a track to download:"

            # Используем существующую клавиатуру поиска для первых 10 треков
            keyboard = get_collection_keyboard(info['tracks'][:10], parsed['type'], parsed['id'], lang=lang)
            
            await status_msg.edit_text(message, reply_markup=keyboard, parse_mode='HTML')
            return
        except Exception as e:
            await status_msg.edit_text(f"❌ Ошибка при обработке коллекции: {str(e)}")
            return

    if parsed['type'] != 'track':
        await update.message.reply_text(
            "⚠️ Only tracks, albums, artists and playlists are supported." if lang == "en" else "⚠️ Поддерживаются только треки, альбомы, артисты и плейлисты.",
            parse_mode='HTML'
        )
        return
    
    # Получаем настройки из модели пользователя (Функция 3, 18)
    user = await db.get_or_create_user(user_id, update.effective_user)
    quality = user.preferred_quality
    file_format = user.format
    lang = user.language
    
    # Шаг 1: Получаем информацию о треке
    status_msg = await update.message.reply_text(get_string("searching", lang))
    
    try:
        track_info = await spotify_service.get_track_info_from_url(message_text)
        
        if not track_info:
            await status_msg.edit_text("❌ Не удалось получить информацию о треке")
            return
        
        # Используем ID из track_info (Spotify ID), если он есть
        track_id = track_info.get('id')
        
        # Если ID нет (не Spotify ссылка), генерируем на основе артиста и названия
        if not track_id:
            import hashlib
            unique_string = f"{track_info['artist']}_{track_info['name']}".lower()
            track_id = hashlib.md5(unique_string.encode()).hexdigest()[:16]
            track_info['id'] = track_id
        
        # Сохраняем в БД
        if db:
            await db.get_or_create_track(track_info)
        
        # Проверяем кэш (Функция 10)
        cached_file_id = None
        if db:
            cached_file_id = await db.get_cached_file_id(track_id, file_format=file_format, quality=quality)
            
            # НОВОЕ: Если в кэше конкретного качества нет, проверяем общее хранилище Telegram Storage
            # Это предотвращает дубликаты в канале (Функция deduplication)
            if not cached_file_id:
                # 1. Пробуем по ID
                telegram_file = await db.get_telegram_file(track_id)
                if telegram_file:
                    cached_file_id = telegram_file.file_id
                    print(f"✅ Found existing track by ID in Storage: {track_id}")
                else:
                    # 2. Пробуем по Имени/Артисту (если ID не совпали)
                    telegram_file_by_name = await db.get_telegram_file_by_name(track_info['artist'], track_info['name'])
                    if telegram_file_by_name:
                        cached_file_id = telegram_file_by_name.file_id
                        print(f"✅ Found existing track by name in Storage: {track_info['artist']} - {track_info['name']}")

        if cached_file_id:
            # Файл уже есть в кэше, отправляем сразу
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
                caption = f"🎵 <b>{track_info['name']}</b>\n👤 {track_info['artist']}\n\n" + \
                          f"🎧 {format_label} • {quality_display}\n" + \
                          (f"✨ From library" if lang == "en" else f"✨ Из библиотеки")
                
                is_fav = await db.is_favorite(user_id, track_id) if db else False
                keyboard = get_track_actions_keyboard(track_id, is_favorite=is_fav, lang=lang)
                
                # Скачиваем обложку для thumbnail если есть
                thumb_path = None
                if track_info.get('image_url'):
                    thumb_path = await download_service.download_image(track_info['image_url'])
                
                thumb_file = None
                if thumb_path and os.path.exists(thumb_path):
                    thumb_file = open(thumb_path, 'rb')

                try:
                    await update.message.reply_audio(
                        audio=cached_file_id,
                        title=track_info['name'],
                        performer=track_info['artist'],
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
                
                # Отдельное сообщение с клавиатурой
                action_msg = "📝 <b>Действия с треком:</b>" if lang == "ru" else "📝 <b>Track actions:</b>"
                await update.message.reply_text(action_msg, reply_markup=keyboard, parse_mode='HTML')
                await update.message.reply_text(get_string("share_after_download", lang), reply_markup=keyboard, parse_mode='HTML')
                
                await status_msg.delete()
                # Записываем в историю
                if db:
                    history_quality = f"{quality} kbps" if file_format == 'mp3' else f"Hi-Res FLAC ({quality} kbps)"
                    await db.add_download_to_history(user_id, track_id, history_quality, 0)
                    backup_service = context.bot_data.get('backup_service')
                    if backup_service:
                        context.application.create_task(backup_service.backup_to_telegram())
                
                return
            except Exception as e:
                print(f"❌ Ошибка отправки из кэша: {e}")
                # Продолжаем обычное скачивание
        
        # Шаг 2: Показываем информацию
        message_key = "downloading"
        info_message = get_string(message_key, lang, name=track_info['name'], artist=track_info['artist'])
        
        await status_msg.edit_text(info_message.strip(), parse_mode='HTML')
        
        # Шаг 3: АВТОМАТИЧЕСКИ скачиваем
        if not download_service:
            await status_msg.edit_text(
                f"❌ Сервис скачивания недоступен\n\n"
                f"🎵 {track_info['name']}\n\n"
                f"🔗 <a href=\"{track_info['spotify_url']}\">Открыть в Spotify</a>",
                parse_mode='HTML'
            )
            return
        
        # Скачиваем трек используя только название
        # YouTube сам найдёт правильного исполнителя
        search_query = track_info['name']
        if track_info.get('artist'):
            search_query = f"{track_info['artist']} {track_info['name']}"
        
        # Скачиваем с выбранным качеством и форматом (Функция 3, 18)
        result = await download_service.search_and_download_by_query(
            search_query, 
            quality=quality, 
            file_format=file_format
        )

        
        if not result or not result.get('file_path'):
            await status_msg.edit_text(
                f"❌ Не удалось скачать трек из доступных источников\n\n"
                f"🎵 {track_info['name']}\n"
                f"👤 {track_info['artist']}\n\n"
                f"Попробуйте другой трек или откройте в Spotify:\n"
                f"{track_info['spotify_url']}",
                parse_mode='HTML'
            )
            return
        
        # Проверяем размер файла (Лимит Telegram Bot API - 50 MB)
        file_size_mb = result.get('file_size', 0) / (1024 * 1024)
        if file_size_mb > 50:
            await status_msg.edit_text(
                get_string("error_file_too_large", lang, size=f"{file_size_mb:.1f}"),
                parse_mode='HTML'
            )
            return

        # Шаг 4: Отправляем файл
        await status_msg.edit_text(
            get_string("uploading", lang) + f"\n\n🎵 <b>{track_info['name']}</b>",
            parse_mode='HTML'
        )
        
        # Проверяем существование файла
        if not os.path.exists(result['file_path']):
            await status_msg.edit_text(
                f"❌ Файл не найден после скачивания\n\n"
                f"🎵 {track_info['name']}\n\n"
                f"Попробуйте другой трек или откройте в Spotify:\n"
                f"{track_info['spotify_url']}",
                parse_mode='HTML'
            )
            return
        
        try:
            with open(result['file_path'], 'rb') as audio_file:
                # Формируем caption с качеством и форматом
                if file_format == 'mp3':
                    quality_display = f"{quality} kbps"
                else:
                    if quality == '1411': quality_display = "1411 kbps (CD)"
                    elif quality == '4600': quality_display = "4600 kbps (Hi-Res)"
                    elif quality == '9200': quality_display = "9200 kbps (Ultra Hi-Res)"
                    else: quality_display = "Lossless"
                format_label = file_format.upper()
                source = (result.get('source') or 'youtube').strip()
                caption = f"🎵 <b>{track_info['name']}</b>\n👤 {track_info['artist']}\n\n" + \
                          f"🎧 {format_label} • {quality_display}\n" + \
                          f"📡 Source: {source}"
                
                # Проверяем, в избранном ли трек
                is_fav = await db.is_favorite(user_id, track_id) if db else False
                is_fav = await db.is_favorite(user_id, track_id) if db else False
                keyboard = get_track_actions_keyboard(track_id, is_favorite=is_fav, lang=lang)
                
                # Скачиваем обложку для thumbnail если есть
                thumb_path = None
                if track_info.get('image_url'):
                    thumb_path = await download_service.download_image(track_info['image_url'])
                
                thumb_file = None
                if thumb_path and os.path.exists(thumb_path):
                    thumb_file = open(thumb_path, 'rb')

                try:
                    sent_message = await update.message.reply_audio(
                        audio=audio_file,
                        title=track_info['name'],
                        performer=track_info['artist'],
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
                
                # Сохраняем file_id в кэш (Функция 10)
                if db and sent_message.audio:
                    # 1. Традиционный кэш
                    await db.update_track_cache(
                        track_id, 
                        sent_message.audio.file_id,
                        file_format=file_format,
                        quality=quality
                    )
                    # 2. Новое общее хранилище Telegram для Discover
                    await db.save_telegram_file(
                        track_id=track_id,
                        file_id=sent_message.audio.file_id,
                        artist=track_info['artist'],
                        track_name=track_info['name'],
                        file_size=result.get('file_size', 0)
                    )
                
                # Записываем в историю (Функция 5)
                if db:
                    file_size = result.get('file_size', 0)
                    history_quality = f"{quality} kbps" if file_format == 'mp3' else f"Hi-Res FLAC ({quality} kbps)"
                    await db.add_download_to_history(user_id, track_id, history_quality, file_size)
                    backup_service = context.bot_data.get('backup_service')
                    if backup_service:
                        context.application.create_task(backup_service.backup_to_telegram())
            
            # Удаляем статусное сообщение
            await status_msg.delete()
            await update.message.reply_text(get_string("share_after_download", lang), reply_markup=keyboard, parse_mode='HTML')
            
            # Удаляем временный файл
            download_service.cleanup_file(result['file_path'])
            
        except Exception as e:
            await status_msg.edit_text(
                f"❌ Ошибка при отправке файла: {str(e)}\n\n"
                f"🎵 {track_info['name']}",
                parse_mode='HTML'
            )
            print(f"❌ Ошибка отправки файла: {e}")

    
    except Exception as e:
        await status_msg.edit_text(
            f"❌ Ошибка при обработке: {str(e)}\n\n"
            f"Попробуйте другую ссылку.",
            parse_mode='HTML'
        )
        print(f"❌ Ошибка в handle_spotify_link: {e}")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /search"""
    user_id = update.effective_user.id
    db = context.bot_data.get('db')
    lang = "ru"
    if db:
        user = await db.get_or_create_user(user_id, update.effective_user)
        lang = user.language
        
    await update.message.reply_text(
        get_string("search_welcome", lang),
        parse_mode='HTML'
    )


async def handle_text_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик текстового поиска (не ссылка)
    Ищет в Discover (БД) и в Spotify
    """
    query = update.message.text
    user_id = update.effective_user.id
    db = context.bot_data.get('db')
    spotify_service: SpotifyService = context.bot_data.get('spotify')
    
    lang = "ru"
    if db:
        user = await db.get_or_create_user(user_id, update.effective_user)
        lang = user.language
        
    status_msg = await update.message.reply_text(
        "🔍 Ищу в библиотеке и Spotify..." if lang == "ru" else "🔍 Searching in library and Spotify..."
    )
    
    try:
        playlist_results = []
        if spotify_service:
            playlist_results = await spotify_service.search_playlists(query, limit=8)

        # Сначала показываем плейлисты Spotify; отдельные треки — после входа в плейлист или по кнопке
        if playlist_results:
            context.user_data["last_text_search_query"] = query
            safe_q = html.escape(query)
            message = (
                f"🔎 <b>Результаты для:</b> <i>{safe_q}</i>\n\n"
                f"📋 <b>{'Плейлисты Spotify' if lang == 'ru' else 'Spotify playlists'}</b>\n"
            )
            message += (
                "Выберите плейлист — внутри будут все треки:"
                if lang == "ru"
                else "Choose a playlist — all tracks will be listed inside:"
            )
            keyboard = get_spotify_playlist_search_keyboard(playlist_results, lang=lang)
            await status_msg.edit_text(message, reply_markup=keyboard, parse_mode='HTML')
            return

        message, keyboard = await build_track_search_keyboard_and_message(
            query, db, spotify_service, lang
        )

        if not message:
            await status_msg.edit_text(
                "❌ Ничего не найдено по вашему запросу." if lang == "ru" else "❌ Nothing found for your query."
            )
            return

        await status_msg.edit_text(message, reply_markup=keyboard, parse_mode='HTML')
        
    except Exception as e:
        print(f"❌ Ошибка при текстовом поиске: {e}")
        await status_msg.edit_text(
            "❌ Произошла ошибка при поиске. Попробуйте другую формулировку." if lang == "ru" else "❌ Search error. Try different keywords."
        )
