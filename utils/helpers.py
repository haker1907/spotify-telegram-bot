"""
Вспомогательные функции
"""
import re
from typing import Optional
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def format_duration(duration_ms: int) -> str:
    """
    Форматирование длительности из миллисекунд в MM:SS
    
    Args:
        duration_ms: Длительность в миллисекундах
    
    Returns:
        Строка формата "MM:SS"
    """
    if not duration_ms:
        return "0:00"
    
    seconds = duration_ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"


def validate_spotify_url(url: str) -> bool:
    """
    Проверка, является ли URL ссылкой на Spotify
    
    Args:
        url: URL для проверки
    
    Returns:
        True если это Spotify URL, иначе False
    """
    spotify_pattern = r'(https?://)?(open\.)?spotify\.com/(track|album|playlist)/[a-zA-Z0-9]+'
    return bool(re.match(spotify_pattern, url))


def extract_spotify_id(url: str) -> Optional[str]:
    """
    Извлечение Spotify ID из URL
    
    Args:
        url: Spotify URL
    
    Returns:
        Spotify ID или None
    """
    pattern = r'spotify\.com/(?:track|album|playlist)/([a-zA-Z0-9]+)'
    match = re.search(pattern, url)
    return match.group(1) if match else None


def error_handler(func):
    """
    Декоратор для обработки ошибок в обработчиках
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Ошибка в {func.__name__}: {e}", exc_info=True)
            # Можно добавить отправку сообщения пользователю об ошибке
            raise
    return wrapper


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Обрезать текст до указанной длины
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина
        suffix: Суффикс для добавления в конец
    
    Returns:
        Обрезанный текст
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def escape_markdown(text: str) -> str:
    """
    Экранирование специальных символов для Markdown
    
    Args:
        text: Исходный текст
    
    Returns:
        Экранированный текст
    """
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text
