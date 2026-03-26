# Используем официальный Python образ
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app
ENV PYTHONUNBUFFERED=1

# Устанавливаем системные зависимости для ffmpeg и Node.js (для yt-dlp)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    nodejs \
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
