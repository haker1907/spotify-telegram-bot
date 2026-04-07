from flask import Flask, request, jsonify, send_file, render_template, g, has_request_context
from flask_cors import CORS
import asyncio
import threading
import os
import sys
import functools
import hashlib
from datetime import datetime, timedelta
import jwt
import time
from collections import defaultdict
import requests
import uuid
import logging
import mimetypes
from werkzeug.utils import secure_filename

# Добавляем корневую директорию в путь для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from services.spotify_service import SpotifyService
from services.download_service import DownloadService
from database.db_manager import DatabaseManager

app = Flask(__name__)
logger = logging.getLogger("web.app")
# Важно: часть логгеров (например, werkzeug) пишет записи вне request context.
# Чтобы не падать с KeyError: 'request_id', добавляем поле по умолчанию на уровне LogRecordFactory.
_old_factory = logging.getLogRecordFactory()
def _record_factory(*args, **kwargs):
    record = _old_factory(*args, **kwargs)
    if not hasattr(record, "request_id"):
        record.request_id = "-"
    return record
logging.setLogRecordFactory(_record_factory)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] [%(request_id)s] %(message)s")
# CORS: ограничиваем доверенные origin
allowed_origins_env = os.getenv("WEB_ALLOWED_ORIGINS", "").strip()
if allowed_origins_env:
    allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    allowed_origins = [config.WEB_APP_URL, "http://localhost:5000", "https://localhost:5000"]

CORS(
    app,
    origins=allowed_origins,
    methods=["GET", "POST", "OPTIONS"],
    supports_credentials=True,
)

# Инициализация сервисов
spotify_service = SpotifyService()
download_service = DownloadService()
db = DatabaseManager()

# Настройки сессионных токенов (JWT)
SESSION_SECRET = os.getenv("WEB_SESSION_SECRET") or os.getenv("TELEGRAM_BOT_TOKEN") or "dev-insecure-session-secret"
SESSION_TTL_SECONDS = int(os.getenv("WEB_SESSION_TTL", "2592000"))  # 30 дней по умолчанию


def get_telegram_avatar_url(user_id: int) -> str | None:
    """
    Получить URL аватарки пользователя из Telegram Bot API.
    Возвращает прямую ссылку на файл или None, если фото недоступно.
    """
    try:
        bot_token = getattr(config, "TELEGRAM_BOT_TOKEN", None)
        if not bot_token:
            return None

        base = f"https://api.telegram.org/bot{bot_token}"
        resp = requests.get(
            f"{base}/getUserProfilePhotos",
            params={"user_id": int(user_id), "limit": 1},
            timeout=6,
        )
        data = resp.json() if resp.ok else {}
        photos = (data or {}).get("result", {}).get("photos", [])
        if not photos:
            return None

        # Берём самое большое изображение из первого набора размеров
        sizes = photos[0] or []
        if not sizes:
            return None
        file_id = (sizes[-1] or {}).get("file_id")
        if not file_id:
            return None

        resp2 = requests.get(f"{base}/getFile", params={"file_id": file_id}, timeout=6)
        data2 = resp2.json() if resp2.ok else {}
        file_path = (data2 or {}).get("result", {}).get("file_path")
        if not file_path:
            return None

        return f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
    except Exception as e:
        print(f"⚠️ Avatar fetch failed for user {user_id}: {e}")
        return None


def create_session_token(user_id: int) -> str:
    """Создать JWT-сессию для веб-пользователя."""
    payload = {
        "sub": str(user_id),
        "iat": int(datetime.utcnow().timestamp()),
        "exp": int((datetime.utcnow() + timedelta(seconds=SESSION_TTL_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, SESSION_SECRET, algorithm="HS256")


def require_auth(fn):
    """Декоратор для защиты эндпоинтов: требует Bearer JWT и кладёт user_id в g.current_user_id."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        else:
            # Secure fallback: HttpOnly cookie session
            token = request.cookies.get("session_token")
            if not token:
                return jsonify({"error": "Unauthorized"}), 401
        try:
            data = jwt.decode(token, SESSION_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Session expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid session token"}), 401

        user_id = data.get("sub")
        if not user_id:
            return jsonify({"error": "Invalid session payload"}), 401

        try:
            g.current_user_id = int(user_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid user id in session"}), 401

        return fn(*args, **kwargs)

    return wrapper


def require_admin(fn):
    """Декоратор для защиты админ-эндпоинтов: требует JWT и флаг `users.is_admin`."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = getattr(g, "current_user_id", None)
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401

        is_admin = run_async(db.is_admin(user_id))

        if not is_admin:
            return jsonify({"error": "Forbidden"}), 403

        return fn(*args, **kwargs)

    return wrapper

# ========== Rate limiting (in-memory, per process) ==========
# В проде на multiple workers это не полностью глобально, но защищает от простого флуда.
_rate_store = defaultdict(list)  # key -> list[timestamps]

def _rate_limited(key: str, limit: int, per_seconds: int) -> tuple[bool, int]:
    """
    Возвращает (is_limited, retry_after_seconds).
    retry_after_seconds полезно для фронтенда.
    """
    now = time.time()
    window_start = now - per_seconds

    timestamps = _rate_store.get(key, [])
    timestamps = [t for t in timestamps if t >= window_start]

    if len(timestamps) >= limit:
        oldest = min(timestamps) if timestamps else now
        retry_after = int(per_seconds - (now - oldest)) + 1
        _rate_store[key] = timestamps  # обновим pruning
        return True, max(1, retry_after)

    timestamps.append(now)
    _rate_store[key] = timestamps
    return False, 0

def rate_limit(limit: int, per_seconds: int):
    """Декоратор rate limiting для защищённых эндпоинтов."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # Приоритет: user_id из require_auth, иначе IP.
            user_id = getattr(g, "current_user_id", None)
            forwarded_for = request.headers.get("X-Forwarded-For", "")
            ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.remote_addr
            key = f"{fn.__name__}:{user_id or ip or 'anon'}"

            limited, retry_after = _rate_limited(key, limit=limit, per_seconds=per_seconds)
            if limited:
                return jsonify({"error": "Too many requests", "retry_after": retry_after}), 429

            return fn(*args, **kwargs)
        return wrapper
    return decorator

# Defaults (можно переопределить env в Railway)
DOWNLOAD_LIMIT = int(os.getenv("DOWNLOAD_RATE_LIMIT", "10"))
DOWNLOAD_PERIOD = int(os.getenv("DOWNLOAD_RATE_PERIOD_SECONDS", "600"))  # 10 минут
PREPARE_STREAM_LIMIT = int(os.getenv("PREPARE_STREAM_RATE_LIMIT", "10"))
PREPARE_STREAM_PERIOD = int(os.getenv("PREPARE_STREAM_RATE_PERIOD_SECONDS", "600"))
SYNC_LIMIT = int(os.getenv("SYNC_RATE_LIMIT", "1"))
SYNC_PERIOD = int(os.getenv("SYNC_RATE_PERIOD_SECONDS", "3600"))  # 1 час
BACKUP_LIMIT = int(os.getenv("BACKUP_RATE_LIMIT", "1"))
BACKUP_PERIOD = int(os.getenv("BACKUP_RATE_PERIOD_SECONDS", "600"))  # 10 минут

# Telegram Storage Service будет инициализирован при первом использовании
telegram_storage = None
backup_service = None
_async_runtime_loop = None
_async_runtime_thread = None
playlist_cache_jobs = {}
playlist_cache_jobs_lock = threading.Lock()


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if has_request_context():
            record.request_id = getattr(g, "request_id", "-")
        else:
            record.request_id = "-"
        return True


logger.addFilter(RequestIdFilter())


def _ensure_async_runtime():
    global _async_runtime_loop, _async_runtime_thread
    if _async_runtime_loop and _async_runtime_loop.is_running():
        return _async_runtime_loop

    _async_runtime_loop = asyncio.new_event_loop()

    def _runner():
        asyncio.set_event_loop(_async_runtime_loop)
        _async_runtime_loop.run_forever()

    _async_runtime_thread = threading.Thread(target=_runner, daemon=True)
    _async_runtime_thread.start()
    return _async_runtime_loop


def run_async(coro):
    loop = _ensure_async_runtime()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


def _set_playlist_cache_job(job_id: str, **fields):
    with playlist_cache_jobs_lock:
        job = playlist_cache_jobs.get(job_id) or {}
        job.update(fields)
        playlist_cache_jobs[job_id] = job
        return job


def _get_playlist_cache_job(job_id: str):
    with playlist_cache_jobs_lock:
        return dict(playlist_cache_jobs.get(job_id) or {})

def get_telegram_storage():
    """Ленивая инициализация Telegram Storage Service"""
    global telegram_storage
    if telegram_storage is None:
        from services.telegram_storage_service import TelegramStorageService
        telegram_storage = TelegramStorageService()
    return telegram_storage

def get_backup_service():
    """Ленивая инициализация Database Backup Service"""
    global backup_service
    if backup_service is None:
        from services.db_backup_service import DatabaseBackupService
        backup_service = DatabaseBackupService(
            storage_service=get_telegram_storage(),
            db_path=db.get_database_file_path(),
            db_manager=db
        )
    return backup_service

# Флаг и замок инициализации БД
db_initialized = False
init_lock = threading.Lock()

def run_background_sync():
    """Фоновая задача для глубокой синхронизации (Deep Sync)"""
    try:
        import threading
        import time
        print(f"🛰️  [BACKGROUND-{threading.get_ident()}] Starting asynchronous Deep Sync task...")
        
        # Даем сети время стабилизироваться (критично для Railway)
        # 30 секунд - это время, когда и бот, и веб-сервер уже полностью запущены
        print(f"⏳ [BACKGROUND] Waiting 30s for network to be fully ready...", flush=True)
        time.sleep(30)
        
        # Создаем новый event loop для этого потока
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        from services.telegram_storage_sync import DeepSyncService
        sync_service = DeepSyncService(get_telegram_storage(), db, download_service, spotify_service)
        
        # Запускаем синхронизацию
        print(f"🛰️  [BACKGROUND] Triggering deep scan (Full History)...", flush=True)
        count = loop.run_until_complete(sync_service.run_deep_sync(range_size=100000))
        print(f"✅ [BACKGROUND-{threading.get_ident()}] Deep Sync completed! Found {count} tracks")
        
        loop.close()
    except Exception as e:
        print(f"❌ [BACKGROUND] Deep Sync failed: {e}")
        import traceback
        traceback.print_exc()

def ensure_db_initialized():
    """Фоновая инициализация БД: только проверка на Deep Sync, если библиотека пуста"""
    global db_initialized
    print(f"🕵️  [WEB] ensure_db_initialized called (initialized={db_initialized})", flush=True)
    with init_lock:
        if not db_initialized:
            try:
                print("🌐 [WEB] Worker initializing database connection...")
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # 1. Применяем настройки WAL mode/схемы для этого процесса
                loop.run_until_complete(db.init_db())
                
                # 2. Проверка на пустоту для Deep Sync (только если база пуста)
                is_empty = loop.run_until_complete(db.is_library_empty())
                if is_empty:
                    import threading
                    print("🚀 [WEB] Library is EMPTY. Triggering background Deep Sync...")
                    thread = threading.Thread(target=run_background_sync)
                    thread.daemon = True
                    thread.start()
                else:
                    print("✅ [WEB] Library is ready.")
                
                loop.close()
                db_initialized = True
            except Exception as e:
                print(f"❌ [WEB] Database connection init failed: {e}")
                db_initialized = True

@app.before_request
def before_request():
    """Инициализация БД перед первым запросом, пропуск для health-check"""
    g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:12]
    if request.path != '/health':
        logger.info("Incoming request %s %s", request.method, request.path)
    
    if request.path == '/health':
        return
    ensure_db_initialized()


@app.after_request
def after_request(response):
    if hasattr(g, "request_id"):
        response.headers["X-Request-ID"] = g.request_id
    return response

@app.route('/health')
def health_check():
    return jsonify({'status': 'ok'}), 200

@app.route('/')
def index():
    """Главная страница с поддержкой авторизации через параметр auth"""
    auth_token = request.args.get('auth')
    return render_template('index.html', auth_token=auth_token)


@app.route('/admin', methods=['GET'])
def admin_page():
    """Админ-панель (минимальная)."""
    return render_template('admin.html')


@app.route('/admin/api/users', methods=['GET'])
@require_auth
@require_admin
def admin_users():
    """Список пользователей (только чтение)."""
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        users = run_async(db.get_users_overview_for_admin(limit=limit, offset=offset))

        # JSON-сериализация datetime
        for u in users:
            if u.get('last_active') and hasattr(u['last_active'], 'isoformat'):
                u['last_active'] = u['last_active'].isoformat()

        return jsonify({'users': users})
    except Exception as e:
        print(f"❌ Admin users error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/api/tracks', methods=['GET'])
@require_auth
@require_admin
def admin_tracks():
    """Список треков для админа (только чтение)."""
    try:
        limit = int(request.args.get('limit', 50))
        limit = max(1, min(limit, 200))
        query = request.args.get('q', '').strip()
        sort_by = request.args.get('sort_by', 'downloads_desc')
        without_cover = request.args.get('without_cover', '0') in ('1', 'true', 'yes')
        min_downloads = int(request.args.get('min_downloads', 0))
        tracks = run_async(db.get_tracks_overview_for_admin_filtered(
            limit=limit, query=query, sort_by=sort_by, without_cover=without_cover, min_downloads=min_downloads
        ))

        return jsonify({'tracks': tracks})
    except Exception as e:
        print(f"❌ Admin tracks error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/api/tracks/enrich-images', methods=['POST'])
@require_auth
@require_admin
def admin_tracks_enrich_images():
    """
    Догрузка обложек для треков админки.
    Важно: вынесено в отдельный запрос, чтобы основной список грузился быстро.
    """
    try:
        data = request.json or {}
        items = data.get('tracks') or []
        if not isinstance(items, list):
            return jsonify({'error': 'tracks must be a list'}), 400

        # Safety caps
        items = items[:30]

        async def _enrich(items_: list[dict]) -> dict:
            sem = asyncio.Semaphore(5)
            out: dict[str, str] = {}

            async def one(t: dict):
                track_id = str(t.get('id') or '').strip()
                if not track_id:
                    return

                async with sem:
                    # Надёжнее всего: у нас уже есть Spotify track_id (tracks.id в БД).
                    # Берём обложку через oEmbed/embed по ID (без текстового поиска).
                    info = await spotify_service.get_track_info(track_id)
                    if info and info.get('image_url'):
                        out[track_id] = info['image_url']

            await asyncio.gather(*(one(t) for t in items_), return_exceptions=True)
            return out

        enrich_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(enrich_loop)
        images = enrich_loop.run_until_complete(_enrich(items))
        enrich_loop.close()

        return jsonify({'images': images})
    except Exception as e:
        print(f"❌ Admin enrich images error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/api/tracks/delete', methods=['POST'])
@require_auth
@require_admin
def admin_delete_track():
    """Админ: удалить трек (из БД)."""
    try:
        data = request.json or {}
        track_id = data.get('track_id')
        if not track_id:
            return jsonify({'error': 'track_id is required'}), 400

        admin_id = getattr(g, "current_user_id", None)
        success = run_async(db.delete_track_for_admin(track_id))

        if not success:
            return jsonify({'error': 'Track not found'}), 404

        # Write-through backup, чтобы изменения пережили redeploy
        try:
            backup_svc = get_backup_service()
            run_async(backup_svc.backup_to_telegram(force=True))
        except Exception as e:
            print(f"⚠️ Admin delete backup failed: {e}")
        if admin_id:
            run_async(db.log_admin_action(admin_id, "delete_track", "track", str(track_id), "Deleted from admin panel"))

        return jsonify({'success': True})
    except Exception as e:
        print(f"❌ Admin delete track error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/favicon.ico')
def favicon():
    # Чтобы не было 404 в консоли браузера: иконка не критична для работы приложения.
    return ('', 204)

@app.route('/api/sync/deep', methods=['POST'])
@require_auth
@rate_limit(SYNC_LIMIT, SYNC_PERIOD)
def sync_deep():
    """Запустить глубокую синхронизацию (сканирование истории канала)"""
    try:
        from services.telegram_storage_sync import DeepSyncService
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        storage = get_telegram_storage()
        sync_service = DeepSyncService(storage, db, download_service, spotify_service)
        
        # Получаем параметры из запроса
        data = request.json or {}
        range_size = data.get('range', 100000)
        
        count = loop.run_until_complete(sync_service.run_deep_sync(range_size=range_size))
        
        # Сразу делаем backup после синхронизации
        backup_svc = get_backup_service()
        loop.run_until_complete(backup_svc.backup_to_telegram())
        
        loop.close()
        return jsonify({'success': True, 'found_count': count})
        
    except Exception as e:
        print(f"❌ Deep Sync error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/search', methods=['POST'])
def search():
    """Поиск треков (БД + Spotify) или плейлиста по Spotify ссылке."""
    try:
        data = request.json
        query = data.get('query', '')
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Проверяем, является ли query Spotify URL
        if 'spotify.com' in query or 'open.spotify' in query:
            return search_by_url(query)
        
        # Обычный поиск по тексту
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 1. Сначала ищем во внутренней базе (Discover)
        discover_tracks = []
        try:
            discover_tracks = loop.run_until_complete(db.search_telegram_files(query, limit=10))
            print(f"🏠 [WEB] Found {len(discover_tracks)} tracks in Discover database")
        except Exception as db_e:
            print(f"⚠️ [WEB] Database search failed: {db_e}")

        # 2. Ищем в Spotify
        spotify_tracks_raw = []
        try:
            spotify_tracks_raw = loop.run_until_complete(spotify_service.search_track(query))
        except Exception as sp_e:
            print(f"⚠️ [WEB] Spotify search failed: {sp_e}")
        
        loop.close()
        
        # Объединяем результаты и убираем дубликаты
        seen_ids = set()
        final_tracks = []
        
        # Приоритет - Discover
        for track in discover_tracks:
            seen_ids.add(track['id'])
            final_tracks.append({
                'id': track['id'],
                'name': f"✨ {track['name']}",
                'artist': track['artist'],
                'album': track.get('album'),
                'duration': 0, # В Discover может не быть длительности
                'image': track.get('image'),
                'preview_url': None,
                'from_discover': True
            })
            
        # Добавляем из Spotify то, чего нет в Discover
        for track in spotify_tracks_raw:
            if track.get('id') not in seen_ids:
                final_tracks.append({
                    'id': track.get('id'),
                    'name': track.get('name'),
                    'artist': track.get('artist'),
                    'album': track.get('album'),
                    'duration': (track.get('duration_ms', 0) // 1000) if track.get('duration_ms') else 0,
                    'image': track.get('image_url'),
                    'preview_url': track.get('preview_url')
                })
        
        return jsonify({'tracks': final_tracks[:20]})
    
    except Exception as e:
        print(f"❌ Comprehensive search error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/sync-library', methods=['POST'])
@require_auth
@rate_limit(SYNC_LIMIT, SYNC_PERIOD)
def sync_library():
    """Синхронизировать библиотеку (перенести данные из старых таблиц в Discovery)"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Получаем все треки с легаси ID
        async def run_sync():
            async with db.async_session() as session:
                from database.models import Track, TrackCache, TelegramFile
                from sqlalchemy import select
                from datetime import datetime
                
                added_count = 0
                # 1. Сначала из Track.telegram_file_id
                result = await session.execute(select(Track).where(Track.telegram_file_id != None))
                for track in result.scalars().all():
                    exists = await session.get(TelegramFile, track.id)
                    if not exists:
                        session.add(TelegramFile(
                            track_id=track.id,
                            file_id=track.telegram_file_id,
                            artist=track.artist,
                            track_name=track.name,
                            uploaded_at=track.cached_at or track.created_at or datetime.utcnow()
                        ))
                        added_count += 1
                
                # 2. Потом из TrackCache
                result = await session.execute(select(TrackCache))
                for entry in result.scalars().all():
                    exists = await session.get(TelegramFile, entry.track_id)
                    if not exists:
                        track = await session.get(Track, entry.track_id)
                        if track:
                            session.add(TelegramFile(
                                track_id=entry.track_id,
                                file_id=entry.telegram_file_id,
                                artist=track.artist,
                                track_name=track.name,
                                uploaded_at=entry.created_at or datetime.utcnow()
                            ))
                            added_count += 1
                
                await session.commit()
                return added_count
        
        count = loop.run_until_complete(run_sync())
        
        # Сразу делаем backup после синхронизации
        backup_svc = get_backup_service()
        loop.run_until_complete(backup_svc.backup_to_telegram())
        
        loop.close()
        return jsonify({'success': True, 'added_count': count})
        
    except Exception as e:
        print(f"❌ Sync error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/library', methods=['GET'])
def get_library():
    """Получить все треки из библиотеки (кэша)"""
    try:
        limit = int(request.args.get('limit', 1000))
        limit = max(1, min(limit, 2000))
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tracks_dict = loop.run_until_complete(db.get_library_tracks(limit=limit))
        loop.close()
        
        print(f"🌐 [API] /api/library returning {len(tracks_dict)} tracks", flush=True)
        return jsonify({'tracks': tracks_dict})
        
    except Exception as e:
        print(f"❌ Error in get_library: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/public-playlists', methods=['GET'])
def get_public_playlists():
    """Глобальные Spotify-плейлисты (для всех пользователей, web)."""
    try:
        limit = int(request.args.get('limit', 30))
        limit = max(1, min(limit, 100))
        cached_only = str(request.args.get('cached_only', '0')).lower() in ('1', 'true', 'yes')
        if cached_only:
            items = run_async(db.get_public_cached_spotify_playlists(limit=limit))
        else:
            items = run_async(db.get_public_spotify_playlists(limit=limit))
        playlists = []
        for p in items:
            playlists.append({
                'spotify_id': getattr(p, 'spotify_id', None),
                'name': getattr(p, 'name', ''),
                'owner': getattr(p, 'owner', ''),
                'spotify_url': getattr(p, 'spotify_url', ''),
                'total_tracks': getattr(p, 'total_tracks', None),
                'is_cached_public': bool(getattr(p, 'is_cached_public', 0)),
                'cached_tracks_count': getattr(p, 'cached_tracks_count', None),
            })
        return jsonify({'playlists': playlists})
    except Exception as e:
        print(f"❌ Error in get_public_playlists: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/spotify-playlists/<string:spotify_id>/tracks', methods=['GET'])
def get_spotify_playlist_tracks(spotify_id: str):
    """Получить все треки Spotify-плейлиста по ID (для веб-страницы плейлиста)."""
    try:
        url = f"https://open.spotify.com/playlist/{spotify_id}"
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        info = loop.run_until_complete(spotify_service.get_playlist_info(url))
        loop.close()

        if not info or not info.get('tracks'):
            return jsonify({'error': 'Playlist not found or empty', 'tracks': []}), 404

        # Обновляем/сохраняем в глобальный список
        try:
            run_async(db.save_public_spotify_playlist(
                spotify_id=spotify_id,
                name=info.get('name') or 'Playlist',
                owner=info.get('owner', ''),
                spotify_url=url,
                total_tracks=len(info.get('tracks') or []),
                added_by_user_id=getattr(g, 'current_user_id', None)
            ))
        except Exception as save_e:
            print(f"⚠️ Failed to refresh public playlist meta: {save_e}")

        tracks_out = []
        for t in info['tracks']:
            tracks_out.append({
                'id': t.get('id'),
                'name': t.get('name'),
                'artist': t.get('artist'),
                'album': t.get('album'),
                'duration': (t.get('duration_ms') or 0) // 1000 if t.get('duration_ms') else t.get('duration', 0),
                'image': t.get('image'),
                'preview_url': None,
            })

        return jsonify({
            'tracks': tracks_out,
            'name': info.get('name'),
            'owner': info.get('owner', ''),
            'total_tracks': len(tracks_out),
        })
    except Exception as e:
        print(f"❌ Error in get_spotify_playlist_tracks: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'tracks': []}), 500


@app.route('/api/upload-track', methods=['POST'])
@require_auth
def upload_track():
    """Загрузка локального аудиофайла пользователя в библиотеку web."""
    try:
        user_id = getattr(g, 'current_user_id', None)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        if 'file' not in request.files:
            return jsonify({'error': 'Audio file is required'}), 400

        uploaded = request.files['file']
        if not uploaded or not uploaded.filename:
            return jsonify({'error': 'Audio file is required'}), 400

        filename = secure_filename(uploaded.filename)
        if not filename:
            return jsonify({'error': 'Invalid filename'}), 400

        allowed_ext = {'.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg', '.opus'}
        _, ext = os.path.splitext(filename.lower())
        if ext not in allowed_ext:
            return jsonify({'error': f'Unsupported format: {ext or "unknown"}'}), 400

        # Размер файла ограничиваем 60MB для стабильности на web.
        uploaded.stream.seek(0, os.SEEK_END)
        file_size = uploaded.stream.tell()
        uploaded.stream.seek(0)
        if file_size > 60 * 1024 * 1024:
            return jsonify({'error': 'File is too large (max 60MB)'}), 400

        # Сохраняем в uploads/ с поддиректорией пользователя
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        user_upload_dir = os.path.join(base_dir, 'uploads', str(user_id))
        os.makedirs(user_upload_dir, exist_ok=True)

        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(user_upload_dir, unique_name)
        uploaded.save(file_path)

        # Метаданные: из формы или из имени файла "Artist - Track"
        artist = (request.form.get('artist') or '').strip()
        track_name = (request.form.get('name') or '').strip()
        if not track_name:
            stem = os.path.splitext(filename)[0]
            if ' - ' in stem:
                parts = stem.split(' - ', 1)
                if not artist:
                    artist = parts[0].strip()
                track_name = parts[1].strip()
            else:
                track_name = stem.strip()
        if not artist:
            artist = 'Local Upload'

        raw_id = f"{user_id}:{artist}:{track_name}:{file_size}:{os.path.basename(file_path)}"
        track_id = f"upload_{hashlib.md5(raw_id.encode()).hexdigest()[:16]}"
        preview_url = f"/api/stream-local/{track_id}"

        cover_image_url = None
        cover_file = request.files.get('cover') or request.files.get('image')
        if cover_file and cover_file.filename:
            cname = secure_filename(cover_file.filename)
            _, cext = os.path.splitext((cname or '').lower())
            allowed_img = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
            if cext not in allowed_img:
                return jsonify({'error': f'Unsupported cover format: {cext or "unknown"}'}), 400
            cover_file.stream.seek(0, os.SEEK_END)
            csize = cover_file.stream.tell()
            cover_file.stream.seek(0)
            if csize > 8 * 1024 * 1024:
                return jsonify({'error': 'Cover image is too large (max 8MB)'}), 400
            covers_dir = os.path.join(base_dir, 'uploads', 'covers')
            os.makedirs(covers_dir, exist_ok=True)
            cover_path = os.path.join(covers_dir, f"{track_id}{cext}")
            # перезаписываем, если повторная загрузка того же трека
            cover_file.save(cover_path)
            cover_image_url = f"/api/local-cover/{track_id}"

        track_data = {
            'id': track_id,
            'name': track_name,
            'artist': artist,
            'album': None,
            'duration_ms': None,
            'preview_url': preview_url,
            'spotify_url': f"local://upload/{track_id}",
            'image_url': cover_image_url,
            'popularity': None
        }

        # Сохраняем трек и файл в БД
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(db.get_or_create_track(track_data))
        # file_id делаем локальным псевдо-ID для совместимости
        loop.run_until_complete(db.save_telegram_file(
            track_id=track_id,
            file_id=f"local:{track_id}",
            file_path=file_path,
            file_size=file_size,
            artist=artist,
            track_name=track_name,
            image_url=cover_image_url
        ))
        loop.close()

        return jsonify({
            'success': True,
            'track': {
                'id': track_id,
                'name': track_name,
                'artist': artist,
                'image': cover_image_url,
                'preview_url': preview_url,
                'from_discover': True,
                'uploaded_at': datetime.utcnow().isoformat()
            }
        })
    except Exception as e:
        print(f"Upload track error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stream-local/<track_id>', methods=['GET'])
@require_auth
def stream_local_track(track_id: str):
    """Стрим локально загруженного трека по track_id."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tg_file = loop.run_until_complete(db.get_telegram_file(track_id))
        loop.close()

        if not tg_file:
            return jsonify({'error': 'Track not found'}), 404

        local_path = tg_file.telegram_file_path
        if not local_path or not os.path.exists(local_path):
            return jsonify({'error': 'File not found on disk'}), 404

        return send_file(local_path, as_attachment=False, conditional=True)
    except Exception as e:
        print(f"Stream local error: {e}")
        return jsonify({'error': str(e)}), 500


def _local_cover_file_path(base_dir: str, track_id: str) -> str | None:
    covers_dir = os.path.join(base_dir, 'uploads', 'covers')
    if not os.path.isdir(covers_dir):
        return None
    prefix = f"{track_id}."
    for name in os.listdir(covers_dir):
        if name.startswith(prefix):
            full = os.path.join(covers_dir, name)
            if os.path.isfile(full):
                return full
    return None


@app.route('/api/local-cover/<track_id>', methods=['GET'])
@require_auth
def local_cover_image(track_id: str):
    """Отдача обложки локально загруженного трека."""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = _local_cover_file_path(base_dir, track_id)
        if not path:
            return jsonify({'error': 'Cover not found'}), 404
        mt, _ = mimetypes.guess_type(path)
        return send_file(path, mimetype=mt or 'image/jpeg', as_attachment=False, conditional=True)
    except Exception as e:
        print(f"Local cover error: {e}")
        return jsonify({'error': str(e)}), 500


def search_by_url(url):
    """Поиск по Spotify URL.

    Для плейлиста:
    - сначала возвращаем только информацию о плейлисте (playlists), без треков,
      чтобы фронтенд показывал карточку плейлиста первой;
    - сами треки запрашиваются отдельным вызовом /api/spotify-playlists/<id>/tracks.
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        info = None
        
        # Определяем тип URL (track, album, playlist, artist)
        if '/track/' in url:
            track_info = loop.run_until_complete(spotify_service.get_track_info_from_url(url))
            loop.close()
            
            if track_info:
                return jsonify({
                    'tracks': [{
                        'id': track_info.get('id', ''),
                        'name': track_info.get('name'),
                        'artist': track_info.get('artist'),
                        'album': track_info.get('album', ''),
                        'duration': 0,
                        'image': track_info.get('image_url'),
                        'preview_url': None
                    }]
                })
        
        elif '/playlist/' in url:
            info = loop.run_until_complete(spotify_service.get_playlist_info(url))
            parsed = spotify_service.parse_spotify_url(url)
            playlist_id = parsed.get("id") if parsed else None
            loop.close()

            if info:
                # Сохраняем в глобальный каталог публичных плейлистов
                try:
                    if playlist_id:
                        run_async(db.save_public_spotify_playlist(
                            spotify_id=playlist_id,
                            name=info.get('name') or 'Playlist',
                            owner=info.get('owner', ''),
                            spotify_url=f"https://open.spotify.com/playlist/{playlist_id}",
                            total_tracks=len(info.get('tracks') or []),
                            added_by_user_id=getattr(g, 'current_user_id', None)
                        ))
                except Exception as save_e:
                    print(f"⚠️ Failed to save public playlist: {save_e}")

                # Возвращаем только плейлист, без списка треков
                image = info.get('image')
                return jsonify({
                    'playlists': [{
                        'id': playlist_id,
                        'name': info.get('name'),
                        'owner': info.get('owner', ''),
                        'image': image,
                        'total_tracks': len(info.get('tracks') or []),
                        'type': 'playlist'
                    }],
                    'tracks': []
                })
        elif '/album/' in url:
            info = loop.run_until_complete(spotify_service.get_album_info(url))
        elif '/artist/' in url:
            info = loop.run_until_complete(spotify_service.get_artist_info(url))
        
        loop.close()
        
        if info and info.get('tracks'):
            # Для album/artist оставляем старое поведение — сразу треки коллекции.
            tracks = []
            for track in info['tracks']:
                tracks.append({
                    'id': track.get('id', f"{track['artist']}_{track['name']}"),
                    'name': track['name'],
                    'artist': track['artist'],
                    'album': track.get('album') or info['name'],
                    'duration': track.get('duration', 0),
                    'image': track.get('image'),
                    'preview_url': None,
                    'collection_name': info['name'],
                    'collection_type': info.get('type', 'collection')
                })
            
            return jsonify({
                'tracks': tracks,
                'collection_info': {
                    'name': info['name'],
                    'type': info.get('type', 'collection'),
                    'total_tracks': len(tracks)
                }
            })
            
        return jsonify({'tracks': [], 'error': 'No tracks found in this link'})
    
    except Exception as e:
        print(f"❌ Error in search_by_url: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'tracks': []})

@app.route('/api/download', methods=['POST'])
@require_auth
@rate_limit(DOWNLOAD_LIMIT, DOWNLOAD_PERIOD)
def download():
    """Скачивание трека"""
    # Создаем один loop на весь запрос
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        user_id = getattr(g, 'current_user_id', None)
        if not user_id:
            loop.close()
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json
        track_id = data.get('track_id')
        track_name = data.get('track_name')
        track_artist = data.get('track_artist')
        quality = data.get('quality', '320')
        file_format = data.get('format', 'mp3')
        
        # Если есть имя и исполнитель, используем их напрямую
        if track_name and track_artist:
            # 1. Скачиваем файл
            result = loop.run_until_complete(
                download_service.search_and_download(
                    track_artist,
                    track_name,
                    quality,
                    file_format
                )
            )
            
            if result and result.get('file_path') and os.path.exists(result['file_path']):
                file_path = result['file_path']
                
                # РЕГИСТРАЦИЯ В DISCOVER (Функция для надежности)
                try:
                    # Генерируем ID если его нет
                    if not track_id:
                        import hashlib
                        unique_string = f"{track_artist}_{track_name}".lower()
                        track_id = hashlib.md5(unique_string.encode()).hexdigest()[:16]
                    
                    # Используем метаданные из YouTube (thumbnail) для изображения
                    track_data = {
                        'id': track_id,
                        'name': track_name,
                        'artist': track_artist,
                        'spotify_url': f"https://open.spotify.com/search/{track_artist} {track_name}",
                        'image_url': result.get('thumbnail')  # Используем YouTube thumbnail
                    }
                    
                    # 1. Создаем трек в БД с изображением из YouTube
                    loop.run_until_complete(db.get_or_create_track(track_data))
                    
                    # 2. ПРОВЕРЯЕМ ДУБЛИКАТЫ ПЕРЕД ЗАГРУЗКОЙ (Функция deduplication)
                    existing_file = loop.run_until_complete(db.get_telegram_file(track_id))
                    if not existing_file:
                        existing_file = loop.run_until_complete(db.get_telegram_file_by_name(track_artist, track_name))
                    
                    if existing_file:
                        print(f"✅ Track already in Telegram Storage, skipping duplicate upload: {track_name}")
                        file_id = existing_file.file_id
                    else:
                        # Загружаем в Telegram Storage (чтобы появился в Discover)
                        print(f"📤 Auto-uploading web download to Telegram: {track_name}")
                        upload_result = get_telegram_storage().upload_file(file_path, f"🎵 {track_artist} - {track_name}")
                        file_id = upload_result.get('file_id') if upload_result else None
                    
                    if file_id:
                        # Сохраняем во все кэш-таблицы
                        loop.run_until_complete(db.update_track_cache(track_id, file_id, file_format, quality))
                        loop.run_until_complete(db.save_telegram_file(
                            track_id=track_id, 
                            file_id=file_id, 
                            artist=track_artist, 
                            track_name=track_name, 
                            file_size=result.get('file_size', 0)
                        ))

                    # Записываем в web history
                    loop.run_until_complete(
                        db.add_download_to_history(
                            user_id=user_id,
                            track_id=track_id,
                            quality=str(quality),
                            file_size=result.get('file_size', 0)
                        )
                    )
                    backup_svc = get_backup_service()
                    loop.run_until_complete(backup_svc.backup_to_telegram())
                except Exception as reg_e:
                    print(f"⚠️ Warning: Registration in discovery failed: {reg_e}")
                return send_file(
                    file_path,
                    as_attachment=True,
                    download_name=f"{track_artist} - {track_name}.{file_format}"
                )
            else:
                error_msg = result.get('error') if result else "Unknown error"
                loop.close()
                return jsonify({'error': f"Download failed: {error_msg}"}), 500
        
        # Иначе используем track_id
        if not track_id:
            loop.close()
            return jsonify({'error': 'Track ID or name/artist is required'}), 400
        
        # 1. Получаем информацию о треке (ВАЖНО: До скачивания для метаданных)
        track_info = loop.run_until_complete(spotify_service.get_track_info(track_id))
        
        if not track_info:
            loop.close()
            return jsonify({'error': 'Track not found'}), 404
            
        # 2. Скачиваем трек
        result = loop.run_until_complete(
            download_service.search_and_download(
                track_info['artist'],
                track_info['name'],
                quality,
                file_format
            )
        )
        
        if result and result.get('file_path') and os.path.exists(result['file_path']):
            file_path = result['file_path']
            

            # РЕГИСТРАЦИЯ В DISCOVER
            try:
                # 1. ГАРАНТИРУЕМ ЧТО ТРЕК ЕСТЬ В БД (Важно для Foreign Key в cache/files)
                track_data = {
                    'id': track_id,
                    'name': track_info['name'],
                    'artist': track_info['artist'],
                    'spotify_url': f"https://open.spotify.com/track/{track_id}",
                    'image_url': track_info.get('image_url') or result.get('thumbnail')  # Spotify image или YouTube thumbnail
                }
                loop.run_until_complete(db.get_or_create_track(track_data))

                # 2. ПРОВЕРЯЕМ ДУБЛИКАТЫ ПЕРЕД ЗАГРУЗКОЙ
                existing_file = loop.run_until_complete(db.get_telegram_file(track_id))
                if not existing_file:
                    existing_file = loop.run_until_complete(db.get_telegram_file_by_name(track_info['artist'], track_info['name']))
                
                if existing_file:
                    print(f"✅ Track already in Telegram Storage, skipping duplicate upload: {track_info['name']}")
                    file_id = existing_file.file_id
                else:
                    # Загружаем в Telegram Storage
                    print(f"📤 Auto-uploading web download to Telegram: {track_info['name']}")
                    upload_result = get_telegram_storage().upload_file(file_path, f"🎵 {track_info['artist']} - {track_info['name']}")
                    file_id = upload_result.get('file_id') if upload_result else None
                
                if file_id:
                    # Сохраняем в кэш и в Discovery-таблицу
                    loop.run_until_complete(db.update_track_cache(track_id, file_id, file_format, quality))
                    loop.run_until_complete(db.save_telegram_file(
                        track_id=track_id, 
                        file_id=file_id, 
                        artist=track_info['artist'], 
                        track_name=track_info['name'], 
                        file_size=result.get('file_size', 0),
                        file_path=file_id # Используем file_id как путь для совместимости
                    ))

                # Записываем в web history
                loop.run_until_complete(
                    db.add_download_to_history(
                        user_id=user_id,
                        track_id=track_id,
                        quality=str(quality),
                        file_size=result.get('file_size', 0)
                    )
                )
                backup_svc = get_backup_service()
                loop.run_until_complete(backup_svc.backup_to_telegram())
            except Exception as reg_e:
                print(f"⚠️ Warning: Registration in discovery failed: {reg_e}")

            loop.close()
            return send_file(
                file_path,
                as_attachment=True,
                download_name=f"{track_info['artist']} - {track_info['name']}.{file_format}"
            )
        else:
            error_msg = result.get('error') if result else "Unknown error"
            if 'loop' in locals() and not loop.is_closed():
                loop.close()
            return jsonify({'error': f"Download failed: {error_msg}"}), 500
    
    except Exception as e:
        if 'loop' in locals() and not loop.is_closed():
            loop.close()
        print(f"❌ Download error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Временное хранилище токенов (в идеале использовать Redis или общую таблицу в БД)
# Но для простоты пока будем использовать глобальную переменную, 
# так как бот и веб работают в разных процессах, нам нужно общее хранилище.
# ОБНОВЛЕНИЕ: Лучше использовать таблицу в БД для синхронизации между процессами.

@app.route('/api/auth', methods=['POST'])
def authenticate():
    """Верификация токена из Telegram и выдача веб-сессионного токена."""
    try:
        data = request.json or {}
        token = data.get('token')

        if not token:
            return jsonify({'error': 'Token is required'}), 400

        # Проверяем токен в БД (постоянная ссылка из /login)
        user = run_async(db.verify_auth_token(token))

        if not user:
            return jsonify({'error': 'Invalid or expired token'}), 401

        # Создаём веб-сессию (JWT)
        session_token = create_session_token(user.id)
        resp = jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username or 'User',
                'first_name': user.first_name,
                'last_name': user.last_name,
                'avatar_url': get_telegram_avatar_url(user.id)
            }
        })
        # Храним токен только в HttpOnly cookie, а не в localStorage
        cookie_secure_env = os.getenv("WEB_COOKIE_SECURE", "auto").strip().lower()
        secure_cookie = request.is_secure if cookie_secure_env == "auto" else cookie_secure_env in ("1", "true", "yes", "on")
        resp.set_cookie(
            "session_token",
            session_token,
            max_age=SESSION_TTL_SECONDS,
            httponly=True,
            secure=secure_cookie,
            samesite="Lax",
            path="/",
        )
        return resp
    except Exception as e:
        print(f"❌ Auth error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/me', methods=['GET'])
@require_auth
def get_me():
    """Текущий пользователь по cookie/JWT-сессии."""
    try:
        user_id = getattr(g, 'current_user_id', None)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        user = run_async(db.get_or_create_user(user_id))
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username or 'User',
                'first_name': user.first_name,
                'last_name': user.last_name,
                'avatar_url': get_telegram_avatar_url(user.id)
            }
        })
    except Exception as e:
        print(f"❌ Me error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/my-spotify-playlists', methods=['GET', 'POST'])
@require_auth
def my_spotify_playlists():
    """Личные сохранённые Spotify-плейлисты пользователя (web)."""
    try:
        user_id = getattr(g, 'current_user_id', None)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        if request.method == 'GET':
            items = run_async(db.get_user_spotify_playlists(user_id))
            playlists = []
            for p in items:
                playlists.append({
                    'spotify_id': p.spotify_id,
                    'name': p.name,
                    'owner': p.owner,
                    'spotify_url': p.spotify_url,
                    'total_tracks': p.total_tracks,
                })
            return jsonify({'playlists': playlists})

        data = request.json or {}
        spotify_id = (data.get('spotify_id') or '').strip()
        name = (data.get('name') or '').strip() or 'Playlist'
        owner = (data.get('owner') or '').strip() or None
        spotify_url = (data.get('spotify_url') or '').strip() or None
        total_tracks = data.get('total_tracks')

        if not spotify_id:
            return jsonify({'error': 'spotify_id is required'}), 400

        pl = run_async(db.save_user_spotify_playlist(
            user_id=user_id,
            spotify_id=spotify_id,
            name=name,
            owner=owner,
            spotify_url=spotify_url,
            total_tracks=total_tracks,
        ))
        return jsonify({
            'success': True,
            'playlist': {
                'spotify_id': pl.spotify_id,
                'name': pl.name,
                'owner': pl.owner,
                'spotify_url': pl.spotify_url,
                'total_tracks': pl.total_tracks,
            }
        })
    except Exception as e:
        print(f"❌ my_spotify_playlists error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/api/audit-logs', methods=['GET'])
@require_auth
@require_admin
def admin_audit_logs():
    """Логи действий админа."""
    try:
        limit = int(request.args.get('limit', 50))
        limit = max(1, min(limit, 200))
        logs = run_async(db.get_admin_audit_logs(limit=limit))
        for item in logs:
            if item.get("created_at") and hasattr(item["created_at"], "isoformat"):
                item["created_at"] = item["created_at"].isoformat()
        return jsonify({"logs": logs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/logout', methods=['POST'])
def logout():
    """Выйти из веб-сессии (очистить cookie)."""
    resp = jsonify({'success': True})
    # Удаляем cookie с теми же атрибутами path/samesite; secure зависит от окружения
    cookie_secure_env = os.getenv("WEB_COOKIE_SECURE", "auto").strip().lower()
    secure_cookie = request.is_secure if cookie_secure_env == "auto" else cookie_secure_env in ("1", "true", "yes", "on")
    resp.set_cookie(
        "session_token",
        "",
        max_age=0,
        expires=0,
        httponly=True,
        secure=secure_cookie,
        samesite="Lax",
        path="/",
    )
    return resp

@app.route('/api/playlists', methods=['GET', 'POST'])
@require_auth
def handle_playlists():
    """Работа с плейлистами"""
    try:
        user_id = getattr(g, 'current_user_id', None)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
            
        if request.method == 'GET':
            # Получить список плейлистов
            playlists_db = loop.run_until_complete(db.get_user_playlists(user_id))
            
            result = []
            for pl in playlists_db:
                # Получаем количество треков
                count = loop.run_until_complete(db.get_playlist_track_count(user_id, pl.id))
                result.append({
                    'id': pl.id,
                    'name': pl.name,
                    'description': pl.description,
                    'track_count': count
                })
            
            loop.close()
            return jsonify({'playlists': result})
            
        elif request.method == 'POST':
            # Создать новый плейлист
            data = request.json
            name = data.get('name')
            description = data.get('description', '')
            
            if not name:
                return jsonify({'error': 'Name is required'}), 400
                
            playlist = loop.run_until_complete(db.create_playlist(user_id, name, description))
            loop.close()
            
            # Trigger immediate backup
            try:
                backup_service = get_backup_service()
                # Run sync in separate thread/loop or just wait? 
                # Since this is a simple Flask app without Celery/Redis, we can run it synchronously 
                # or create a new loop just for this.
                # However, backup_to_telegram is async.
                
                # Re-using a new loop for backup
                backup_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(backup_loop)
                backup_loop.run_until_complete(backup_service.backup_to_telegram(force=True))
                backup_loop.close()
            except Exception as e:
                print(f"⚠️ Backup trigger failed: {e}")

            return jsonify({
                'id': playlist.id,
                'name': playlist.name,
                'description': playlist.description
            })
            
    except Exception as e:
        print(f"❌ Playlists API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/playlists/add_track', methods=['POST'])
@require_auth
def add_track_to_playlist():
    """Добавить трек в плейлист"""
    try:
        user_id = getattr(g, 'current_user_id', None)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        data = request.json
        playlist_id = data.get('playlist_id')
        track_data = data.get('track')
        
        if not playlist_id or not track_data:
            return jsonify({'error': 'Missing required data'}), 400
            
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 1. Получаем/создаем трек в БД
        # Генерируем стабильный ID на основе названия и исполнителя
        import hashlib
        track_id = track_data.get('id')
        if not track_id or track_id.startswith('web_'):
            # Создаем уникальный ID на основе исполнителя и названия
            unique_string = f"{track_data.get('artist', '')}_{track_data.get('name', '')}".lower()
            track_id = f"web_{hashlib.md5(unique_string.encode()).hexdigest()[:16]}"
        
        track = loop.run_until_complete(db.get_or_create_track({
            'id': track_id,
            'name': track_data.get('name'),
            'artist': track_data.get('artist'),
            'album': track_data.get('album'),
            'image_url': track_data.get('image'),
            'spotify_url': track_data.get('spotify_url', '')
        }))
        
        # 2. Добавляем в плейлист
        success = loop.run_until_complete(db.add_track_to_playlist(user_id, playlist_id, track.id))
        loop.close()
        
        if success:
            # Trigger immediate backup
            try:
                backup_service = get_backup_service()
                backup_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(backup_loop)
                backup_loop.run_until_complete(backup_service.backup_to_telegram(force=True))
                backup_loop.close()
            except Exception as e:
                print(f"⚠️ Backup trigger failed: {e}")

            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Track already in playlist'}), 400
            
    except Exception as e:
        print(f"❌ Add track error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/playlists/<int:playlist_id>/tracks', methods=['GET'])
@require_auth
def get_playlist_tracks(playlist_id):
    """Получить треки плейлиста"""
    try:
        user_id = getattr(g, 'current_user_id', None)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
            
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Получаем треки плейлиста
        tracks = loop.run_until_complete(db.get_playlist_tracks(user_id, playlist_id))
        loop.close()
        
        # Форматируем результат
        result = []
        for track in tracks:
            result.append({
                'id': track.id,
                'name': track.name,
                'artist': track.artist,
                'album': track.album,
                'duration': track.duration_ms // 1000 if track.duration_ms else 0,
                'image': track.image_url,
                'spotify_url': track.spotify_url
            })
        
        return jsonify({'tracks': result})
        
    except Exception as e:
        print(f"❌ Get playlist tracks error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/history', methods=['GET'])
@require_auth
def get_history():
    """История скачиваний пользователя (web)"""
    try:
        user_id = getattr(g, 'current_user_id', None)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        # Ленивая подкачка: по умолчанию 10 последних
        try:
            limit = int(request.args.get('limit', 10))
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 50))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        history_items = loop.run_until_complete(db.get_download_history(user_id, limit=limit))
        loop.close()

        # Приводим к JSON-сериализуемому виду
        history = []
        for item in history_items:
            downloaded_at = item.get('downloaded_at')
            if downloaded_at and hasattr(downloaded_at, 'isoformat'):
                downloaded_at = downloaded_at.isoformat()

            history.append({
                'track': item.get('track'),
                'downloaded_at': downloaded_at,
                'quality': item.get('quality'),
            })

        return jsonify({'history': history})
    except Exception as e:
        print(f"❌ Get history error: {e}")
        return jsonify({'error': str(e)}), 500


def ensure_track_cached(loop, track_id: str, artist: str, track_name: str, image_url: str = None) -> dict:
    """
    Гарантировать, что трек есть в Telegram Storage и в локальном кэше БД.
    Возвращает {'success': bool, 'cached': bool, 'file_id': str|None, 'stream_url': str|None, 'error': str|None}.
    """
    if not artist or not track_name:
        return {'success': False, 'error': 'Artist and track name required'}

    file_id = None
    telegram_file = loop.run_until_complete(db.get_telegram_file(track_id))
    if telegram_file:
        file_id = telegram_file.file_id
    else:
        telegram_file_by_name = loop.run_until_complete(db.get_telegram_file_by_name(artist, track_name))
        if telegram_file_by_name:
            file_id = telegram_file_by_name.file_id
        else:
            for q in ['320', '192', '128', 'FLAC']:
                file_id = loop.run_until_complete(db.get_cached_file_id(track_id, quality=q))
                if file_id:
                    break

    if file_id:
        # Нормализуем связь track_id -> file_id, чтобы следующий поиск был быстрее.
        try:
            track_data = {
                'id': track_id,
                'name': track_name,
                'artist': artist,
                'spotify_url': f"https://open.spotify.com/search/{artist} {track_name}",
                'image_url': image_url
            }
            loop.run_until_complete(db.get_or_create_track(track_data))
            loop.run_until_complete(db.update_track_cache(track_id, file_id, 'mp3', '192'))
            loop.run_until_complete(db.save_telegram_file(
                track_id=track_id,
                file_id=file_id,
                artist=artist,
                track_name=track_name,
                image_url=image_url
            ))
        except Exception as relink_e:
            print(f"⚠️ Relink warning for cached track {track_id}: {relink_e}")

        file_url = get_telegram_storage().get_file_url(file_id)
        return {'success': True, 'cached': True, 'file_id': file_id, 'stream_url': file_url}

    result = loop.run_until_complete(
        download_service.search_and_download(
            artist,
            track_name,
            '192',
            'mp3'
        )
    )
    if not result or result.get('error'):
        return {'success': False, 'error': result.get('error') if result else 'Unknown download error'}
    if not result.get('file_path') or not os.path.exists(result['file_path']):
        return {'success': False, 'error': 'File not found after download'}

    file_path = result['file_path']
    caption = f"🎵 {artist} - {track_name}"
    upload_result = get_telegram_storage().upload_file(file_path, caption)
    if not upload_result or not upload_result.get('file_id'):
        return {'success': False, 'error': 'Failed to upload to Telegram Storage'}

    final_image_url = image_url or result.get('thumbnail')
    file_id = upload_result['file_id']
    track_data = {
        'id': track_id,
        'name': track_name,
        'artist': artist,
        'spotify_url': f"https://open.spotify.com/search/{artist} {track_name}",
        'image_url': final_image_url
    }
    loop.run_until_complete(db.get_or_create_track(track_data))
    loop.run_until_complete(db.update_track_cache(track_id, file_id, 'mp3', '192'))
    loop.run_until_complete(db.save_telegram_file(
        track_id=track_id,
        file_id=file_id,
        file_path=upload_result.get('file_path'),
        file_size=upload_result.get('file_size'),
        artist=artist,
        track_name=track_name,
        image_url=final_image_url
    ))

    try:
        download_service.cleanup_file(file_path)
    except Exception:
        pass

    file_url = get_telegram_storage().get_file_url(file_id)
    return {'success': True, 'cached': False, 'file_id': file_id, 'stream_url': file_url}


def _run_playlist_cache_job(job_id: str, user_id: int, spotify_id: str, requested_limit: int):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        _set_playlist_cache_job(job_id, status='running', progress_percent=1, message='Loading playlist...')

        limit = max(1, min(int(requested_limit or 50), 100))
        url = f"https://open.spotify.com/playlist/{spotify_id}"
        info = loop.run_until_complete(spotify_service.get_playlist_info(url))
        if not info or not info.get('tracks'):
            _set_playlist_cache_job(job_id, status='failed', error='Playlist not found or empty', progress_percent=100)
            return

        all_tracks = info.get('tracks') or []
        playlist_name = info.get('name') or 'Playlist'
        playlist_owner = info.get('owner') or ''
        total_tracks = len(all_tracks)

        existing_public = loop.run_until_complete(db.get_public_spotify_playlist(spotify_id))
        start_from = 0
        if existing_public and existing_public.cached_tracks_count:
            start_from = max(0, min(int(existing_public.cached_tracks_count), total_tracks))

        end_index = min(start_from + limit, total_tracks)
        tracks = all_tracks[start_from:end_index]

        loop.run_until_complete(db.save_user_spotify_playlist(
            user_id=user_id,
            spotify_id=spotify_id,
            name=playlist_name,
            owner=playlist_owner,
            spotify_url=url,
            total_tracks=total_tracks,
        ))
        loop.run_until_complete(db.save_public_spotify_playlist(
            spotify_id=spotify_id,
            name=playlist_name,
            owner=playlist_owner,
            spotify_url=url,
            total_tracks=total_tracks,
            added_by_user_id=user_id,
        ))

        cached_count = 0
        uploaded_count = 0
        failed_count = 0
        failed_tracks = []
        current_checkpoint = start_from

        _set_playlist_cache_job(
            job_id,
            status='running',
            progress_percent=2,
            message=f'Processing {len(tracks)} tracks...',
            total_tracks=total_tracks,
            resume_from=start_from,
            processed=0
        )

        for idx, t in enumerate(tracks):
            tid = (t.get('id') or '').strip()
            artist = (t.get('artist') or '').strip()
            name = (t.get('name') or '').strip()
            if not tid:
                tid = hashlib.md5(f"{artist}_{name}".lower().encode()).hexdigest()[:16]

            if not name or not artist:
                failed_count += 1
                if len(failed_tracks) < 5:
                    failed_tracks.append({'name': name or 'Unknown', 'artist': artist or 'Unknown', 'error': 'Invalid track data'})
            else:
                result = ensure_track_cached(loop, tid, artist, name, t.get('image'))
                if result.get('success'):
                    if result.get('cached'):
                        cached_count += 1
                    else:
                        uploaded_count += 1
                    current_checkpoint += 1
                else:
                    failed_count += 1
                    if len(failed_tracks) < 5:
                        failed_tracks.append({'name': name, 'artist': artist, 'error': result.get('error', 'Unknown error')})

            processed = idx + 1
            progress = int((processed / max(1, len(tracks))) * 100)
            _set_playlist_cache_job(
                job_id,
                status='running',
                progress_percent=progress,
                message=f'Caching {processed}/{len(tracks)}',
                processed=processed,
                current_track=f'{artist} - {name}'
            )

        try:
            backup_svc = get_backup_service()
            loop.run_until_complete(backup_svc.backup_to_telegram())
        except Exception as backup_e:
            print(f"⚠️ Playlist cache backup failed: {backup_e}")

        loop.run_until_complete(db.save_public_spotify_playlist(
            spotify_id=spotify_id,
            name=playlist_name,
            owner=playlist_owner,
            spotify_url=url,
            total_tracks=total_tracks,
            added_by_user_id=user_id,
            is_cached_public=True,
            cached_tracks_count=current_checkpoint,
            cached_at=datetime.utcnow(),
        ))

        _set_playlist_cache_job(
            job_id,
            status='completed',
            progress_percent=100,
            message='Completed',
            playlist={
                'spotify_id': spotify_id,
                'name': playlist_name,
                'owner': playlist_owner,
                'total_tracks': total_tracks,
                'processed_tracks': len(tracks),
                'start_from': start_from,
                'end_at': current_checkpoint
            },
            cache_result={
                'already_cached': cached_count,
                'uploaded_new': uploaded_count,
                'failed': failed_count,
                'failed_examples': failed_tracks,
                'resume_from': start_from,
                'next_index': current_checkpoint,
                'completed': current_checkpoint >= total_tracks
            }
        )
    except Exception as e:
        print(f"❌ Playlist cache job error: {e}")
        _set_playlist_cache_job(job_id, status='failed', error=str(e), progress_percent=100, message='Failed')
    finally:
        loop.close()


@app.route('/api/spotify-playlists/<string:spotify_id>/cache/start', methods=['POST'])
@require_auth
@rate_limit(SYNC_LIMIT, SYNC_PERIOD)
def start_cache_spotify_playlist_job(spotify_id: str):
    try:
        user_id = getattr(g, 'current_user_id', None)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json or {}
        requested_limit = data.get('limit', 50)
        job_id = str(uuid.uuid4())
        _set_playlist_cache_job(job_id, status='queued', progress_percent=0, message='Queued...')

        thread = threading.Thread(
            target=_run_playlist_cache_job,
            args=(job_id, int(user_id), spotify_id, requested_limit),
            daemon=True
        )
        thread.start()
        return jsonify({'success': True, 'job_id': job_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/spotify-playlists/cache-jobs/<string:job_id>', methods=['GET'])
@require_auth
def get_cache_spotify_playlist_job(job_id: str):
    job = _get_playlist_cache_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify({'success': True, 'job': job})


@app.route('/api/spotify-playlists/<string:spotify_id>/cache', methods=['POST'])
@require_auth
@rate_limit(SYNC_LIMIT, SYNC_PERIOD)
def cache_spotify_playlist(spotify_id: str):
    """Сохранить плейлист в личный список и прогреть кэш всех его треков в Telegram Storage."""
    try:
        user_id = getattr(g, 'current_user_id', None)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json or {}
        requested_limit = data.get('limit', 50)
        try:
            limit = int(requested_limit)
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 100))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        url = f"https://open.spotify.com/playlist/{spotify_id}"
        info = loop.run_until_complete(spotify_service.get_playlist_info(url))
        if not info or not info.get('tracks'):
            loop.close()
            return jsonify({'error': 'Playlist not found or empty'}), 404

        all_tracks = info.get('tracks') or []
        existing_public = loop.run_until_complete(db.get_public_spotify_playlist(spotify_id))
        start_from = 0
        if existing_public and existing_public.cached_tracks_count:
            # Resume from last successful checkpoint (contiguous progress).
            start_from = max(0, min(int(existing_public.cached_tracks_count), len(all_tracks)))

        end_index = min(start_from + limit, len(all_tracks))
        tracks = all_tracks[start_from:end_index]
        playlist_name = info.get('name') or 'Playlist'
        playlist_owner = info.get('owner') or ''

        # Сохраняем плейлист у пользователя
        loop.run_until_complete(db.save_user_spotify_playlist(
            user_id=user_id,
            spotify_id=spotify_id,
            name=playlist_name,
            owner=playlist_owner,
            spotify_url=url,
            total_tracks=len(info.get('tracks') or []),
        ))
        # И сразу в публичный каталог
        loop.run_until_complete(db.save_public_spotify_playlist(
            spotify_id=spotify_id,
            name=playlist_name,
            owner=playlist_owner,
            spotify_url=url,
            total_tracks=len(info.get('tracks') or []),
            added_by_user_id=user_id,
        ))

        cached_count = 0
        uploaded_count = 0
        failed_count = 0
        failed_tracks = []

        current_checkpoint = start_from
        for t in tracks:
            tid = (t.get('id') or '').strip()
            artist = (t.get('artist') or '').strip()
            name = (t.get('name') or '').strip()
            if not name or not artist:
                failed_count += 1
                if len(failed_tracks) < 5:
                    failed_tracks.append({'name': name or 'Unknown', 'artist': artist or 'Unknown', 'error': 'Invalid track data'})
                continue

            if not tid:
                tid = hashlib.md5(f"{artist}_{name}".lower().encode()).hexdigest()[:16]

            result = ensure_track_cached(loop, tid, artist, name, t.get('image'))
            if result.get('success'):
                if result.get('cached'):
                    cached_count += 1
                else:
                    uploaded_count += 1
                current_checkpoint += 1
            else:
                failed_count += 1
                if len(failed_tracks) < 5:
                    failed_tracks.append({'name': name, 'artist': artist, 'error': result.get('error', 'Unknown error')})

        # Один backup после пакетной операции
        try:
            backup_svc = get_backup_service()
            loop.run_until_complete(backup_svc.backup_to_telegram())
        except Exception as backup_e:
            print(f"⚠️ Playlist cache backup failed: {backup_e}")

        # Обновляем публичный статус кэша плейлиста
        loop.run_until_complete(db.save_public_spotify_playlist(
            spotify_id=spotify_id,
            name=playlist_name,
            owner=playlist_owner,
            spotify_url=url,
            total_tracks=len(info.get('tracks') or []),
            added_by_user_id=user_id,
            is_cached_public=True,
            cached_tracks_count=current_checkpoint,
            cached_at=datetime.utcnow(),
        ))

        loop.close()
        return jsonify({
            'success': True,
            'playlist': {
                'spotify_id': spotify_id,
                'name': playlist_name,
                'owner': playlist_owner,
                'total_tracks': len(info.get('tracks') or []),
                'processed_tracks': len(tracks),
                'start_from': start_from,
                'end_at': current_checkpoint
            },
            'cache_result': {
                'already_cached': cached_count,
                'uploaded_new': uploaded_count,
                'failed': failed_count,
                'failed_examples': failed_tracks,
                'resume_from': start_from,
                'next_index': current_checkpoint,
                'completed': current_checkpoint >= len(all_tracks)
            }
        })
    except Exception as e:
        print(f"❌ cache_spotify_playlist error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/prepare-stream', methods=['POST'])
@require_auth
@rate_limit(PREPARE_STREAM_LIMIT, PREPARE_STREAM_PERIOD)
def prepare_stream():
    """Подготовить трек для стриминга через Telegram Storage"""
    try:
        data = request.json
        artist = data.get('artist', '')
        track_name = data.get('name', '')
        track_id = data.get('id', '')
        image_url = data.get('image') # Spotify image URL from search result
        
        if not artist or not track_name:
            return jsonify({'error': 'Artist and track name required'}), 400
        
        # Генерируем уникальный track_id если не передан
        if not track_id:
            import hashlib
            # Используем тот же алгоритм, что и в боте для консистентности
            unique_string = f"{artist}_{track_name}".lower()
            track_id = hashlib.md5(unique_string.encode()).hexdigest()[:16]
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = ensure_track_cached(loop, track_id, artist, track_name, image_url)
        loop.close()

        if result.get('success') and result.get('stream_url'):
            return jsonify({
                'success': True,
                'stream_url': result.get('stream_url'),
                'cached': bool(result.get('cached')),
                'title': f"{artist} - {track_name}"
            })
        return jsonify({'error': result.get('error') or 'Failed to prepare stream'}), 500
            
    except Exception as e:
        print(f"❌ Prepare stream error: {e}")
        import traceback
        traceback.print_exc()
        # Возвращаем детали ошибки для диагностики
        return jsonify({
            'error': f"Internal Server Error: {str(e)}",
            'type': type(e).__name__
        }), 500

@app.route('/api/stream-file/<path:filename>')
def stream_file(filename):
    """Стримить скачанный файл (legacy, теперь используем Telegram)"""
    try:
        # Получаем абсолютный путь к файлу
        file_path = os.path.join(download_service.download_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        # Отправляем файл с поддержкой Range requests для HTML5 audio
        return send_file(
            file_path,
            mimetype='audio/mpeg',
            as_attachment=False,
            conditional=True
        )
        
    except Exception as e:
        print(f"❌ Stream file error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/backup-db', methods=['POST'])
@require_auth
@rate_limit(BACKUP_LIMIT, BACKUP_PERIOD)
def backup_database():
    """Создать backup БД (вызывается при закрытии/обновлении страницы)"""
    try:
        backup_svc = get_backup_service()
        
        # Создаем backup асинхронно
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(backup_svc.backup_to_telegram())
        loop.close()
        
        if success:
            return jsonify({'success': True, 'message': 'Database backup created'})
        else:
            return jsonify({'success': False, 'error': 'Failed to create backup'}), 500
            
    except Exception as e:
        print(f"❌ Backup error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # Инициализация БД перед запуском
    
    # Запуск сервера
    port = int(os.environ.get('PORT', 5000))
    print(f"Web App starting on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
