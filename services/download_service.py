import os
import asyncio
import hashlib
import glob
import time
import base64
from typing import Optional, Dict
from pathlib import Path

import yt_dlp
import httpx

class DownloadService:
    """Сервис для поиска и скачивания музыки с YouTube с продвинутым обходом блокировок"""
    
    def __init__(self, download_dir: str = "downloads"):
        # Используем Path для кроссплатформенности и надежности путей
        self.base_dir = Path(__file__).resolve().parent.parent
        self.download_dir = self.base_dir / download_dir
        self.cookies_path = self.base_dir / "cookies.txt"
        
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Инициализация YouTube API
        self.youtube_api = None
        self._init_youtube_api()
        # Восстановление кук из окружения (для Docker/Railway)
        self._restore_cookies_from_env()

    def _init_youtube_api(self):
        try:
            from services.youtube_api_service import YouTubeAPIService
            self.youtube_api = YouTubeAPIService()
        except (ImportError, Exception) as e:
            print(f"ℹ️ YouTube API service not found or failed: {e}")

    def _restore_cookies_from_env(self):
        cookies_env = os.getenv('YOUTUBE_COOKIES_BASE64')
        if cookies_env:
            try:
                print(f"📦 Восстановление cookies из YOUTUBE_COOKIES_BASE64...")
                # Очистка строки
                cookies_env = cookies_env.strip().replace('\n', '').replace('\r', '')
                cookies_content = base64.b64decode(cookies_env).decode('utf-8')
                
                with open(self.cookies_path, 'w', encoding='utf-8') as f:
                    f.write(cookies_content)
                print(f"✅ Cookies успешно обновлены: {self.cookies_path}")
            except Exception as e:
                print(f"❌ Ошибка декодирования cookies: {e}")

    def _get_ffmpeg_args(self, quality: str, file_format: str) -> list:
        """Настройки ресемплирования для Hi-Res форматов"""
        if file_format != 'flac':
            return []
        
        configs = {
            '1411': ['-af', 'aresample=44100', '-sample_fmt', 's16'],
            '4600': ['-af', 'aresample=96000', '-sample_fmt', 's32'],
            '9200': ['-af', 'aresample=192000', '-sample_fmt', 's32']
        }
        return configs.get(quality, [])

    def _get_base_ydl_opts(self, artist: str, track_name: str, quality: str, file_format: str, ffmpeg_args: list) -> dict:
        # Очистка имени файла
        raw_name = f"{artist} - {track_name}_{quality}"
        safe_name = "".join([c if c.isalnum() or c in " -_" else "_" for c in raw_name])
        out_tmpl = str(self.download_dir / f"{safe_name}.%(ext)s")
        
        return {
            'format': 'bestaudio/best',
            'outtmpl': out_tmpl,
            'overwrites': True,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch1',
            'nocheckcertificate': True,
            'socket_timeout': 60,
            'retries': 10,
            'geo_bypass': True,
            'cookiefile': str(self.cookies_path) if self.cookies_path.exists() else None,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': file_format,
                'preferredquality': quality if file_format == 'mp3' else None,
            }],
            'postprocessor_args': {'ffmpeg': ffmpeg_args} if ffmpeg_args else {},
            'extractor_args': {
                'youtube': {
                    'skip': ['translated_subs'],
                    'player_client': ['ios', 'android', 'web_music']
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8',
            }
        }

    async def search_and_download(self, artist: str, track_name: str, quality: str = '192', file_format: str = 'mp3') -> Optional[Dict]:
        query = f"{artist} - {track_name}"
        ffmpeg_args = self._get_ffmpeg_args(quality, file_format)
        
        youtube_url = None
        if self.youtube_api:
            res = self.youtube_api.search_video(query)
            if res: youtube_url = res['url']

        ydl_opts = self._get_base_ydl_opts(artist, track_name, quality, file_format, ffmpeg_args)
        if youtube_url: ydl_opts['default_search'] = None
            
        return await self._download_with_rotation(youtube_url or query, query, ydl_opts, file_format, youtube_url)

    async def _download_with_rotation(self, target: str, query: str, ydl_opts: dict, file_format: str, url_provided: bool) -> Optional[Dict]:
        loop = asyncio.get_event_loop()
        
        def is_blocked(res):
            if not res or 'error' not in res: return False
            err = res['error'].lower()
            return any(msg in err for msg in ["confirm you're not a bot", "sign in", "403", "forbidden", "unavailable"])

        # Стратегии перебора клиентов
        strategies = [
            ['ios', 'android'],      # 1. Мобильные (самые надежные)
            ['web_music', 'mweb'],   # 2. Музыкальный веб
            ['web_embedded'],        # 3. Встраиваемый плеер
            ['default']              # 4. Стандартный
        ]

        result = None
        for clients in strategies:
            print(f"🚀 Попытка через клиенты: {clients}")
            ydl_opts['extractor_args']['youtube']['player_client'] = clients
            result = await loop.run_in_executor(None, self._download_sync, target, ydl_opts, file_format)
            
            if not is_blocked(result):
                return result

        # Если бан по кукам — пробуем без них
        if is_blocked(result) and ydl_opts.get('cookiefile'):
            print("🔄 Бан по cookies. Пробуем без них...")
            ydl_opts['cookiefile'] = None
            result = await loop.run_in_executor(None, self._download_sync, target, ydl_opts, file_format)

        # Если поиск по конкретному URL провалился — пробуем найти альтернативу
        if is_blocked(result) and url_provided:
            print("🔄 Видео недоступно. Ищем альтернативу...")
            ydl_opts['default_search'] = 'ytsearch1'
            result = await loop.run_in_executor(None, self._download_sync, query, ydl_opts, file_format)

        return result

    def _download_sync(self, query: str, ydl_opts: dict, file_format: str) -> Optional[Dict]:
        """Синхронное ядро скачивания"""
        # Список форматов для перебора, если m4a (аудио-онли) недоступен
        formats = ["bestaudio[ext=m4a]/bestaudio", "bestaudio", "best"]
        last_err = "Unknown error"

        for fmt in formats:
            try:
                current_opts = ydl_opts.copy()
                current_opts['format'] = fmt
                
                with yt_dlp.YoutubeDL(current_opts) as ydl:
                    info = ydl.extract_info(query, download=True)
                    if not info: continue
                    
                    # Логика поиска файла (yt-dlp + ffmpeg могут менять расширение)
                    base_filename = ydl.prepare_filename(info)
                    expected_path = os.path.splitext(base_filename)[0] + f".{file_format}"
                    
                    # Проверка существования
                    if not os.path.exists(expected_path):
                        # Ищем самый новый файл с этим расширением в папке
                        files = glob.glob(str(self.download_dir / f"*.{file_format}"))
                        if files:
                            expected_path = max(files, key=os.path.getctime)
                        else:
                            continue

                    return {
                        'file_path': expected_path,
                        'title': info.get('title', 'Unknown'),
                        'duration': info.get('duration', 0),
                        'artist': info.get('artist', ''),
                        'thumbnail': info.get('thumbnail', ''),
                        'file_size': os.path.getsize(expected_path)
                    }
            except Exception as e:
                last_err = str(e)
                if "format is not available" not in last_err.lower():
                    break
        
        return {'error': last_err}

    async def download_image(self, url: str) -> Optional[str]:
        if not url: return None
        try:
            file_hash = hashlib.md5(url.encode()).hexdigest()
            file_path = self.download_dir / f"thumb_{file_hash}.jpg"
            
            if file_path.exists(): return str(file_path)
                
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10.0)
                if resp.status_code == 200:
                    with open(file_path, 'wb') as f:
                        f.write(resp.content)
                    return str(file_path)
        except Exception: pass
        return None

    def cleanup_file(self, file_path: str):
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️ Удален: {file_path}")
        except Exception as e:
            print(f"❌ Ошибка удаления: {e}")