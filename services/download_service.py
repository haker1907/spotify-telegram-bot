import os
import asyncio
import base64
from typing import Optional, Dict, List
from urllib.parse import quote_plus

import yt_dlp
import httpx
import copy
import glob
import time
import re

try:
    from config import JAMENDO_CLIENT_ID as _CFG_JAMENDO_CLIENT_ID
    from config import FMA_FALLBACK_URL_TEMPLATE as _CFG_FMA_FALLBACK_URL_TEMPLATE
    from config import DOWNLOAD_SOURCE_PRIORITY as _CFG_DOWNLOAD_SOURCE_PRIORITY
    from config import SOURCE_ENABLE_YOUTUBE as _CFG_SOURCE_ENABLE_YOUTUBE
    from config import SOURCE_ENABLE_JAMENDO as _CFG_SOURCE_ENABLE_JAMENDO
    from config import SOURCE_ENABLE_ARCHIVE as _CFG_SOURCE_ENABLE_ARCHIVE
    from config import SOURCE_ENABLE_FMA as _CFG_SOURCE_ENABLE_FMA
    from config import SOURCE_ENABLE_CCMIXTER as _CFG_SOURCE_ENABLE_CCMIXTER
except Exception:  # noqa: BLE001
    _CFG_JAMENDO_CLIENT_ID = ""
    _CFG_FMA_FALLBACK_URL_TEMPLATE = ""
    _CFG_DOWNLOAD_SOURCE_PRIORITY = "youtube,jamendo,archive,fma,ccmixter"
    _CFG_SOURCE_ENABLE_YOUTUBE = True
    _CFG_SOURCE_ENABLE_JAMENDO = True
    _CFG_SOURCE_ENABLE_ARCHIVE = True
    _CFG_SOURCE_ENABLE_FMA = True
    _CFG_SOURCE_ENABLE_CCMIXTER = True

class DownloadService:
    """Сервис для поиска и скачивания музыки с YouTube"""
    
    def __init__(self, download_dir: str = "downloads"):
        # Всегда используем абсолютный путь относительно корня проекта
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.download_dir = os.path.join(base_dir, download_dir)
        
        # Путь к файлу кук (всегда используем абсолютный путь)
        self.cookies_path = os.path.join(base_dir, "cookies.txt")
        # Источник browser cookies для yt-dlp (пример: firefox, firefox:default-release)
        self.cookies_browser = os.getenv('YTDLP_COOKIES_FROM_BROWSER', 'firefox').strip()
        self.cookies_browser_available = self._is_browser_cookies_available(self.cookies_browser)
        
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Инициализация YouTube API (если доступен)
        self.youtube_api = None
        try:
            from services.youtube_api_service import YouTubeAPIService
            self.youtube_api = YouTubeAPIService()
        except Exception as e:
            print(f"YouTube API not available: {e}")
        
        # Проверяем переменную окружения для Railway деплоя
        cookies_env = os.getenv('YOUTUBE_COOKIES_BASE64')
        if cookies_env:
            try:
                # Очищаем от пробелов/переносов и возможных обрамляющих кавычек.
                # В Railway переменную часто вставляют как строку в кавычках.
                cookies_env = cookies_env.strip().strip('"').strip("'")
                cookies_env = cookies_env.replace('\n', '').replace('\r', '')
                
                print("Attempting to restore cookies from YOUTUBE_COOKIES_BASE64...")
                try:
                    cookies_content = base64.b64decode(cookies_env, validate=True).decode('utf-8')
                except Exception:
                    # Fallback для urlsafe base64 и неполного padding
                    padded = cookies_env + ("=" * (-len(cookies_env) % 4))
                    cookies_content = base64.urlsafe_b64decode(padded).decode('utf-8')
                
                # Простая проверка формата (должен начинаться с # Netscape или содержать HTTP Cookie)
                is_netscape = cookies_content.startswith('# Netscape') or '# HTTP' in cookies_content[:100]
                
                if len(cookies_content) > 10:
                    print(f"Decoded size: {len(cookies_content)} bytes")
                    if not is_netscape:
                        print("WARNING: Cookies do NOT look like Netscape format! Download might fail.")
                    else:
                        print("Cookie format looks valid (Netscape)")
                
                with open(self.cookies_path, 'w', encoding='utf-8') as f:
                    f.write(cookies_content)
                print(f"YouTube cookies restored/updated to: {self.cookies_path}")
            except Exception as e:
                print(f"Failed to restore cookies from environment: {e}")
        
        if os.path.exists(self.cookies_path):
            print(f"YouTube cookie file found: {self.cookies_path}")
        else:
            if not self.youtube_api or not self.youtube_api.api_key:
                print(f"YouTube cookie file NOT found at: {self.cookies_path}")
                print("Set YOUTUBE_API_KEY or YOUTUBE_COOKIES_BASE64 environment variable")
            else:
                print("Using YouTube API instead of cookies")

        if self.cookies_browser and self.cookies_browser_available:
            print(f"Browser cookies enabled: {self.cookies_browser}")
        elif self.cookies_browser:
            print(f"Browser cookies disabled: profile not found for '{self.cookies_browser}'")
            print("   Using cookiefile/env cookies fallback.")

        jamendo_id = (_CFG_JAMENDO_CLIENT_ID or os.getenv("JAMENDO_CLIENT_ID", "")).strip()
        if jamendo_id:
            print("Legal fallback Jamendo: enabled (JAMENDO_CLIENT_ID is set)")
        else:
            print("Legal fallback Jamendo: disabled — set JAMENDO_CLIENT_ID in environment or .env")
        print(f"Source priority: {self._get_source_priority()}")

    def _is_source_enabled(self, source_name: str) -> bool:
        env_map = {
            "youtube": _CFG_SOURCE_ENABLE_YOUTUBE,
            "jamendo": _CFG_SOURCE_ENABLE_JAMENDO,
            "archive": _CFG_SOURCE_ENABLE_ARCHIVE,
            "fma": _CFG_SOURCE_ENABLE_FMA,
            "ccmixter": _CFG_SOURCE_ENABLE_CCMIXTER,
        }
        return bool(env_map.get(source_name, True))

    def _get_source_priority(self) -> List[str]:
        raw = (_CFG_DOWNLOAD_SOURCE_PRIORITY or "").strip().lower()
        if not raw:
            raw = "youtube,jamendo,archive,fma,ccmixter"
        order = [x.strip() for x in raw.split(",") if x.strip()]
        valid = {"youtube", "jamendo", "archive", "fma", "ccmixter"}
        order = [x for x in order if x in valid]
        if "youtube" not in order:
            order.insert(0, "youtube")
        for item in ["jamendo", "archive", "fma", "ccmixter"]:
            if item not in order:
                order.append(item)
        return order

    def _is_browser_cookies_available(self, browser_value: str) -> bool:
        """Проверка, есть ли профиль браузера в текущем окружении."""
        if not browser_value:
            return False

        browser_name = browser_value.split(':', 1)[0].strip().lower()
        home = os.path.expanduser('~')

        if browser_name == 'firefox':
            candidates = [
                os.path.join(home, '.config', 'mozilla', 'firefox'),
                os.path.join(home, '.mozilla', 'firefox'),
                os.path.join(home, '.var', 'app', 'org.mozilla.firefox', 'config', 'mozilla', 'firefox'),
                os.path.join(home, '.var', 'app', 'org.mozilla.firefox', '.mozilla', 'firefox'),
                os.path.join(home, 'snap', 'firefox', 'common', '.mozilla', 'firefox'),
            ]
            return any(os.path.isdir(path) for path in candidates)

        # Для остальных браузеров пробуем передать в yt-dlp "как есть"
        return True

    def _get_cookie_auth_options(self, prefer_browser: bool = True) -> dict:
        """
        Сформировать auth-опции для yt-dlp.
        Приоритет:
        1) cookies-from-browser (если включено)
        2) cookiefile
        """
        opts = {}

        if prefer_browser and self.cookies_browser and self.cookies_browser_available:
            # Поддержка формата "browser:profile"
            if ':' in self.cookies_browser:
                browser, profile = self.cookies_browser.split(':', 1)
                opts['cookiesfrombrowser'] = (browser.strip(), profile.strip())
            else:
                opts['cookiesfrombrowser'] = (self.cookies_browser,)

        if os.path.exists(self.cookies_path):
            opts['cookiefile'] = self.cookies_path

        return opts

    def _is_youtube_sign_in_error(self, err: str) -> bool:
        e = (err or "").lower()
        return (
            ("sign in" in e and "bot" in e)
            or "confirm you're not a bot" in e
            or "sign in to confirm" in e
        )

    def _cookie_hint_suffix(self) -> str:
        has_file = os.path.exists(self.cookies_path)
        has_env = bool(os.getenv("YOUTUBE_COOKIES_BASE64"))
        if not has_file and not has_env:
            prefix = " Сейчас нет cookies.txt и не задана YOUTUBE_COOKIES_BASE64. "
        else:
            prefix = " Cookies могли устареть — экспортируйте заново. "
        return (
            prefix
            + "На сервере (Railway) браузерных cookies нет — используйте Netscape cookies.txt "
            "в переменной YOUTUBE_COOKIES_BASE64 (base64). См. "
            "https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp"
        )

    def _polish_error(self, res: Optional[Dict]) -> Optional[Dict]:
        """Добавляет подсказку к типичной ошибке YouTube «not a bot»."""
        if not res or not isinstance(res, dict):
            return res
        err = res.get("error")
        if err is None:
            return res
        err_s = str(err)
        if "yt-dlp/wiki" in err_s and "YOUTUBE_COOKIES_BASE64" in err_s:
            return res
        if not self._is_youtube_sign_in_error(err_s):
            return res
        return {**res, "error": err_s + " | " + self._cookie_hint_suffix()}
        
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
            return self._polish_error({'error': str(e)})

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
            # Базовые заголовки браузера помогают уменьшить bot-check на стороне YouTube.
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
                ),
                'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
            },
            'socket_timeout': 60,
            'retries': 10,
            **self._get_cookie_auth_options(prefer_browser=True),
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
        youtube_enabled = self._is_source_enabled("youtube")
        result = {'error': 'YouTube source is disabled by config'} if not youtube_enabled else None
        
        # Для текстового поиска сразу используем стратегию кандидатных URL,
        # иначе ytsearch1 часто зацикливается на одном "битом" видео.
        if youtube_enabled and not youtube_url and isinstance(download_target, str) and not download_target.startswith("http"):
            candidate_result = await self._download_from_search_candidates(
                search_query=search_query,
                ydl_opts=ydl_opts,
                file_format=file_format,
                limit=10
            )
            if candidate_result and candidate_result.get('file_path'):
                return candidate_result
            result = candidate_result or {'error': 'Search candidates exhausted'}
        elif youtube_enabled:
            # Попытка 1: Стандартные клиенты yt-dlp (Без переопределения)
            # yt-dlp сам знает, какие клиенты работают лучше всего для избегания ошибок PO Token
            result = None
            player_client_attempts = [
                ['default'],
                ['web_music', 'mweb'],
                ['web_embedded'],
                ['web'],
                ['android'],
                ['ios'],
                ['tv_embedded'],
            ]
            for player_client in player_client_attempts:
                attempt_opts = copy.deepcopy(ydl_opts)
                attempt_opts['extractor_args']['youtube']['player_client'] = player_client
                result = await loop.run_in_executor(None, self._download_sync, download_target, attempt_opts, file_format)
                if not self._is_blocked(result):
                    break

            if self._is_blocked(result):
                # No cookies
                attempt_opts = copy.deepcopy(ydl_opts)
                attempt_opts['cookiefile'] = None
                attempt_opts.pop('cookiesfrombrowser', None)
                attempt_opts['extractor_args']['youtube']['player_client'] = ['default']
                result = await loop.run_in_executor(None, self._download_sync, download_target, attempt_opts, file_format)
    
        if youtube_enabled and self._should_try_search(result) and youtube_url:
            attempt_opts = copy.deepcopy(ydl_opts)
            attempt_opts['cookiefile'] = None
            attempt_opts.pop('cookiesfrombrowser', None)
            attempt_opts['default_search'] = 'ytsearch1'
            attempt_opts['extractor_args']['youtube']['player_client'] = ['default']
            result = await loop.run_in_executor(None, self._download_sync, search_query, attempt_opts, file_format)

        # Если первый поисковый результат тоже недоступен, пробуем несколько кандидатов.
        # Это важно для кейса "Video unavailable" на конкретном видео.
        if youtube_enabled and self._should_try_search(result):
            candidate_result = await self._download_from_search_candidates(
                search_query=search_query,
                ydl_opts=ydl_opts,
                file_format=file_format,
                limit=10
            )
            if candidate_result and candidate_result.get('file_path'):
                return candidate_result
    
        # Последний шаг: если YouTube полностью недоступен, пробуем легальные free-источники.
        if (not result or not result.get('file_path')):
            legal_result = await self._download_from_legal_sources(search_query, file_format=file_format)
            if legal_result and legal_result.get('file_path'):
                return legal_result

        return self._polish_error(result)

    async def _download_from_legal_sources(self, search_query: str, file_format: str = 'mp3') -> Optional[Dict]:
        """
        Фолбэк на легальные бесплатные источники:
        Jamendo -> Internet Archive -> Free Music Archive -> ccMixter.
        """
        # Для простоты и предсказуемости выдаем легальные фолбэки только в mp3.
        # Основной поток (yt-dlp) уже покрывает другие форматы.
        if file_format != 'mp3':
            return None

        providers = {
            "jamendo": self._download_from_jamendo,
            "archive": self._download_from_internet_archive,
            "fma": self._download_from_fma,
            "ccmixter": self._download_from_ccmixter,
        }
        query_variants = self._build_legal_query_variants(search_query)
        last_error = None
        last_provider = None

        for q in query_variants:
            for source_name in self._get_source_priority():
                if source_name == "youtube":
                    continue
                if not self._is_source_enabled(source_name):
                    continue
                provider = providers.get(source_name)
                if not provider:
                    continue
                last_provider = source_name
                try:
                    print(f"🔁 Legal fallback: trying {source_name} q='{q}'")
                    res = await provider(q)
                    if res and res.get('file_path'):
                        return res
                    if res and res.get('error'):
                        last_error = res.get('error')
                    else:
                        print(f"   {source_name}: no result")
                except Exception as e:
                    last_error = str(e)
                    print(f"⚠️ Legal fallback provider failed ({source_name}): {e}")
                    continue

        if last_error:
            return {'error': f'All legal fallback sources failed (last: {last_provider}): {last_error}'}
        return None

    def _build_query_tokens(self, search_query: str) -> List[str]:
        normalized = re.sub(r"[^\w\s-]", " ", search_query or "")
        normalized = re.sub(r"\s+", " ", normalized).strip().lower()
        tokens = [t for t in normalized.split(" ") if len(t) > 1]
        return tokens[:6]

    def _build_legal_query_variants(self, search_query: str, limit: int = 4) -> List[str]:
        """
        Подготавливаем несколько вариантов запроса, чтобы увеличить шанс найти трек
        на Jamendo/Archive/FMA/ccMixter.
        """
        raw = (search_query or "").strip()
        if not raw:
            return []

        cleaned = raw
        # убираем популярные суффиксы и скобки: "(official audio)", "[remix]" и т.п.
        cleaned = re.sub(r"\(.*?\)|\[.*?\]", " ", cleaned)
        cleaned = re.sub(r"(?i)\b(official\s+audio|official|audio|topic|remix|mix)\b", " ", cleaned)
        cleaned = re.sub(r"(?i)\b(feat\.?|ft\.?)\b.*$", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        variants = [raw]
        if cleaned and cleaned.lower() != raw.lower():
            variants.append(cleaned)

        # если есть разделитель "-", пробуем отдельно левую/правую части
        if "-" in raw:
            parts = [p.strip() for p in raw.split("-", 1)]
            if len(parts) == 2:
                if parts[0]:
                    variants.append(parts[0])
                if parts[1]:
                    variants.append(parts[1])

        # дедупликация, сохранение порядка
        variants = list(dict.fromkeys([v for v in variants if v and len(v) > 2]))
        return variants[:limit]

    async def _download_http_file(self, url: str, title_hint: str, source: str) -> Optional[Dict]:
        safe_name = "".join([c if c.isalnum() or c in " -_" else "_" for c in (title_hint or "track")]).strip()
        if not safe_name:
            safe_name = "track"
        out_path = os.path.join(self.download_dir, f"{safe_name}_{source}.mp3")

        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            response = await client.get(url)
            if response.status_code != 200 or not response.content:
                return None
            with open(out_path, "wb") as f:
                f.write(response.content)

        if not os.path.exists(out_path):
            return None
        return {
            'file_path': out_path,
            'title': title_hint or 'Unknown',
            'duration': 0,
            'artist': '',
            'thumbnail': '',
            'file_size': os.path.getsize(out_path),
            'source': source
        }

    async def _download_from_jamendo(self, search_query: str) -> Optional[Dict]:
        client_id = (_CFG_JAMENDO_CLIENT_ID or os.getenv("JAMENDO_CLIENT_ID", "")).strip()
        if not client_id:
            return {'error': 'JAMENDO_CLIENT_ID is not set'}

        q = search_query.strip()
        url = "https://api.jamendo.com/v3.0/tracks/"
        params = {
            "client_id": client_id,
            "format": "json",
            "limit": 1,
            "audioformat": "mp32",
            "search": q,
        }
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.get(url, params=params)
            if r.status_code != 200:
                return None
            data = r.json()
        results = (data or {}).get("results") or []
        if not results:
            return None
        item = results[0]
        audio_url = item.get("audio")
        if not audio_url:
            return None
        title = item.get("name") or q
        return await self._download_http_file(audio_url, title, "jamendo")

    async def _download_from_internet_archive(self, search_query: str) -> Optional[Dict]:
        tokens = self._build_query_tokens(search_query)
        if not tokens:
            return None
        q = " ".join(tokens)
        search_url = "https://archive.org/advancedsearch.php"
        params = {
            "q": f"(title:({q}) OR creator:({q})) AND mediatype:(audio)",
            "fl[]": ["identifier", "title"],
            "rows": 1,
            "page": 1,
            "output": "json",
        }
        async with httpx.AsyncClient(timeout=25.0) as client:
            sr = await client.get(search_url, params=params)
            if sr.status_code != 200:
                return None
            docs = ((sr.json() or {}).get("response") or {}).get("docs") or []
            if not docs:
                return None
            identifier = docs[0].get("identifier")
            title = docs[0].get("title") or q
            if not identifier:
                return None

            meta_url = f"https://archive.org/metadata/{identifier}"
            mr = await client.get(meta_url)
            if mr.status_code != 200:
                return None
            files = (mr.json() or {}).get("files") or []

        audio_file = None
        for f in files:
            name = (f.get("name") or "").lower()
            if name.endswith(".mp3"):
                audio_file = f.get("name")
                break
        if not audio_file:
            return None
        download_url = f"https://archive.org/download/{identifier}/{audio_file}"
        return await self._download_http_file(download_url, title, "archive")

    async def _download_from_fma(self, search_query: str) -> Optional[Dict]:
        """
        FMA публичного стабильного API без ключа сейчас не предоставляет.
        Оставляем расширяемую точку: можно задать готовый прямой URL через env.
        """
        base = (_CFG_FMA_FALLBACK_URL_TEMPLATE or os.getenv("FMA_FALLBACK_URL_TEMPLATE", "")).strip()
        if not base:
            return {'error': 'FMA_FALLBACK_URL_TEMPLATE is not set'}
        q = quote_plus((search_query or "").strip())
        url = base.replace("{query}", q)
        return await self._download_http_file(url, search_query, "fma")

    async def _download_from_ccmixter(self, search_query: str) -> Optional[Dict]:
        """
        Для ccMixter используем простой JSON endpoint, если доступен.
        """
        q = re.sub(r"\s+", "+", search_query.strip())
        api_url = f"https://ccmixter.org/api/query?f=json&limit=1&tags={q}"
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.get(api_url)
            if r.status_code != 200:
                return None
            try:
                data = r.json()
            except Exception:
                return None
        if not isinstance(data, list) or not data:
            return None
        item = data[0] or {}
        files = item.get("files") or []
        if not files:
            return None
        audio_url = None
        for f in files:
            dl = f.get("download_url") or f.get("file_page_url")
            if dl and str(dl).lower().endswith(".mp3"):
                audio_url = dl
                break
        if not audio_url:
            return None
        title = item.get("upload_name") or search_query
        return await self._download_http_file(audio_url, title, "ccmixter")

    def _is_blocked(self, res: Optional[Dict]) -> bool:
        """Определить, что ошибка связана с блокировкой/недоступностью источника."""
        if not res or not isinstance(res, dict) or 'error' not in res:
            return False
        e = str(res['error']).lower()
        blocked_markers = [
            "confirm you're not a bot", "sign in", "403", "page needs to be reloaded",
            "forbidden", "failed to extract any player response", "failed to extract player response",
            "innertube_context", "extractor error", "unsupported url",
            "video unavailable", "this content isn’t available", "this content isn't available",
            "this video is not available", "sign in to confirm"
        ]
        return any(marker in e for marker in blocked_markers)

    def _should_try_search(self, res: Optional[Dict]) -> bool:
        """Решить, нужен ли fallback на дополнительные поисковые кандидаты."""
        if not res:
            return True
        if not isinstance(res, dict):
            return True
        if res.get('file_path'):
            return False
        if self._is_blocked(res):
            return True

        error_text = str(res.get('error', '')).lower()
        retryable_markers = [
            "no formats returned",
            "yt-dlp returned empty info",
            "download finished but output file not found",
            "all format candidates failed",
            "requested format is not available",
            "only images are available",
            "sign in to confirm",
            "not a bot"
        ]
        return any(marker in error_text for marker in retryable_markers)

    async def _download_from_search_candidates(self, search_query: str, ydl_opts: dict, file_format: str, limit: int = 10) -> Optional[Dict]:
        """Ищет несколько YouTube кандидатов и пытается скачать их по очереди."""
        loop = asyncio.get_event_loop()
        candidate_urls = await loop.run_in_executor(None, self._get_search_candidate_urls_sync, search_query, limit)
        if not candidate_urls:
            return None

        print(f"🔁 Trying fallback candidates for query: {search_query} (count={len(candidate_urls)})")
        last_result = None

        for candidate_url in candidate_urls:
            # На каждом candidate URL пробуем несколько client-профилей.
            # Это увеличивает шанс получить доступный аудиопоток без PO token.
            for player_client in (['default'], ['web'], ['web_embedded'], ['android'], ['ios']):
                attempt_opts = copy.deepcopy(ydl_opts)
                attempt_opts['default_search'] = None
                attempt_opts['extractor_args']['youtube']['player_client'] = player_client
                result = await loop.run_in_executor(None, self._download_sync, candidate_url, attempt_opts, file_format)
                if result and result.get('file_path'):
                    return result
                last_result = result

                # Если с cookies не удалось, пробуем тот же client без cookies.
                # Это оставляет шанс на успех в локальной среде, но не ломает Railway-кейс.
                if self._is_blocked(result):
                    no_cookie_opts = copy.deepcopy(attempt_opts)
                    no_cookie_opts['cookiefile'] = None
                    no_cookie_opts.pop('cookiesfrombrowser', None)
                    no_cookie_res = await loop.run_in_executor(None, self._download_sync, candidate_url, no_cookie_opts, file_format)
                    if no_cookie_res and no_cookie_res.get('file_path'):
                        return no_cookie_res
                    last_result = no_cookie_res

        return last_result

    def _get_search_candidate_urls_sync(self, search_query: str, limit: int = 10) -> list:
        """Получить список candidate URL из YouTube поиска."""
        ydl_opts_base = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'skip_download': True,
            **self._get_cookie_auth_options(prefer_browser=True),
            'extractor_args': {
                'youtube': {
                    'skip': ['translated_subs'],
                }
            },
        }
        try:
            urls = []
            for query_variant in self._build_query_variants(search_query):
                if len(urls) >= limit:
                    break

                ydl_opts = copy.deepcopy(ydl_opts_base)
                # Берем сразу несколько результатов в каждом варианте, а не только ytsearch1
                ydl_opts['default_search'] = 'ytsearch5'
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(query_variant, download=False)
                if not info:
                    continue

                entries = info.get('entries') or []
                for entry in entries:
                    if not entry:
                        continue
                    video_id = entry.get('id')
                    webpage_url = entry.get('webpage_url')
                    if webpage_url:
                        urls.append(webpage_url)
                    elif video_id:
                        urls.append(f"https://www.youtube.com/watch?v={video_id}")
                    if len(urls) >= limit:
                        break

            # Удаляем дубликаты с сохранением порядка
            unique_urls = list(dict.fromkeys(urls))
            return unique_urls[:limit]
        except Exception as e:
            print(f"⚠️ Failed to collect fallback candidates: {e}")
            return []

    def _build_query_variants(self, search_query: str) -> list:
        """Построить варианты поискового запроса для обхода плохого первого результата."""
        base = (search_query or "").strip()
        if not base:
            return []

        normalized = re.sub(r"[^\w\s-]", " ", base)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        tokens = [t for t in re.split(r"[\s,;/|]+", normalized) if t]
        title_like = tokens[-1] if tokens else ""
        artist_like = " ".join(tokens[:-1]).strip() if len(tokens) > 1 else normalized

        variants = [
            base,
            f"{base} audio",
            f"{base} official audio",
            f"{base} topic",
        ]
        if normalized and normalized != base:
            variants.extend([
                normalized,
                f"{normalized} audio",
                f"{normalized} official audio",
            ])

        # Частый кейс: "Artist1, Artist2, ... TrackName"
        # Добавляем перестановки "track + artists", которые дают другие результаты YouTube.
        if title_like and artist_like:
            variants.extend([
                f"{title_like} {artist_like}",
                f"{title_like} by {artist_like}",
                f"{title_like} {artist_like} official audio",
                f"{title_like} {artist_like} topic",
            ])

        # Для длинных списков артистов пробуем укороченный вариант с первым артистом.
        if tokens:
            first_artist = tokens[0]
            if title_like:
                variants.extend([
                    f"{first_artist} {title_like}",
                    f"{title_like} {first_artist}",
                    f"{first_artist} {title_like} audio",
                ])

        return list(dict.fromkeys(variants))
        
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
            **self._get_cookie_auth_options(prefer_browser=True),
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
                    'file_size': os.path.getsize(file_path),
                    'source': 'youtube'
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
            **self._get_cookie_auth_options(prefer_browser=True),
        }
        
        try:
            # ИСПОЛЬЗУЕМ РОТАЦИЮ, ЧТОБЫ БЫЛ ФОЛЛБЕК БЕЗ КУК!
            return await self._download_with_rotation(
                download_target=search_query,
                search_query=search_query,
                ydl_opts=ydl_opts,
                file_format=file_format,
                youtube_url=None,
            )
        except Exception as e:
            print(f"❌ Ошибка скачивания {search_query}: {e}")
            return self._polish_error({'error': str(e)})
    
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
