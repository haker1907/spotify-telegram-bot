# Используем официальный Python образ
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app
ENV PYTHONUNBUFFERED=1

# ffmpeg для конвертации аудио; --no-install-recommends ускоряет сборку и уменьшает образ
# Node.js не нужен yt-dlp для типичного YouTube; при необходимости верните: nodejs
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаем директории для данных и устанавливаем права
RUN mkdir -p downloads data && chmod -R 777 downloads data

# Запускаем систему через Python-стартер (Бот + Веб)
CMD ["python", "startup.py"]
