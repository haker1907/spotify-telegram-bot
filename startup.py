import sys
import os
import time
import signal
import asyncio

# Ensure project root is in path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Force unbuffered output for all prints
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

import config
from database.db_manager import DatabaseManager

async def pre_startup_db_init():
    """
    Централизованная инициализация БД перед запуском всех сервисов.
    Включает retry-логику для работы в нестабильных сетевых условиях при старте контейнера.
    """
    print("=" * 80, flush=True)
    print("🏗️  PRE-STARTUP DATABASE INITIALIZATION: Starting...", flush=True)
    print("=" * 80, flush=True)
    
    # 0. Даем сети 10 секунд чтобы "ожить" (актуально для контейнеров)
    print("⏳ Waiting 10s for network interface to settle...", flush=True)
    await asyncio.sleep(10)
    
    max_retries = 5
    retry_delay = 5
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"📦 [INIT] Attempt {attempt}/{max_retries} to initialize database...", flush=True)
            db = DatabaseManager()
            
            # 1. Восстановление из Telegram
            print("📦 [INIT] Checking for database restoration from Telegram...", flush=True)
            from services.telegram_storage_service import TelegramStorageService
            from services.db_backup_service import DatabaseBackupService
            
            storage = TelegramStorageService()
            db_path = config.DATABASE_URL.replace('sqlite+aiosqlite:///', '')
            backup_service = DatabaseBackupService(storage_service=storage, db_path=db_path, db_manager=db)
            
            restored = await backup_service.restore_from_telegram()
            if restored:
                print("🔄 [INIT] Database restored! Refreshing engine...", flush=True)
                await db.reconnect()
            else:
                print("ℹ️  [INIT] No backup found or restore skipped.", flush=True)
                
            # 2. Инициализация схемы и WAL mode
            print("📦 [INIT] Ensuring database schema and WAL mode...", flush=True)
            await db.init_db()
            
            # Закрываем соединение, так как воркеры откроют свои
            await db.close()
            
            print("✅ [INIT] Database is READY for services.", flush=True)
            print("=" * 80, flush=True)
            return True
            
        except Exception as e:
            print(f"❌ [INIT] Attempt {attempt} failed: {e}", flush=True)
            if attempt < max_retries:
                print(f"⏳ Retrying in {retry_delay} seconds...", flush=True)
                await asyncio.sleep(retry_delay)
            else:
                import traceback
                traceback.print_exc()
                return False

def main():
    print("🚀 Starting Spotify Telegram Bot system...", flush=True)

    # Set environment variables if needed
    env = os.environ.copy()
    
    # Processes list
    processes = []

    try:
        # 0. Инициализация БД перед запуском всех сервисов
        success = asyncio.run(pre_startup_db_init())
        if not success:
            print("⚠️  Warning: Pre-startup database initialization failed. Continuing...", flush=True)
        else:
            print("✅ Pre-startup DB init finished successfully!", flush=True)

        # Enable unbuffered output for the web process
        web_env = env.copy()
        web_env['PYTHONUNBUFFERED'] = '1'
        port = env.get('PORT', '5000')
        
        print(f"🔗 Starting Web Interface (Gunicorn) on port {port}...", flush=True)
        import subprocess
        web_process = subprocess.Popen(
            ["gunicorn", "--bind", f"0.0.0.0:{port}", "--workers", "1", "--timeout", "120", "web.app:app"],
            env=web_env,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        processes.append(web_process)

        # 2. Start Telegram Bot with delay to prevent Conflict (terminated by other getUpdates)
        # Give Railway time to stop the old container
        print("🤖 Starting Telegram Bot in 30 seconds to prevent conflicts...", flush=True)
        bot_process = subprocess.Popen(
            [sys.executable, "-c", "import time; print('⏳ Waiting for old instances...', flush=True); time.sleep(30); import subprocess, sys; subprocess.run([sys.executable, 'bot.py'])"],
            env=env,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        processes.append(bot_process)

        print("✅ All processes started. Monitoring...", flush=True)

        # Monitor processes
        while True:
            for p in processes:
                if p.poll() is not None:
                    print(f"❌ Process exited with code {p.returncode}", flush=True)
                    # If one process dies, we exit to let Railway restart the container
                    return p.returncode
            time.sleep(10)

    except KeyboardInterrupt:
        print("\n👋 Stopping system...", flush=True)
        for p in processes:
            p.terminate()
        return 0
    except Exception as e:
        print(f"❌ Startup error: {e}", flush=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
