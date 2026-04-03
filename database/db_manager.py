from __future__ import annotations
"""
Менеджер базы данных для работы с SQLite
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, delete, event, func
from sqlalchemy.engine import Engine
from typing import Optional, List
from datetime import datetime, timedelta

from .models import Base, User, Playlist, Track, PlaylistTrack, Album, DownloadHistory, Favorite, TrackCache, AuthToken, TelegramFile, BackupLog
import config
import os


class DatabaseManager:
    """Менеджер для асинхронной работы с базой данных"""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or config.DATABASE_URL

        # Диагностика пути к БД и создание файла если нужно
        db_path = self.database_url.replace('sqlite+aiosqlite:///', '').replace('sqlite:///', '')
        db_abs_path = os.path.abspath(db_path)

        # Убедимся что директория существует
        db_dir = os.path.dirname(db_abs_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            print(f"📁 Created database directory: {db_dir}", flush=True)

        # Создадим файл БД если его еще нет (простой touch)
        if not os.path.exists(db_abs_path):
            try:
                # Создаем пустой файл чтобы SQLite мог его открыть
                open(db_abs_path, 'a').close()
                print(f"📄 Created empty database file: {db_abs_path}", flush=True)
            except Exception as e:
                print(f"⚠️  Could not pre-create database file: {e}", flush=True)

        # Добавляем таймаут для SQLite чтобы избежать "database is locked" в многопроцессной среде
        connect_args = {"timeout": 20} if "sqlite" in self.database_url else {}
        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            connect_args=connect_args
        )

        print(f"🔍 [DB] Using database at: {db_abs_path} (Size: {os.path.getsize(db_abs_path) if os.path.exists(db_abs_path) else 'NOT FOUND'} bytes)", flush=True)
        
        # Включаем Foreign Keys на уровне драйвера SQLite для КАЖДОГО соединения
        if "sqlite" in self.database_url:
            @event.listens_for(Engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                # Снижает вероятность ошибок "database is locked" в многопроцессной среде
                cursor.execute("PRAGMA busy_timeout=5000")
                cursor.close()

        self.async_session = async_sessionmaker(
            self.engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )
    
    async def reconnect(self):
        """Пересоздать engine (полезно после восстановления БД из бэкапа)"""
        if self.engine:
            await self.engine.dispose()
        
        db_url = config.DATABASE_URL
        if db_url.startswith('sqlite://'):
            db_url = db_url.replace('sqlite://', 'sqlite+aiosqlite://')
            
        self.engine = create_async_engine(
            db_url,
            echo=False,
            connect_args={"timeout": 30}
        )
        self.async_session = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)
        print("🔌 Database engine re-initialized")

    async def init_db(self):
        """Инициализация базы данных и создание таблиц"""
        async with self.engine.begin() as conn:
            # Включаем WAL mode и Foreign Keys для лучшей параллельности и целостности в SQLite
            if "sqlite" in self.database_url:
                await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
                await conn.exec_driver_sql("PRAGMA foreign_keys = ON")
                # Более предсказуемая запись под нагрузкой
                await conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
                await conn.exec_driver_sql("PRAGMA temp_store=MEMORY")
            
            # checkfirst=True предотвращает ошибки если таблицы уже существуют (например, после восстановления из бэкапа)
            def create_tables(sync_conn):
                Base.metadata.create_all(bind=sync_conn, checkfirst=True)
            
            await conn.run_sync(create_tables)

            # Lightweight schema sync for SQLite (no migrations framework).
            # We ensure `users.is_admin` exists so admin checks won't crash on old DBs.
            if "sqlite" in self.database_url:
                def ensure_admin_column(sync_conn):
                    try:
                        columns = [row[1] for row in sync_conn.exec_driver_sql("PRAGMA table_info(users)")]
                        if "is_admin" not in columns:
                            print("⚙️ [DB] Adding missing column users.is_admin...")
                            sync_conn.exec_driver_sql("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
                    except Exception as e:
                        # Don't block startup if schema introspection fails.
                        print(f"⚠️ [DB] Could not ensure users.is_admin column: {e}")

                await conn.run_sync(ensure_admin_column)
        print("✅ База данных инициализирована (WAL mode enabled)")

    def get_database_file_path(self) -> Optional[str]:
        """
        Вернуть файловый путь к SQLite DB, если DATABASE_URL указывает на SQLite.
        Для PostgreSQL/прочих СУБД возвращает None.
        """
        url = (self.database_url or "").strip()
        if "sqlite" not in url:
            return None

        # Удаляем возможные параметры query string
        url = url.split("?", 1)[0]

        prefixes = [
            "sqlite+aiosqlite:///",
            "sqlite+aiosqlite://",
            "sqlite:///",
            "sqlite://",
        ]

        file_path = None
        for p in prefixes:
            if url.startswith(p):
                file_path = url[len(p):]
                break

        if not file_path:
            return None

        return os.path.abspath(file_path)
    
    async def close(self):
        """Закрытие соединения с БД"""
        await self.engine.dispose()
    
    # ========== ПОЛЬЗОВАТЕЛИ ==========
    
    async def get_or_create_user(self, user_id: int, tg_user_or_username: any = None, 
                                  first_name: str = None, last_name: str = None,
                                  username: str = None) -> User:
        """Получить или создать пользователя"""
        # Более надежный способ извлечения данных из объекта пользователя
        if tg_user_or_username and not isinstance(tg_user_or_username, str):
            tg_user = tg_user_or_username
            username = getattr(tg_user, 'username', None)
            # Приоритет отдаем переданным аргументам, если они не None
            first_name = first_name or getattr(tg_user, 'first_name', None)
            last_name = last_name or getattr(tg_user, 'last_name', None)
        else:
            username = tg_user_or_username

        async with self.async_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                user = User(
                    id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                print(f"✅ Создан новый пользователь: {user_id}")
            else:
                # Обновляем last_active
                user.last_active = datetime.utcnow()
                # Также обновляем информацию о пользователе, если она изменилась
                if username: user.username = username
                if first_name: user.first_name = first_name
                if last_name: user.last_name = last_name
                await session.commit()
            
            return user
    
    # ========== ПЛЕЙЛИСТЫ ==========
    
    async def create_playlist(self, user_id: int, name: str, description: str = None) -> Playlist:
        """Создать новый плейлист с гарантией существования пользователя"""
        async with self.async_session() as session:
            # ГАРАНТИРУЕМ существование пользователя (Foreign Key integrity)
            # Это критично для веб-версии, если пользователь еще не взаимодействовал с ботом
            user_result = await session.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            
            if not user:
                print(f"⚠️ Creating placeholder user {user_id} during playlist creation.")
                user = User(id=user_id, username="Web User")
                session.add(user)
                await session.flush() # Чтобы ID стал доступен для FK
            
            playlist = Playlist(
                user_id=user_id,
                name=name,
                description=description
            )
            session.add(playlist)
            await session.commit()
            await session.refresh(playlist)
            return playlist
    
    async def get_user_playlists(self, user_id: int) -> List[Playlist]:
        """Получить все плейлисты пользователя"""
        async with self.async_session() as session:
            result = await session.execute(
                select(Playlist)
                .where(Playlist.user_id == user_id)
                .order_by(Playlist.created_at.desc())
            )
            return list(result.scalars().all())
    
    async def get_playlist(self, playlist_id: int) -> Optional[Playlist]:
        """Получить плейлист по ID"""
        async with self.async_session() as session:
            result = await session.execute(select(Playlist).where(Playlist.id == playlist_id))
            return result.scalar_one_or_none()
    
    async def delete_playlist(self, playlist_id: int) -> bool:
        """Удалить плейлист"""
        async with self.async_session() as session:
            result = await session.execute(delete(Playlist).where(Playlist.id == playlist_id))
            await session.commit()
            return result.rowcount > 0
    
    # ========== ТРЕКИ ==========
    
    async def get_or_create_track(self, track_data: dict) -> Track:
        """Получить или создать трек, обогащая существующие треки недостающими данными"""
        async with self.async_session() as session:
            track_id = track_data['id']
            result = await session.execute(select(Track).where(Track.id == track_id))
            track = result.scalar_one_or_none()
            
            if not track:
                # Создаем новый трек
                track = Track(**track_data)
                session.add(track)
            else:
                # Обновляем существующий трек недостающими данными
                # Это важно для треков, созданных без полных метаданных
                updated = False
                
                # Обновляем image_url если его нет, а в новых данных есть
                if not track.image_url and track_data.get('image_url'):
                    track.image_url = track_data['image_url']
                    updated = True
                
                # Обновляем другие важные поля если они отсутствуют
                if not track.album and track_data.get('album'):
                    track.album = track_data['album']
                    updated = True
                
                if not track.duration_ms and track_data.get('duration_ms'):
                    track.duration_ms = track_data['duration_ms']
                    updated = True
                
                if not track.popularity and track_data.get('popularity'):
                    track.popularity = track_data['popularity']
                    updated = True
                
                if updated:
                    print(f"✅ Обогащен трек {track_id} новыми метаданными")
            
            await session.commit()
            await session.refresh(track)
            return track
    
    async def get_track(self, track_id: str) -> Optional[Track]:
        """Получить трек по ID"""
        async with self.async_session() as session:
            result = await session.execute(select(Track).where(Track.id == track_id))
            return result.scalar_one_or_none()

    async def delete_track_for_admin(self, track_id: str) -> bool:
        """
        Админ: удалить трек из БД.
        Примечание: удаление файла из Telegram Storage требует message_id файлов, в текущей схеме он не хранится,
        поэтому здесь удаляем только связанные записи в БД (с каскадом по внешним ключам).
        """
        async with self.async_session() as session:
            result = await session.execute(select(Track).where(Track.id == track_id))
            track = result.scalar_one_or_none()
            if not track:
                return False

            await session.execute(delete(Track).where(Track.id == track_id))
            await session.commit()
            return True
    
    # ========== ТРЕКИ В ПЛЕЙЛИСТАХ ==========
    
    async def add_track_to_playlist(self, user_id: int, playlist_id: int, track_id: str) -> bool:
        """Добавить трек в плейлист"""
        async with self.async_session() as session:
            # Проверяем владение плейлистом
            playlist_owner = await session.execute(
                select(Playlist.id).where(Playlist.id == playlist_id).where(Playlist.user_id == user_id)
            )
            if playlist_owner.scalar_one_or_none() is None:
                return False

            # Проверяем, не добавлен ли уже трек
            result = await session.execute(
                select(PlaylistTrack)
                .where(PlaylistTrack.playlist_id == playlist_id)
                .where(PlaylistTrack.track_id == track_id)
            )
            existing = result.scalars().first()
            
            if existing:
                return False  # Трек уже в плейлисте
            
            # Получаем максимальную позицию
            result = await session.execute(
                select(PlaylistTrack.position)
                .where(PlaylistTrack.playlist_id == playlist_id)
                .order_by(PlaylistTrack.position.desc())
            )
            max_position = result.scalars().first()
            new_position = (max_position or 0) + 1
            
            # Добавляем трек
            playlist_track = PlaylistTrack(
                playlist_id=playlist_id,
                track_id=track_id,
                position=new_position
            )
            session.add(playlist_track)
            
            # Обновляем время изменения плейлиста
            playlist_result = await session.execute(select(Playlist).where(Playlist.id == playlist_id))
            playlist = playlist_result.scalar_one_or_none()
            if playlist:
                playlist.updated_at = datetime.utcnow()
            
            await session.commit()
            return True
    
    async def get_playlist_tracks(self, user_id: int, playlist_id: int) -> List[Track]:
        """Получить все треки плейлиста"""
        async with self.async_session() as session:
            # Проверяем владение плейлистом
            playlist_owner = await session.execute(
                select(Playlist.id).where(Playlist.id == playlist_id).where(Playlist.user_id == user_id)
            )
            if playlist_owner.scalar_one_or_none() is None:
                return []

            result = await session.execute(
                select(Track)
                .join(PlaylistTrack)
                .where(PlaylistTrack.playlist_id == playlist_id)
                .order_by(PlaylistTrack.position)
            )
            return list(result.scalars().all())
    
    async def remove_track_from_playlist(self, user_id: int, playlist_id: int, track_id: str) -> bool:
        """Удалить трек из плейлиста"""
        async with self.async_session() as session:
            # Проверяем владение плейлистом
            playlist_owner = await session.execute(
                select(Playlist.id).where(Playlist.id == playlist_id).where(Playlist.user_id == user_id)
            )
            if playlist_owner.scalar_one_or_none() is None:
                return False

            result = await session.execute(
                delete(PlaylistTrack)
                .where(PlaylistTrack.playlist_id == playlist_id)
                .where(PlaylistTrack.track_id == track_id)
            )
            await session.commit()
            return result.rowcount > 0
    
    async def get_playlist_track_count(self, user_id: int, playlist_id: int) -> int:
        """Получить количество треков в плейлисте"""
        async with self.async_session() as session:
            # Проверяем владение плейлистом
            playlist_owner = await session.execute(
                select(Playlist.id).where(Playlist.id == playlist_id).where(Playlist.user_id == user_id)
            )
            if playlist_owner.scalar_one_or_none() is None:
                return 0

            result = await session.execute(
                select(PlaylistTrack)
                .where(PlaylistTrack.playlist_id == playlist_id)
            )
            return len(list(result.scalars().all()))
    
    # ========== ИСТОРИЯ СКАЧИВАНИЙ (Функция 5) ==========
    
    async def add_download_to_history(self, user_id: int, track_id: str, quality: str = '192', file_size: int = 0):
        """Добавить запись в историю скачиваний"""
        async with self.async_session() as session:
            history_entry = DownloadHistory(
                user_id=user_id,
                track_id=track_id,
                quality=quality,
                file_size_mb=file_size // (1024 * 1024)  # Конвертируем в MB
            )
            session.add(history_entry)
            
            # Обновляем статистику пользователя
            user_result = await session.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if user:
                user.total_downloads += 1
                user.total_size_mb += file_size // (1024 * 1024)
            
            # Обновляем счётчик скачиваний трека
            track_result = await session.execute(select(Track).where(Track.id == track_id))
            track = track_result.scalar_one_or_none()
            if track:
                track.download_count += 1
            
            await session.commit()
    
    async def get_download_history(self, user_id: int, limit: int = 10):
        """Получить историю скачиваний пользователя"""
        async with self.async_session() as session:
            result = await session.execute(
                select(DownloadHistory, Track)
                .join(Track, DownloadHistory.track_id == Track.id)
                .where(DownloadHistory.user_id == user_id)
                .order_by(DownloadHistory.downloaded_at.desc())
                .limit(limit)
            )
            
            history = []
            for download, track in result.all():
                history.append({
                    'track': {
                        'id': track.id,
                        'name': track.name,
                        'artist': track.artist,
                        'spotify_url': track.spotify_url
                    },
                    'downloaded_at': download.downloaded_at,
                    'quality': download.quality,
                    'file_size_mb': download.file_size_mb
                })
            
            return history
    
    async def clear_download_history(self, user_id: int):
        """Очистить историю скачиваний пользователя"""
        async with self.async_session() as session:
            await session.execute(
                delete(DownloadHistory).where(DownloadHistory.user_id == user_id)
            )
            await session.commit()
    
    # ========== ИЗБРАННОЕ (Функция 8) ==========
    
    async def add_to_favorites(self, user_id: int, track_id: str):
        """Добавить трек в избранное"""
        async with self.async_session() as session:
            # ГАРАНТИРУЕМ существование пользователя
            user_check = await session.execute(select(User).where(User.id == user_id))
            if not user_check.scalar_one_or_none():
                session.add(User(id=user_id, username="Web User"))
                await session.flush()

            # Проверяем, не добавлен ли уже
            result = await session.execute(
                select(Favorite)
                .where(Favorite.user_id == user_id)
                .where(Favorite.track_id == track_id)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                return False  # Уже в избранном
            
            favorite = Favorite(user_id=user_id, track_id=track_id)
            session.add(favorite)
            await session.commit()
            return True
    
    async def remove_from_favorites(self, user_id: int, track_id: str):
        """Удалить трек из избранного"""
        async with self.async_session() as session:
            result = await session.execute(
                delete(Favorite)
                .where(Favorite.user_id == user_id)
                .where(Favorite.track_id == track_id)
            )
            await session.commit()
            return result.rowcount > 0
    
    async def get_favorites(self, user_id: int):
        """Получить избранные треки пользователя"""
        async with self.async_session() as session:
            result = await session.execute(
                select(Favorite, Track)
                .join(Track, Favorite.track_id == Track.id)
                .where(Favorite.user_id == user_id)
                .order_by(Favorite.added_at.desc())
            )
            
            favorites = []
            for fav, track in result.all():
                favorites.append({
                    'track': {
                        'id': track.id,
                        'name': track.name,
                        'artist': track.artist,
                        'spotify_url': track.spotify_url,
                        'image_url': track.image_url
                    },
                    'added_at': fav.added_at
                })
            
            return favorites
    
    async def is_favorite(self, user_id: int, track_id: str) -> bool:
        """Проверить, находится ли трек в избранном"""
        async with self.async_session() as session:
            result = await session.execute(
                select(Favorite)
                .where(Favorite.user_id == user_id)
                .where(Favorite.track_id == track_id)
            )
            return result.scalar_one_or_none() is not None
    
    # ========== НАСТРОЙКИ ПОЛЬЗОВАТЕЛЯ (Функция 3, 18) ==========
    
    async def update_user_setting(self, user_id: int, setting_name: str, value):
        """Обновить настройку пользователя"""
        async with self.async_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if user:
                setattr(user, setting_name, value)
                await session.commit()
                return True
            return False
                
    async def is_library_empty(self) -> bool:
        """Проверить, пуста ли библиотека треков"""
        async with self.async_session() as session:
            from sqlalchemy import func
            result = await session.execute(select(func.count()).select_from(TelegramFile))
            count = result.scalar()
            print(f"📊 [DB] Library track count (TelegramFile): {count}", flush=True)
            return count == 0

    async def is_backup_logs_empty(self) -> bool:
        """Проверить, пуста ли таблица логов бэкапов"""
        async with self.async_session() as session:
            result = await session.execute(select(BackupLog).limit(1))
            return result.scalar_one_or_none() is None

    async def has_meaningful_data(self) -> bool:
        """
        Проверить, что в БД есть пользовательские данные, которые важно бэкапить.
        Используется на старте, чтобы не закреплять пустую БД как новый backup.
        """
        async with self.async_session() as session:
            playlist_count = await session.scalar(select(func.count()).select_from(Playlist))
            history_count = await session.scalar(select(func.count()).select_from(DownloadHistory))
            favorite_count = await session.scalar(select(func.count()).select_from(Favorite))
            tg_files_count = await session.scalar(select(func.count()).select_from(TelegramFile))
            track_cache_count = await session.scalar(select(func.count()).select_from(TrackCache))

            total = (
                int(playlist_count or 0)
                + int(history_count or 0)
                + int(favorite_count or 0)
                + int(tg_files_count or 0)
                + int(track_cache_count or 0)
            )
            return total > 0
            
    async def get_user_quality(self, user_id: int) -> str:
        """Получить предпочитаемое качество пользователя"""
        async with self.async_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            return user.preferred_quality if user else '192'
    
    async def get_user_stats(self, user_id: int):
        """Получить статистику пользователя"""
        async with self.async_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                return None
            
            return {
                'total_downloads': user.total_downloads,
                'total_size_mb': user.total_size_mb,
                'member_since': user.created_at,
                'last_active': user.last_active
            }

    async def is_admin(self, user_id: int) -> bool:
        """
        Проверить, является ли пользователь админом.
        Источник истины:
        1) БД: `users.is_admin`
        2) Env fallback: `ADMIN_USER_IDS` (comma-separated)
        """
        admin_ids_raw = os.getenv("ADMIN_USER_IDS", "").strip()
        if admin_ids_raw:
            try:
                admin_ids = {int(x.strip()) for x in admin_ids_raw.split(",") if x.strip()}
                if user_id in admin_ids:
                    return True
            except ValueError:
                # Ignore malformed env
                pass

        async with self.async_session() as session:
            try:
                result = await session.execute(select(User.is_admin).where(User.id == user_id))
                is_admin_val = result.scalar_one_or_none()
                return bool(is_admin_val)
            except Exception as e:
                # If DB schema is older than code (missing column), fail closed.
                print(f"⚠️ Admin check failed for user_id={user_id}: {e}")
                return False

    async def get_users_overview_for_admin(self, limit: int = 100, offset: int = 0):
        """Админ: обзор пользователей (только чтение)."""
        async with self.async_session() as session:
            result = await session.execute(
                select(User)
                .order_by(User.last_active.desc())
                .offset(offset)
                .limit(limit)
            )
            users = result.scalars().all()

            return [
                {
                    "id": u.id,
                    "username": u.username,
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "total_downloads": u.total_downloads,
                    "total_size_mb": u.total_size_mb,
                    "last_active": u.last_active,
                    "is_admin": bool(getattr(u, "is_admin", 0)),
                }
                for u in users
            ]

    async def get_tracks_overview_for_admin(self, limit: int = 100):
        """Админ: обзор треков (только чтение)."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Track).order_by(Track.download_count.desc()).limit(limit)
            )
            tracks = result.scalars().all()

            return [
                {
                    "id": t.id,
                    "name": t.name,
                    "artist": t.artist,
                    "download_count": t.download_count,
                    "spotify_url": t.spotify_url,
                }
                for t in tracks
            ]
    
    # ========== КЭШИРОВАНИЕ (Функция 10) ==========
    
    async def update_track_cache(self, track_id: str, telegram_file_id: str, 
                                 file_format: str = 'mp3', quality: str = '192'):
        """Обновить кэш трека (сохранить telegram_file_id в TrackCache)"""
        async with self.async_session() as session:
            # Сначала проверяем, существует ли основной трек (Foreign Key integrity)
            track_result = await session.execute(select(Track).where(Track.id == track_id))
            track = track_result.scalar_one_or_none()
            
            if not track:
                print(f"⚠️ Cannot update cache: Track {track_id} not found in database!")
                return False

            # Проверяем, есть ли уже такой кэш (чтобы не дублировать)
            result = await session.execute(
                select(TrackCache)
                .where(TrackCache.track_id == track_id)
                .where(TrackCache.file_format == file_format)
                .where(TrackCache.quality == quality)
            )
            cache_entry = result.scalars().first()
            
            if cache_entry:
                cache_entry.telegram_file_id = telegram_file_id
                cache_entry.created_at = datetime.utcnow()
            else:
                cache_entry = TrackCache(
                    track_id=track_id,
                    telegram_file_id=telegram_file_id,
                    file_format=file_format,
                    quality=quality
                )
                session.add(cache_entry)
            
            # Также обновляем время кэширования в основном треке для статистики
            track.telegram_file_id = telegram_file_id # Совместимость со старым кодом
            track.cached_at = datetime.utcnow()

            await session.commit()
            return True
    
    async def get_cached_file_id(self, track_id: str, file_format: str = 'mp3', 
                                 quality: str = '192') -> Optional[str]:
        """Получить telegram_file_id из кэша для конкретного формата и качества"""
        async with self.async_session() as session:
            result = await session.execute(
                select(TrackCache)
                .where(TrackCache.track_id == track_id)
                .where(TrackCache.file_format == file_format)
                .where(TrackCache.quality == quality)
            )
            cache_entry = result.scalars().first()
            
            if cache_entry:
                # Проверяем, не устарел ли кэш (7 дней)
                age = (datetime.utcnow() - cache_entry.created_at).days
                if age < 7:
                    return cache_entry.telegram_file_id
                else:
                    # Удаляем устаревший кэш
                    await session.delete(cache_entry)
                    await session.commit()
            
            return None

    async def get_library_tracks(self, limit: int = 1000) -> List[dict]:
        """Получить все треки, которые есть в Telegram Storage (библиотека канала)"""
        async with self.async_session() as session:
            # Выбираем записи из TelegramFile и объединяем с данными Track
            # Используем dict для гибкости, если данные в Track отсутствуют
            query = (
                select(TelegramFile, Track)
                .join(Track, TelegramFile.track_id == Track.id, isouter=True)
                .order_by(TelegramFile.uploaded_at.desc())
                .limit(limit)
            )
            result = await session.execute(query)
            
            tracks = []
            for tg_file, track in result:
                tracks.append({
                    'id': tg_file.track_id,
                    'name': tg_file.track_name or (track.name if track else "Unknown Track"),
                    'artist': tg_file.artist or (track.artist if track else "Unknown Artist"),
                    'album': track.album if track else None,
                    'image': tg_file.image_url or (track.image_url if track else None),
                    'spotify_url': track.spotify_url if track else f"https://open.spotify.com/track/{tg_file.track_id}",
                    'uploaded_at': tg_file.uploaded_at
                })
            print(f"📊 [DB] get_library_tracks found {len(tracks)} items", flush=True)
            return tracks

    # ========== АУТЕНТИФИКАЦИЯ (WEB) ==========

    async def create_auth_token(self, user_id: int, token: str, expires_in_seconds: Optional[int] = None) -> AuthToken:
        """Создать токен для веб-авторизации (постоянный или временный)"""
        async with self.async_session() as session:
            # Сначала проверяем, есть ли уже токен у этого пользователя
            result = await session.execute(select(AuthToken).where(AuthToken.user_id == user_id).order_by(AuthToken.created_at.desc()))
            existing_token = result.scalars().first()
            
            if existing_token:
                # Если токен не истек, возвращаем его
                if not existing_token.expires_at or existing_token.expires_at > datetime.utcnow():
                    return existing_token
                else:
                    # Удаляем истекший токен
                    await session.delete(existing_token)
                    await session.commit()

            # ГАРАНТИРУЕМ существование пользователя
            user_check = await session.execute(select(User).where(User.id == user_id))
            if not user_check.scalar_one_or_none():
                session.add(User(id=user_id, username="Auth User"))
                await session.flush()

            expires_at = None
            if expires_in_seconds:
                expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds)
            
            new_token = AuthToken(
                token=token,
                user_id=user_id,
                expires_at=expires_at
            )
            session.add(new_token)
            await session.commit()
            return new_token

    async def verify_auth_token(self, token: str) -> Optional[User]:
        """Проверить токен и вернуть пользователя (без удаления токена)"""
        async with self.async_session() as session:
            # Ищем токен, который либо не истек, либо не имеет срока годности
            query = select(AuthToken).where(AuthToken.token == token)
            result = await session.execute(query)
            auth_token = result.scalars().first()
            
            if auth_token:
                # Если у токена есть срок годности, проверяем его
                if auth_token.expires_at and auth_token.expires_at < datetime.utcnow():
                    await session.delete(auth_token)
                    await session.commit()
                    return None
                    
                user_result = await session.execute(select(User).where(User.id == auth_token.user_id))
                user = user_result.scalar_one_or_none()
                
                # Постоянные ссылки НЕ удаляем после использования
                return user
            
            return None
    
    # ========== TELEGRAM STORAGE (Кеширование файлов) ==========
    
    async def save_telegram_file(self, track_id: str, file_id: str, file_path: str = None, 
                                 file_size: int = None, artist: str = None, track_name: str = None,
                                 image_url: str = None) -> TelegramFile:
        """Сохранить file_id в кеш"""
        async with self.async_session() as session:
            # 1. Проверяем по ID
            result = await session.execute(
                select(TelegramFile).where(TelegramFile.track_id == track_id)
            )
            existing = result.scalar_one_or_none()
            
            # 2. ФАЛЛБЭК: Если по ID не нашли, проверяем по Имени и Артисту
            # (Функция deduplication: предотвращает дубликаты если Spotify ID не совпал с ID из Sync)
            if not existing and artist and track_name:
                name_result = await session.execute(
                    select(TelegramFile)
                    .where(func.lower(TelegramFile.artist) == artist.lower())
                    .where(func.lower(TelegramFile.track_name) == track_name.lower())
                )
                existing = name_result.scalar_one_or_none()
                if existing:
                    print(f"🔗 Re-linking track {track_id} to existing file in Storage: {artist} - {track_name}")
            
            if existing:
                # Обновляем существующую запись
                existing.file_id = file_id
                existing.telegram_file_path = file_path
                existing.file_size = file_size
                existing.uploaded_at = datetime.utcnow()
                if artist:
                    existing.artist = artist
                if track_name:
                    existing.track_name = track_name
                if image_url:
                    existing.image_url = image_url
                await session.commit()
                return existing
            else:
                # ГАРАНТИРУЕМ, ЧТО ТРЕК ЕСТЬ В БД (Foreign Key integrity)
                track_result = await session.execute(select(Track).where(Track.id == track_id))
                track = track_result.scalar_one_or_none()
                
                if not track:
                    # НОВОЕ: Перед созданием "минимальной" записи, пробуем найти трек по Имени/Артисту
                    # Это позволяет привязать файл из Sync к существующим богатым метаданным Spotify
                    if artist and track_name:
                        track_name_result = await session.execute(
                            select(Track)
                            .where(func.lower(Track.artist) == artist.lower())
                            .where(func.lower(Track.name) == track_name.lower())
                            .limit(1)
                        )
                        track = track_name_result.scalar_one_or_none()
                        
                        if track:
                            # Мы нашли существующий трек с метаданными! 
                            # Перенаправляем track_id на реальный Spotify ID для этой записи
                            print(f"🔗 Linked synced file {file_id} to existing Spotify track: {track.id} ({artist} - {track_name})")
                            track_id = track.id
                    
                if not track:
                    # Если трека все еще нет, создаем минимальную запись чтобы не упасть по Foreign Key
                    # Это происходит для треков, которых НЕТ в кэше Spotify поиска
                    print(f"⚠️ Track {track_id} not found during file save. Creating minimal record.")
                    track = Track(
                        id=track_id,
                        name=track_name or "Unknown Track",
                        artist=artist or "Unknown Artist",
                        spotify_url=f"https://open.spotify.com/track/{track_id}"  # Required field
                    )
                    session.add(track)
                    # flush чтобы SQLAlchemy увидел трек перед вставкой файла
                    await session.flush()

                # Создаем новую запись
                telegram_file = TelegramFile(
                    track_id=track_id,
                    file_id=file_id,
                    telegram_file_path=file_path,
                    file_size=file_size,
                    artist=artist,
                    track_name=track_name,
                    image_url=image_url
                )
                session.add(telegram_file)
                await session.commit()
                return telegram_file
    
    async def get_telegram_file(self, track_id: str) -> Optional[TelegramFile]:
        """Получить file_id из кеша"""
        async with self.async_session() as session:
            result = await session.execute(
                select(TelegramFile).where(TelegramFile.track_id == track_id)
            )
            return result.scalar_one_or_none()
    
    async def is_telegram_file_cached(self, track_id: str) -> bool:
        """Проверить, есть ли файл в Telegram Storage"""
        telegram_file = await self.get_telegram_file(track_id)
        return telegram_file is not None

    async def get_telegram_file_by_name(self, artist: str, track_name: str) -> Optional[TelegramFile]:
        """Найти файл в Telegram по имени артиста и названию"""
        async with self.async_session() as session:
            result = await session.execute(
                select(TelegramFile)
                .where(func.lower(TelegramFile.artist) == artist.lower())
                .where(func.lower(TelegramFile.track_name) == track_name.lower())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def search_telegram_files(self, query: str, limit: int = 10) -> List[dict]:
        """Поиск файлов в Telegram Storage (Discover) по артисту или названию"""
        async with self.async_session() as session:
            from sqlalchemy import or_
            result = await session.execute(
                select(TelegramFile, Track)
                .join(Track, TelegramFile.track_id == Track.id, isouter=True)
                .where(
                    or_(
                        TelegramFile.artist.ilike(f"%{query}%"),
                        TelegramFile.track_name.ilike(f"%{query}%")
                    )
                )
                .limit(limit)
            )
            
            tracks = []
            for tg_file, track in result:
                tracks.append({
                    'id': tg_file.track_id,
                    'name': tg_file.track_name or (track.name if track else "Unknown Track"),
                    'artist': tg_file.artist or (track.artist if track else "Unknown Artist"),
                    'album': track.album if track else None,
                    'image': tg_file.image_url or (track.image_url if track else None),
                    'spotify_url': track.spotify_url if track else f"https://open.spotify.com/track/{tg_file.track_id}",
                    'from_discover': True
                })
            return tracks

    # ========== BACKUP LOGS ==========
    
    async def save_backup_log(self, message_id: int, file_id: str) -> BackupLog:
        """Сохранить лог бэкапа"""
        async with self.async_session() as session:
            log = BackupLog(
                message_id=message_id,
                file_id=file_id
            )
            session.add(log)
            await session.commit()
            return log
            
    async def get_backup_logs(self, limit: int = 10) -> List[BackupLog]:
        """Получить последние логи бэкапов"""
        async with self.async_session() as session:
            result = await session.execute(
                select(BackupLog).order_by(BackupLog.created_at.desc()).limit(limit)
            )
            return list(result.scalars().all())

    async def delete_backup_log(self, message_id: int):
        """Удалить лог бэкапа"""
        async with self.async_session() as session:
            await session.execute(
                delete(BackupLog).where(BackupLog.message_id == message_id)
            )
            await session.commit()
