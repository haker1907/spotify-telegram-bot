import os
import asyncio
from typing import Optional, Dict
import yt_dlp
import httpx
import copy
import glob
import time

class DownloadService:
    """Сервис для поиска и скачивания музыки с YouTube"""
    
    def __init__(self, download_dir: str = "downloads"):
        # Всегда используем абсолютный путь относительно корня проекта
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.download_dir = os.path.join(base_dir, download_dir)
        
        # Путь к файлу кук (всегда используем абсолютный путь)
        self.cookies_path = os.path.join(base_dir, "cookies.txt")
        
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Инициализация YouTube API (если доступен)
        self.youtube_api = None
        try:
            from services.youtube_api_service import YouTubeAPIService
            self.youtube_api = YouTubeAPIService()
        except Exception as e:
            print(f"ℹ️ YouTube API not available: {e}")
        
        # Проверяем переменную окружения для Railway деплоя
        import base64
        cookies_env = os.getenv('YOUTUBE_COOKIES_BASE64')
        if cookies_env:
            try:
                # Очищаем от пробелов и переносов (частая ошибка при копировании)
                cookies_env = cookies_env.strip().replace('\n', '').replace('\r', '')
                
                print(f"📦 Attempting to restore cookies from YOUTUBE_COOKIES_BASE64...")
                cookies_content = base64.b64decode(cookies_env).decode('utf-8')
                
                # Простая проверка формата (должен начинаться с # Netscape или содержать HTTP Cookie)
                is_netscape = cookies_content.startswith('# Netscape') or '# HTTP' in cookies_content[:100]
                
                if len(cookies_content) > 10:
                    print(f"📊 Decoded size: {len(cookies_content)} bytes")
                    if not is_netscape:
                        print(f"⚠️ WARNING: Cookies do NOT look like Netscape format! Download might fail.")
                    else:
                        print(f"✅ Cookie format looks valid (Netscape)")
                
                with open(self.cookies_path, 'w', encoding='utf-8') as f:
                    f.write(cookies_content)
                print(f"✅ YouTube cookies restored/updated to: {self.cookies_path}")
            except Exception as e:
                print(f"❌ Failed to restore cookies from environment: {e}")
        
        if os.path.exists(self.cookies_path):
            print(f"🍪 YouTube cookie file found: {self.cookies_path}")
        else:
            if not self.youtube_api or not self.youtube_api.api_key:
                print(f"⚠️ YouTube cookie file NOT found at: {self.cookies_path}")
                print(f"   Set YOUTUBE_API_KEY or YOUTUBE_COOKIES_BASE64 environment variable")
            else:
                print(f"✅ Using YouTube API instead of cookies")
        
    def _get_ffmpeg_args(self, quality: str, file_format: str) -> list:
        """Получить аргументы ffmpeg на основе качества и формата"""
        if file_format != 'flac':
            return []
            
        if quality == '1411':
            return ['-af', 'aresample=44100', '-sample_fmt', 's16']
        elif quality == '4600':
            return ['-af', 'aresample=96000', '-sample_fmt', 's32']
        elif quality == '9200':
            return ['-af', 'aresample=192000', '-sample_fmt', 's32']
        return []
    
    async def search_and_download(self, artist: str, track_name: str, quality: str = '192', file_format: str = 'mp3') -> Optional[Dict]:
        """
        Поиск и скачивание трека с YouTube
        """
        ffmpeg_args = self._get_ffmpeg_args(quality, file_format)
        search_query = f"{artist} - {track_name}"
        
        # Если доступен YouTube API, используем его для поиска
        youtube_url = None
        if self.youtube_api and self.youtube_api.api_key:
            print(f"🔍 Searching via YouTube API: {search_query}")
            video_info = self.youtube_api.search_video(search_query)
            if video_info:
                youtube_url = video_info['url']
                print(f"✅ Found via API: {video_info['title']}")
            else:
                print(f"⚠️ API search failed, falling back to yt-dlp search")
        
        # Используем URL от API если доступен, иначе поисковый запрос
        download_target = youtube_url if youtube_url else search_query
        
        # Генерируем опции для скачивания
        ydl_opts = self._get_base_ydl_opts(artist, track_name, quality, file_format, ffmpeg_args)
        if youtube_url:
            ydl_opts['default_search'] = None
        
        has_cookies = os.path.exists(self.cookies_path)
        print(f"🚀 Starting download (Cookies: {'YES' if has_cookies else 'NO'})")
        
        try:
            return await self._download_with_rotation(download_target, search_query, ydl_opts, file_format, youtube_url)
        except Exception as e:
            print(f"❌ Ошибка в search_and_download: {e}")
            return {'error': str(e)}

    def _get_base_ydl_opts(self, artist: str, track_name: str, quality: str, file_format: str, ffmpeg_args: list) -> dict:
        """
        Базовые настройки yt-dlp для всех видов скачивания
        """
        safe_name = "".join([c if c.isalnum() or c in " -_" else "_" for c in f"{artist} - {track_name}"])
        out_tmpl = os.path.join(self.download_dir, f"{safe_name}_{quality}.%(ext)s")
        
        return {
    'format': 'bestaudio/best',
    'outtmpl': out_tmpl,
    'overwrites': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': file_format,
        'preferredquality': quality if file_format == 'mp3' else None,
    }],
    'postprocessor_args': {'ffmpeg': ffmpeg_args} if ffmpeg_args else {},
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'default_search': 'ytsearch1',
    'extractor_args': {
        'youtube': {
            'skip': ['translated_subs'],
        }
    },
    'socket_timeout': 60,
    'retries': 10,
    'cookiefile': self.cookies_path if os.path.exists(self.cookies_path) else None,
}

    async def download_from_url(self, youtube_url: str, quality: str = '192', file_format: str = 'mp3', artist: str = "Unknown", track_name: str = "Track") -> Optional[Dict]:
        """
        Скачивание конкретного видео по URL с использованием ротации
        """
        ffmpeg_args = self._get_ffmpeg_args(quality, file_format)
        search_query = f"{artist} - {track_name}"
        
        ydl_opts = self._get_base_ydl_opts(artist, track_name, quality, file_format, ffmpeg_args)
        ydl_opts['default_search'] = None # Прямой URL, поиск не нужен
        
        return await self._download_with_rotation(youtube_url, search_query, ydl_opts, file_format, youtube_url)

    async def _download_with_rotation(self, download_target, search_query, ydl_opts, file_format, youtube_url=None):
        """
        Внутренняя логика ротации клиентов (4 попытки + поиск альтернатив)
        """
        loop = asyncio.get_event_loop()
        
        def is_blocked(res):
            if not res or not isinstance(res, dict) or 'error' not in res:
                return False
            e = res['error'].lower()
            return any(msg in e for msg in [
                "confirm you're not a bot", "sign in", "403", "page needs to be reloaded",
                "forbidden", "failed to extract any player response", "failed to extract player response",
                "innertube_context", "extractor error", "unsupported url",
                 "video unavailable", "this video is not available",
                "sign in to confirm", "confirm you're not a bot"
            ])

        # Попытка 1: Стандартные клиенты yt-dlp (Без переопределения)
        # yt-dlp сам знает, какие клиенты работают лучше всего для избегания ошибок PO Token
        attempt_opts = copy.deepcopy(ydl_opts)
        attempt_opts['extractor_args']['youtube']['player_client'] = ['default']
        result = await loop.run_in_executor(None, self._download_sync, download_target, attempt_opts, file_format)

        if self._is_blocked(result):
        # Attempt 2
            attempt_opts = copy.deepcopy(ydl_opts)
            attempt_opts['extractor_args']['youtube']['player_client'] = ['web_music', 'mweb']
            result = await loop.run_in_executor(None, self._download_sync, download_target, attempt_opts, file_format)

        if self._is_blocked(result):
            # Attempt 3
            attempt_opts = copy.deepcopy(ydl_opts)
            attempt_opts['extractor_args']['youtube']['player_client'] = ['web_embedded']
            result = await loop.run_in_executor(None, self._download_sync, download_target, attempt_opts, file_format)
    
        if self._is_blocked(result):
            # Attempt 4
            attempt_opts = copy.deepcopy(ydl_opts)
            attempt_opts['extractor_args']['youtube']['player_client'] = ['web']
            result = await loop.run_in_executor(None, self._download_sync, download_target, attempt_opts, file_format)
    
        if self._is_blocked(result):
            # No cookies
            attempt_opts = copy.deepcopy(ydl_opts)
            attempt_opts['cookiefile'] = None
            attempt_opts['extractor_args']['youtube']['player_client'] = ['default']
            result = await loop.run_in_executor(None, self._download_sync, download_target, attempt_opts, file_format)
    
        if self._should_try_search(result) and youtube_url:
            attempt_opts = copy.deepcopy(ydl_opts)
            attempt_opts['cookiefile'] = None
            attempt_opts['default_search'] = 'ytsearch1'
            attempt_opts['extractor_args']['youtube']['player_client'] = ['default']
            result = await loop.run_in_executor(None, self._download_sync, search_query, attempt_opts, file_format)
    
        return result   
        
    async def get_metadata_only(self, artist: str, track_name: str) -> Optional[Dict]:
        """
        Только поиск метаданных (без скачивания)
        """
        search_query = f"{artist} - {track_name}"
        
        # Приоритет: YouTube API (быстрее и надежнее)
        if self.youtube_api and self.youtube_api.api_key:
            try:
                video_info = self.youtube_api.search_video(search_query)
                if video_info:
                    return {
                        'thumbnail': video_info.get('thumbnail'),
                        'title': video_info.get('title'),
                        'duration': None  # API не возвращает duration в search
                    }
            except Exception as e:
                print(f"⚠️ YouTube API metadata search failed: {e}")
        
        # Fallback: yt-dlp (если API недоступен или не сработал)
        import yt_dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'default_search': 'ytsearch1',
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'android', 'web_music'],
                    'skip': ['translated_subs'],
                }
            },
            'referer': 'https://www.google.com/',
            'noproxy': True,
            'cookiefile': self.cookies_path if os.path.exists(self.cookies_path) else None,
        }
        
        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, self._extract_info_sync, search_query, ydl_opts)
            if info and 'entries' in info and info['entries']:
                entry = info['entries'][0]
                return {
                    'thumbnail': entry.get('thumbnail'),
                    'title': entry.get('title'),
                    'duration': entry.get('duration')
                }
            return None
        except Exception as e:
            print(f"❌ Metadata search error for {search_query}: {e}")
            return None

    def _extract_info_sync(self, query: str, opts: dict):
        import yt_dlp
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(query, download=False)


def _download_sync(self, query: str, ydl_opts: dict, file_format: str = 'mp3') -> Optional[Dict]:
    """Синхронное скачивание с предварительной проверкой доступных форматов"""
    format_candidates = [
        "bestaudio[ext=m4a]/bestaudio/best",
        "bestaudio/best",
        "best"
    ]

    last_error = None

    try:
        probe_opts = copy.deepcopy(ydl_opts)
        probe_opts['skip_download'] = True
        probe_opts['quiet'] = False
        probe_opts['no_warnings'] = False

        with yt_dlp.YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(query, download=False)

        if not info:
            return {'error': 'yt-dlp returned empty info'}

        # Если это поиск
        if 'entries' in info and info['entries']:
            info = info['entries'][0]

        formats = info.get('formats') or []
        if not formats:
            return {'error': 'No formats returned by extractor'}

    except yt_dlp.utils.DownloadError as e:
        return {'error': str(e).split('\n')[0]}
    except Exception as e:
        return {'error': f'Probe failed: {e}'}

    for fmt in format_candidates:
        try:
            current_opts = copy.deepcopy(ydl_opts)
            current_opts['format'] = fmt

            print(f"🎵 Trying format: {fmt}...")

            with yt_dlp.YoutubeDL(current_opts) as ydl:
                downloaded_info = ydl.extract_info(query, download=True)

            if not downloaded_info:
                continue

            if 'entries' in downloaded_info and downloaded_info['entries']:
                downloaded_info = downloaded_info['entries'][0]

            title = downloaded_info.get('title', 'Unknown')
            duration = downloaded_info.get('duration', 0)

            base_path = ydl.prepare_filename(downloaded_info)
            file_path = os.path.splitext(base_path)[0] + f'.{file_format}'

            if not os.path.exists(file_path):
                actual_filename = downloaded_info.get('_filename')
                if actual_filename:
                    potential_path = os.path.splitext(actual_filename)[0] + f'.{file_format}'
                    if os.path.exists(potential_path):
                        file_path = potential_path

            if not os.path.exists(file_path):
                pattern = os.path.join(self.download_dir, f'*.{file_format}')
                files = glob.glob(pattern)
                now = time.time()
                recent_files = [f for f in files if now - os.path.getctime(f) < 60]
                if recent_files:
                    file_path = max(recent_files, key=os.path.getctime)

            if not os.path.exists(file_path):
                return {'error': 'Download finished but output file not found'}

            return {
                'file_path': file_path,
                'title': title,
                'duration': duration,
                'artist': downloaded_info.get('artist', ''),
                'thumbnail': downloaded_info.get('thumbnail', ''),
                'file_size': os.path.getsize(file_path)
            }

        except yt_dlp.utils.DownloadError as e:
            last_error = str(e).split('\n')[0]
            print(f"⚠️ Format {fmt} failed: {last_error}")
            continue
        except Exception as e:
            last_error = f"Unexpected error: {e}"
            print(f"❌ Unexpected error in _download_sync: {e}")
            break

    return {'error': last_error or 'All format candidates failed'}
    
    async def search_and_download_by_query(self, search_query: str, quality: str = '192', file_format: str = 'mp3') -> Optional[Dict]:
        ffmpeg_args = self._get_ffmpeg_args(quality, file_format)
        
        # Модифицируем шаблон имени файла чтобы избежать коллизий качества
        safe_query = "".join([c if c.isalnum() or c in " -_" else "_" for c in search_query])
        out_tmpl = os.path.join(self.download_dir, f"{safe_query}_{quality}.%(ext)s")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': out_tmpl,
            'overwrites': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': file_format,
                'preferredquality': quality if file_format == 'mp3' else None,
            }],
            'postprocessor_args': {
                'ffmpeg': ffmpeg_args
            } if ffmpeg_args else {},
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'default_search': 'ytsearch1',
            # Обход блокировки YouTube "Sign in to confirm you're not a bot"
            # Удаляем жесткий user_agent для автоматического подбора под клиента
            'extractor_args': {
                'youtube': {
                    'skip': ['translated_subs'],
                }
            },
            'nocheckcertificate': True,
            'prefer_insecure': True,
            'socket_timeout': 30,
            'retries': 5,
            'geo_bypass': True,
            'age_limit': 99,  # Обход возрастных ограничений
            'cookiefile': self.cookies_path if os.path.exists(self.cookies_path) else None,
        }
        
        try:
            # ИСПОЛЬЗУЕМ РОТАЦИЮ, ЧТОБЫ БЫЛ ФОЛЛБЕК БЕЗ КУК!
            return await self._download_with_rotation(
                download_target=search_query, 
                search_query=search_query, 
                ydl_opts=ydl_opts, 
                file_format=file_format,
                youtube_url=None
            )
        except Exception as e:
            print(f"❌ Ошибка скачивания {search_query}: {e}")
            return {'error': str(e)}
    
    async def get_youtube_url(self, artist: str, track_name: str) -> Optional[str]:
        """
        Получить URL видео на YouTube без скачивания
        """
        search_query = f"{artist} - {track_name} audio"
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'default_search': 'ytsearch1',
        }
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._get_url_sync,
                search_query,
                ydl_opts
            )
            return result
        except Exception as e:
            print(f"❌ Ошибка получения URL: {e}")
            return None
    
    def _get_url_sync(self, query: str, ydl_opts: dict) -> Optional[str]:
        """Синхронное получение URL"""
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)
                if info and 'entries' in info:
                    # Берем первый результат поиска
                    first_result = info['entries'][0]
                    return f"https://www.youtube.com/watch?v={first_result['id']}"
                elif info:
                    return info.get('webpage_url')
        except Exception as e:
            print(f"❌ Ошибка в _get_url_sync: {e}")
            return None
    
    async def download_image(self, url: str) -> Optional[str]:
        """Скачать изображение во временный файл"""
        if not url:
            return None
            
        try:
            # Используем хеш URL для имени файла чтобы не скачивать одно и то же
            import hashlib
            file_hash = hashlib.md5(url.encode()).hexdigest()
            file_path = os.path.join(self.download_dir, f"thumb_{file_hash}.jpg")
            
            if os.path.exists(file_path):
                return file_path
                
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
                if response.status_code == 200:
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    return file_path
        except Exception as e:
            print(f"❌ Ошибка скачивания обложки: {e}")
            
        return None
    
    def cleanup_file(self, file_path: str):
        """Удалить скачанный файл"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️ Удален файл: {file_path}")
        except Exception as e:
            print(f"❌ Ошибка удаления файла {file_path}: {e}")
