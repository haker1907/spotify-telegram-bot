# Spotify Telegram Bot

🎵 Telegram бот для скачивания музыки из Spotify без API ключей

## Возможности

- 🎧 Скачивание треков из Spotify
- 📁 Создание и управление плейлистами
- 🔄 Кэширование файлов для быстрой повторной отправки
- 🎚️ Выбор качества (MP3: 128/192/320 kbps, FLAC: 1411/2300/4600/9200 kbps)
- 🌍 Поддержка русского и английского языков
- 📊 История скачиваний

## Технологии

- Python 3.10+
- python-telegram-bot
- yt-dlp
- SQLite
- FFmpeg

## Установка локально

```bash
# Клонируйте репозиторий
git clone https://github.com/ВАШ_USERNAME/spotify-telegram-bot.git
cd spotify-telegram-bot

# Установите зависимости
pip install -r requirements.txt

# Создайте .env файл
echo "TELEGRAM_BOT_TOKEN=ваш_токен" > .env

# Запустите бота
python bot.py
```

## Деплой на Railway.app

См. [railway_deployment.md](railway_deployment.md) для подробной инструкции.

## Переменные окружения
- `TELEGRAM_BOT_TOKEN` - токен вашего Telegram бота (обязательно)

### Web / авторизация
- `WEB_APP_URL` - URL веб-приложения (например, `https://your-domain.up.railway.app`)
- `WEB_ALLOWED_ORIGINS` - origin(ы) для CORS (через запятую)
- `WEB_SESSION_SECRET` - секрет для подписи JWT-сессии (замените `change-me`)
- `WEB_SESSION_TTL` - срок жизни JWT-сессии в секундах (по умолчанию 30 дней)

### База данных
- `DATABASE_URL` - строка подключения (по умолчанию SQLite: `data/spotify_bot.db`)

### Telegram Storage / backups
- `STORAGE_CHANNEL_ID` - ID канала/группы, где хранятся файлы

### YouTube cookies (для yt-dlp)
- `YOUTUBE_COOKIES_BASE64` - base64 от файла `cookies.txt` в формате Netscape (используется для `yt-dlp`)

Если появляются ошибки вида `Sign in to confirm you’re not a bot`, обновите cookies:
- В браузере откройте `youtube.com` и убедитесь, что вы залогинены.
- Экспортируйте cookies в формате Netscape (`cookies.txt`) для `youtube.com`.
- Преобразуйте `cookies.txt` в base64 и задайте переменную `YOUTUBE_COOKIES_BASE64` в Railway (одно значение, без переносов).
- Сделайте redeploy после обновления cookies.

#### Быстрый runbook (Windows + Railway)
1. Откройте Firefox, зайдите в `youtube.com` под нужным аккаунтом, затем закройте Firefox.
2. В корне проекта выполните:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\rotate_cookies.ps1
   ```
3. Скопируйте выведенное значение и вставьте в Railway env: `YOUTUBE_COOKIES_BASE64`.
4. Перезапустите сервис (redeploy).

> Почему Firefox: Chrome 127+ использует app-bound encryption, поэтому внешние скрипты/библиотеки часто не могут стабильно извлекать cookies.

### Rate limits (in-memory)
- `DOWNLOAD_RATE_LIMIT`, `DOWNLOAD_RATE_PERIOD_SECONDS`
- `PREPARE_STREAM_RATE_LIMIT`, `PREPARE_STREAM_RATE_PERIOD_SECONDS`
- `SYNC_RATE_LIMIT`, `SYNC_RATE_PERIOD_SECONDS`
- `BACKUP_RATE_LIMIT`, `BACKUP_RATE_PERIOD_SECONDS`

## Вход в веб-интерфейс
В Telegram выполните команду `/login` — бот даст персональную ссылку.
Откройте ссылку в браузере: веб-приложение создаст JWT-сессию и начнет работу.

## Лицензия

MIT
