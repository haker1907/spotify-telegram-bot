"""
Модели базы данных SQLAlchemy
"""
from datetime import datetime
from sqlalchemy import BigInteger, String, Integer, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import List, Optional


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""
    pass


class User(Base):
    """Модель пользователя Telegram"""
    __tablename__ = 'users'
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user ID
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Настройки (Функция 3, 18)
    preferred_quality: Mapped[str] = mapped_column(String(10), default='192')  # 128, 192, 320
    language: Mapped[str] = mapped_column(String(5), default='ru')  # ru, en
    auto_delete: Mapped[bool] = mapped_column(Integer, default=0)  # SQLite не поддерживает Boolean
    format: Mapped[str] = mapped_column(String(10), default='mp3')  # mp3, flac
    notifications: Mapped[bool] = mapped_column(Integer, default=1)
    is_admin: Mapped[int] = mapped_column(Integer, default=0)  # 0/1, SQLite-friendly
    
    # Статистика (Функция 9)
    total_downloads: Mapped[int] = mapped_column(Integer, default=0)
    total_size_mb: Mapped[float] = mapped_column(Integer, default=0)  # Используем Integer для SQLite
    referred_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    referrals_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Связи
    playlists: Mapped[List["Playlist"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    download_history: Mapped[List["DownloadHistory"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    favorites: Mapped[List["Favorite"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    auth_tokens: Mapped[List["AuthToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"


class Playlist(Base):
    """Модель плейлиста пользователя"""
    __tablename__ = 'playlists'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    user: Mapped["User"] = relationship(back_populates="playlists")
    playlist_tracks: Mapped[List["PlaylistTrack"]] = relationship(back_populates="playlist", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Playlist(id={self.id}, name={self.name}, user_id={self.user_id})>"


class Track(Base):
    """Модель трека Spotify (кэш)"""
    __tablename__ = 'tracks'
    
    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # Spotify track ID
    name: Mapped[str] = mapped_column(String(500))
    artist: Mapped[str] = mapped_column(String(500))
    album: Mapped[str] = mapped_column(String(500), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    preview_url: Mapped[str] = mapped_column(String(500), nullable=True)
    spotify_url: Mapped[str] = mapped_column(String(500))
    image_url: Mapped[str] = mapped_column(String(500), nullable=True)
    popularity: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Кэширование (Функция 10)
    telegram_file_id: Mapped[str] = mapped_column(String(500), nullable=True)  # Для кэша
    cached_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0)  # Для статистики
    
    # Связи
    playlist_tracks: Mapped[List["PlaylistTrack"]] = relationship(back_populates="track", cascade="all, delete-orphan")
    download_history: Mapped[List["DownloadHistory"]] = relationship(back_populates="track", cascade="all, delete-orphan")
    favorites: Mapped[List["Favorite"]] = relationship(back_populates="track", cascade="all, delete-orphan")
    telegram_files: Mapped[List["TelegramFile"]] = relationship(back_populates="track", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Track(id={self.id}, name={self.name}, artist={self.artist})>"


class PlaylistTrack(Base):
    """Связь многие-ко-многим между плейлистами и треками"""
    __tablename__ = 'playlist_tracks'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    playlist_id: Mapped[int] = mapped_column(Integer, ForeignKey('playlists.id', ondelete='CASCADE'))
    track_id: Mapped[str] = mapped_column(String(255), ForeignKey('tracks.id', ondelete='CASCADE'))
    position: Mapped[int] = mapped_column(Integer, default=0)  # Порядок в плейлисте
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связи
    playlist: Mapped["Playlist"] = relationship(back_populates="playlist_tracks")
    track: Mapped["Track"] = relationship(back_populates="playlist_tracks")
    
    def __repr__(self):
        return f"<PlaylistTrack(playlist_id={self.playlist_id}, track_id={self.track_id})>"


class Album(Base):
    """Модель альбома Spotify (Функция 1)"""
    __tablename__ = 'albums'
    
    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # Spotify album ID
    name: Mapped[str] = mapped_column(String(500))
    artist: Mapped[str] = mapped_column(String(500))
    image_url: Mapped[str] = mapped_column(String(500), nullable=True)
    total_tracks: Mapped[int] = mapped_column(Integer)
    spotify_url: Mapped[str] = mapped_column(String(500))
    release_date: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Album(id={self.id}, name={self.name}, artist={self.artist})>"


class DownloadHistory(Base):
    """История скачиваний (Функция 5)"""
    __tablename__ = 'download_history'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'))
    track_id: Mapped[str] = mapped_column(String(255), ForeignKey('tracks.id', ondelete='CASCADE'))
    downloaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    quality: Mapped[str] = mapped_column(String(10), default='192')  # Качество скачивания
    file_size_mb: Mapped[int] = mapped_column(Integer, default=0)  # Размер файла
    
    # Связи
    user: Mapped["User"] = relationship(back_populates="download_history")
    track: Mapped["Track"] = relationship(back_populates="download_history")
    
    def __repr__(self):
        return f"<DownloadHistory(user_id={self.user_id}, track_id={self.track_id})>"


class Favorite(Base):
    """Избранные треки (Функция 8)"""
    __tablename__ = 'favorites'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'))
    track_id: Mapped[str] = mapped_column(String(255), ForeignKey('tracks.id', ondelete='CASCADE'))
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связи
    user: Mapped["User"] = relationship(back_populates="favorites")
    track: Mapped["Track"] = relationship(back_populates="favorites")
    
    def __repr__(self):
        return f"<Favorite(user_id={self.user_id}, track_id={self.track_id})>"
class TrackCache(Base):
    """Таблица для кэширования аудиофайлов разных форматов и качеств"""
    __tablename__ = 'track_cache'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    track_id: Mapped[str] = mapped_column(String(255), ForeignKey('tracks.id', ondelete='CASCADE'))
    telegram_file_id: Mapped[str] = mapped_column(String(500))
    file_format: Mapped[str] = mapped_column(String(10))  # mp3, flac
    quality: Mapped[str] = mapped_column(String(10))     # 128, 320, 1411, 9200 etc
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связи
    track: Mapped["Track"] = relationship(back_populates="caches")
    
    def __repr__(self):
        return f"<TrackCache(track_id={self.track_id}, format={self.file_format}, quality={self.quality})>"


# Обновляем Track для связи с TrackCache
Track.caches = relationship("TrackCache", back_populates="track", cascade="all, delete-orphan")


class AuthToken(Base):
    """Модель для временных токенов авторизации"""
    __tablename__ = 'auth_tokens'
    
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связь с пользователем
    user: Mapped["User"] = relationship("User", back_populates="auth_tokens")
    
    def __repr__(self):
        return f"<AuthToken(user_id={self.user_id}, expires={self.expires_at})>"

class TelegramFile(Base):
    """Модель для кеширования файлов в Telegram Storage"""
    __tablename__ = 'telegram_files'
    
    track_id: Mapped[str] = mapped_column(String(255), ForeignKey('tracks.id', ondelete='CASCADE'), primary_key=True)
    file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Метаданные трека для удобства
    artist: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    track_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Связи
    track: Mapped["Track"] = relationship(back_populates="telegram_files")

    def __repr__(self):
        return f"<TelegramFile(track_id={self.track_id}, file_id={self.file_id})>"


class BackupLog(Base):
    """Лог бэкапов БД в Telegram Channel"""
    __tablename__ = 'backup_logs'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<BackupLog(id={self.id}, message_id={self.message_id})>"


class AdminAuditLog(Base):
    """Логи действий админа"""
    __tablename__ = 'admin_audit_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AdminAuditLog(action={self.action}, admin={self.admin_user_id})>"


class PublicSpotifyPlaylist(Base):
    """Глобальный каталог Spotify-плейлистов, добавленных пользователями."""
    __tablename__ = "public_spotify_playlists"

    spotify_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    spotify_url: Mapped[str] = mapped_column(String(500))
    total_tracks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    added_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_cached_public: Mapped[int] = mapped_column(Integer, default=0)  # 0/1: треки плейлиста прогреты в Telegram Storage
    cached_tracks_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cached_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<PublicSpotifyPlaylist(spotify_id={self.spotify_id}, name={self.name})>"


class UserSpotifyPlaylist(Base):
    """Личный список сохранённых Spotify-плейлистов пользователя (по playlist_id)."""
    __tablename__ = "user_spotify_playlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    spotify_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    spotify_url: Mapped[str] = mapped_column(String(500))
    total_tracks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<UserSpotifyPlaylist(user_id={self.user_id}, spotify_id={self.spotify_id})>"


Index("ix_track_cache_track_format_quality", TrackCache.track_id, TrackCache.file_format, TrackCache.quality)
Index("ix_download_history_user_downloaded", DownloadHistory.user_id, DownloadHistory.downloaded_at)
Index("ix_telegram_files_artist_track", TelegramFile.artist, TelegramFile.track_name)
Index("ix_tracks_download_count", Track.download_count)
Index("ix_public_spotify_playlists_updated", PublicSpotifyPlaylist.updated_at)
Index("ix_user_spotify_playlists_user_spotify", UserSpotifyPlaylist.user_id, UserSpotifyPlaylist.spotify_id, unique=True)
