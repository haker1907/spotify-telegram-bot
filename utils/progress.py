"""
Утилиты для отображения прогресса (Функция 6)
"""


def create_progress_bar(current: int, total: int, length: int = 10) -> str:
    """
    Создать прогресс-бар
    
    Args:
        current: Текущее значение
        total: Общее значение
        length: Длина прогресс-бара в символах
    
    Returns:
        Строка с прогресс-баром, например: [████████░░] 80%
    """
    if total == 0:
        return f"[{'░' * length}] 0%"
    
    filled = int(length * current / total)
    bar = '█' * filled + '░' * (length - filled)
    percent = int(100 * current / total)
    return f"[{bar}] {percent}%"


def format_time(seconds: int) -> str:
    """
    Форматировать время в читаемый вид
    
    Args:
        seconds: Количество секунд
    
    Returns:
        Строка вида "1:23" или "12:34"
    """
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def format_file_size(size_bytes: int) -> str:
    """
    Форматировать размер файла
    
    Args:
        size_bytes: Размер в байтах
    
    Returns:
        Строка вида "3.5 MB" или "1.2 GB"
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def create_download_progress_message(
    track_name: str,
    current: int,
    total: int,
    status: str = "Скачивание"
) -> str:
    """
    Создать сообщение о прогрессе скачивания
    
    Args:
        track_name: Название трека
        current: Текущий трек
        total: Всего треков
        status: Статус (Скачивание, Конвертация и т.д.)
    
    Returns:
        Форматированное сообщение
    """
    progress_bar = create_progress_bar(current, total)
    
    message = f"""
⏳ <b>{status}...</b>

🎵 {track_name}

{progress_bar}
Трек {current} из {total}
"""
    return message.strip()
