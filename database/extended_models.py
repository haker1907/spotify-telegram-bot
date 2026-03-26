"""
Новые модели для расширенного функционала
"""
from datetime import datetime
from sqlalchemy import BigInteger, String, Integer, DateTime, ForeignKey, Text, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .models import Base


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
    file_size_mb: Mapped[float] = mapped_column(Integer, default=0)  # Размер файла
    
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
