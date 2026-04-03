"""
Database Backup Service - автоматический backup и восстановление БД через Telegram
"""
import os
import asyncio
import shutil
from datetime import datetime
from typing import Optional
import httpx


class DatabaseBackupService:
    """Сервис для backup и восстановления БД через Telegram Storage"""
    
    def __init__(self, storage_service, db_path: Optional[str], db_manager=None):
        """
        Args:
            storage_service: TelegramStorageService instance
            db_path: Путь к файлу БД (например, 'spotify_bot.db') для SQLite. Для других СУБД может быть None.
            db_manager: DatabaseManager instance for persistent logging
        """
        self.storage = storage_service
        self.db_path = db_path
        self.db = db_manager
        self.backup_file_id = None
        self.is_running = False
        self.backup_message_ids = []  # Список message_id созданных в сессии
        self.last_backup_time = datetime.min # Для троттлинга
        
        if not self.db_path:
            print("⚠️ Database Backup Service disabled: DATABASE_URL is not SQLite file-based.")
            self.backup_file_id = None
            self.is_running = False
            self.backup_message_ids = []
            self.last_backup_time = datetime.min
        else:
            print(f"📦 Database Backup Service initialized for: {db_path}")
    
    async def restore_from_telegram(self) -> bool:
        """
        Восстановить БД из Telegram при старте приложения
        
        Returns:
            True если БД успешно восстановлена, False если backup не найден
        """
        try:
            if not self.db_path:
                return False
            print("🔍 Checking for latest backup in Telegram pinned message...")
            backup_info = await self._find_latest_backup()
            
            if not backup_info:
                print("ℹ️  No backup found in Telegram, using local database (if exists)")
                return False
            
            # Если локальный файл существует, проверим, нужно ли его заменять
            if os.path.exists(self.db_path):
                local_size = os.path.getsize(self.db_path)
                backup_size = backup_info.get('file_size', 0)
                local_mtime = os.path.getmtime(self.db_path)

                # Telegram pinned message contains `date` (unix timestamp). Если backup pinned документ
                # обновился позже локального файла, то игнорируем локальные "skip" условия и всегда восстанавливаем.
                backup_date = backup_info.get('date')
                backup_is_newer = False
                if backup_date is not None:
                    try:
                        backup_ts = float(backup_date)
                        backup_is_newer = backup_ts > (local_mtime + 1)
                    except (TypeError, ValueError):
                        backup_is_newer = False
                
                # Проверяем, пуста ли библиотека в текущей БД
                is_empty = False
                if self.db:
                    try:
                        is_empty = await self.db.is_library_empty()
                    except Exception as e:
                         print(f"⚠️ Error checking library state: {e}")
                
                # Если библиотека пуста (результат деплоя), или файл подозрительно маленький
                if is_empty:
                    print(f"⚠️  Local library is EMPTY. Forcing restoration from Telegram...")
                elif local_size < 32768: # 32KB - это примерно пустая БД со схемой
                    print(f"⚠️  Local database is too small ({local_size} bytes), overwriting with backup...")
                elif backup_size > local_size + 1024: # Если бэкап больше хотя бы на 1KB
                    print(f"🔄 Backup in Telegram ({backup_size} bytes) is larger than local DB ({local_size} bytes). Restoring...")
                else:
                    if not backup_is_newer:
                        print(f"✅ Local database exists and has data. Skipping restoration.")
                        return False
                    print(f"🔄 Backup pinned is newer than local file. Overwriting local DB...")
            
            # Скачиваем backup
            print(f"📥 Downloading database backup from Telegram...")
            success = await self._download_backup(backup_info['file_id'])
            
            if success:
                print("✅ Database successfully restored from Telegram!")
                self.backup_file_id = backup_info['file_id']
                return True
            else:
                print("❌ Failed to restore database from Telegram")
                return False
                
        except Exception as e:
            print(f"❌ Error restoring database: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def backup_to_telegram(self, force: bool = False) -> bool:
        """
        Создать backup БД в Telegram
        
        Args:
            force: Игнорировать троттлинг (например, при выключении)
        
        Returns:
            True если backup успешно создан
        """
        try:
            if not self.db_path:
                print("⚠️ Backup skipped: db_path is not set (non-sqlite mode)")
                return False
            # Троттлинг: не чаще чем раз в 15 секунд (если не force)
            if not force:
                elapsed = (datetime.now() - self.last_backup_time).total_seconds()
                if elapsed < 15:
                    print(f"⏳ Backup skipped (throttling: last backup {elapsed:.1f}s ago)")
                    return False

            if not os.path.exists(self.db_path):
                print(f"⚠️  Database file not found: {self.db_path}")
                return False
            
            file_size = os.path.getsize(self.db_path)
            print(f"💾 Creating database backup ({file_size / 1024:.2f} KB)...")
            
            # Загружаем БД как document в Telegram
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            caption = f"🗄️ Database Backup - {timestamp}"
            
            result = self.storage.upload_document(self.db_path, caption)
            
            if result and result.get('file_id'):
                self.backup_file_id = result['file_id']
                print(f"✅ Database backup created: {result['file_id'][:20]}...")
                
                # Закрепляем сообщение, чтобы бот всегда мог его найти
                if result.get('message_id'):
                    pin_success = self.storage.pin_message(result['message_id'])
                    if pin_success:
                        print(f"📌 Backup message pinned: {result['message_id']}")

                        # Проверяем, что закрепленный документ действительно соответствует новому бэкапу.
                        # На некоторых Telegram API/edge случаях закрепление может сработать не мгновенно.
                        try:
                            pinned = self.storage.get_pinned_message()
                            pinned_doc = (pinned or {}).get('document') or {}
                            pinned_file_id = pinned_doc.get('file_id')

                            if pinned_file_id and pinned_file_id != result['file_id']:
                                print("⚠️ Pinned document mismatch. Re-pin attempt...")
                                for _ in range(3):
                                    await asyncio.sleep(1)
                                    self.storage.pin_message(result['message_id'])
                                    pinned = self.storage.get_pinned_message()
                                    pinned_doc = (pinned or {}).get('document') or {}
                                    pinned_file_id = pinned_doc.get('file_id')
                                    if pinned_file_id == result['file_id']:
                                        print("✅ Pinned document matches new backup after retry")
                                        break
                        except Exception as e:
                            print(f"⚠️ Pinned verification failed: {e}")
                        
                        # Удаляем сервисное сообщение "Сообщение закреплено" (оно обычно идет следующим за закрепом)
                        service_msg_id = result['message_id'] + 1
                        self.storage.delete_message(service_msg_id)
                    
                    # Сохраняем message_id бэкапа для безопасного удаления
                    self.backup_message_ids.append(result['message_id'])
                    
                    # Сохраняем в БД для надежности (Функция 3 - персистентность)
                    if self.db:
                        await self.db.save_backup_log(result['message_id'], result['file_id'])
                
                # Автоматическая очистка старых бэкапов (БЕЗОПАСНО - удаляет только отслеживаемые message_id)
                await self.cleanup_old_backups(keep_count=2)
                
                # Обновляем время последнего бэкапа
                self.last_backup_time = datetime.now()
                
                return True
            else:
                print("❌ Failed to create database backup")
                return False
                
        except Exception as e:
            print(f"❌ Error creating backup: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def start_periodic_backup(self, interval: int = 300):
        """
        Запустить периодический backup БД
        
        Args:
            interval: Интервал в секундах (по умолчанию 300 = 5 минут)
        """
        self.is_running = True
        print(f"⏰ Starting periodic database backup (every {interval} seconds)...")
        
        while self.is_running:
            try:
                await asyncio.sleep(interval)
                
                if self.is_running:
                    await self.backup_to_telegram()
                    
            except asyncio.CancelledError:
                print("🛑 Periodic backup cancelled")
                break
            except Exception as e:
                print(f"❌ Error in periodic backup: {e}")
                # Продолжаем работу даже при ошибке
                continue
    
    def stop_periodic_backup(self):
        """Остановить периодический backup"""
        print("🛑 Stopping periodic database backup...")
        self.is_running = False
    
    async def _find_latest_backup(self) -> Optional[dict]:
        """
        Найти последний backup БД в Telegram канале
        
        Returns:
            Dict с информацией о backup или None
        """
        try:
            # 1. Сначала пробуем закрепленное сообщение (самый быстрый и надежный способ)
            message = self.storage.get_pinned_message()
            
            if message and message.get('document'):
                doc = message['document']
                if doc.get('file_name', '').endswith('.db'):
                    print(f"✅ Found backup in pinned message: {doc.get('file_name')}")
                    return {
                        'file_id': doc['file_id'],
                        'file_name': doc.get('file_name'),
                        'file_size': doc.get('file_size'),
                        'date': message.get('date')
                    }
            
            # 2. ФАЛЛБЭК: Если закрепа нет, поищем в последних сообщениях чрез DeepSync-подобный механизм
            print("🔍 No valid backup in pinned message. Scanning last 100 messages for backups...")
            
            # Нам нужно получить текущий ID головы канала
            head_id = 0
            try:
                # Отправляем и удаляем сообщение чтобы узнать текущий ID
                resp = httpx.post(f"{self.storage.base_url}/sendMessage", data={
                    'chat_id': self.storage.channel_id,
                    'text': '🔍 Backup Search Probe'
                })
                if resp.status_code == 200:
                    msg = resp.json().get('result', {})
                    head_id = msg.get('message_id', 0)
                    httpx.post(f"{self.storage.base_url}/deleteMessage", data={
                        'chat_id': self.storage.channel_id,
                        'message_id': head_id
                    })
            except:
                pass
            
            if head_id > 0:
                # Сканируем назад
                for msg_id in range(head_id, max(0, head_id - 100), -1):
                    # Используем forwardMessage для проверки содержимого (трюк DeepSync)
                    try:
                        # Получаем ID бота для форварда самому себе
                        bot_info = httpx.get(f"{self.storage.base_url}/getMe").json()
                        bot_id = bot_info.get('result', {}).get('id')
                        
                        resp = httpx.post(f"{self.storage.base_url}/forwardMessage", data={
                            'chat_id': bot_id,
                            'from_chat_id': self.storage.channel_id,
                            'message_id': msg_id,
                            'disable_notification': True
                        })
                        
                        if resp.status_code == 200:
                            msg_data = resp.json().get('result', {})
                            doc = msg_data.get('document')
                            if doc and doc.get('file_name', '').endswith('.db'):
                                print(f"✅ Found backup via scan at message {msg_id}: {doc['file_name']}")
                                return {
                                    'file_id': doc['file_id'],
                                    'file_name': doc['file_name'],
                                    'file_size': doc.get('file_size'),
                                    'date': msg_data.get('date')
                                }
                    except:
                        continue
            
            print("ℹ️  No database backup found in Telegram storage")
            return None
            
        except Exception as e:
            print(f"❌ Error finding backup: {e}")
            return None
    
    async def _download_backup(self, file_id: str) -> bool:
        """
        Скачать backup из Telegram
        
        Args:
            file_id: ID файла в Telegram
            
        Returns:
            True если успешно скачан
        """
        try:
            # Создаем временный файл для backup
            temp_path = f"{self.db_path}.backup"
            
            # Скачиваем файл
            success = self.storage.download_file(file_id, temp_path)
            
            if success and os.path.exists(temp_path):
                # Заменяем текущую БД на backup
                if os.path.exists(self.db_path):
                    os.remove(self.db_path)
                
                # Создаем директорию если её нет
                os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
                
                shutil.move(temp_path, self.db_path)
                
                # Явно устанавливаем права на запись (chmod 666)
                try:
                    os.chmod(self.db_path, 0o666)
                except Exception as chmod_e:
                    print(f"⚠️  Warning: Could not set permissions: {chmod_e}")
                
                print(f"✅ Database file restored and permissions set: {self.db_path}")
                return True
            else:
                print("❌ Failed to download backup file")
                return False
                
        except Exception as e:
            print(f"❌ Error downloading backup: {e}")
            return False
    
    async def cleanup_old_backups(self, keep_count: int = 2):
        """
        Удалить старые бэкапы БД, оставив только последние keep_count
        
        БЕЗОПАСНО: Удаляет ТОЛЬКО отслеживаемые message_id бэкапов БД!
        Музыкальные файлы НИКОГДА не будут затронуты.
        
        Args:
            keep_count: Количество последних бэкапов для сохранения (по умолчанию 2)
        """
        try:
            print(f"🧹 Cleaning up old database backups (keeping last {keep_count})...")
            
            # Собираем все IDs (из памяти и из БД для персистентности)
            all_ids = []
            if self.db:
                # Берем побольше записей для надежности
                logs = await self.db.get_backup_logs(limit=50)
                all_ids = [log.message_id for log in logs]
                print(f"📊 Found {len(all_ids)} backup logs in database")
            
            # Добавляем IDs из текущей сессии и нормализуем к int для корректной сортировки
            all_ids = list(set([int(mid) for mid in all_ids] + [int(mid) for mid in self.backup_message_ids]))
            
            # Сортируем по возрастанию (от старых к новым)
            all_ids.sort()
            
            # Проверяем, есть ли бэкапы для удаления
            if len(all_ids) <= keep_count:
                print(f"ℹ️ Only {len(all_ids)} backup(s) tracked, nothing to clean up (limit is {keep_count})")
                return
            
            # Вычисляем, сколько бэкапов нужно удалить
            backups_to_delete = all_ids[:-keep_count]  # Все кроме последних keep_count
            print(f"🗑️ Found {len(backups_to_delete)} old backups to delete")
            deleted_count = 0
            
            for message_id in backups_to_delete:
                try:
                    # Удаляем сообщение из Telegram
                    delete_response = httpx.post(
                        f"{self.storage.base_url}/deleteMessage",
                        data={
                            'chat_id': self.storage.channel_id,
                            'message_id': message_id
                        },
                        timeout=10.0
                    )
                    
                    is_ok = delete_response.status_code == 200 and delete_response.json().get('ok')
                    
                    if is_ok or delete_response.status_code == 400: # 400 обычно значит сообщение уже удалено
                        deleted_count += 1
                        print(f"🗑️ Deleted database backup: message {message_id}")
                        
                        # Удаляем из БД
                        if self.db:
                            await self.db.delete_backup_log(message_id)
                        
                        # Удаляем из памяти
                        if message_id in self.backup_message_ids:
                            self.backup_message_ids.remove(message_id)
                    else:
                        print(f"⚠️ Could not delete message {message_id}: {delete_response.text}")
                        
                except Exception as e:
                    print(f"⚠️  Error deleting message {message_id}: {e}")
                    continue
            
            # Обновляем список сессии
            # Мы уже удалили из него нужные элементы в цикле выше
            
            if deleted_count > 0:
                print(f"✅ Cleaned up {deleted_count} old database backup(s)")
                print(f"ℹ️  Kept last {len(self.backup_message_ids)} backup(s)")
                print(f"🛡️  Music files were NOT touched - only tracked .db backups removed")
            else:
                print("ℹ️  No old database backups were deleted")
                
        except Exception as e:
            print(f"⚠️  Error during backup cleanup: {e}")
            # Не критично, продолжаем работу
