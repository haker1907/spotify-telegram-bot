import os
import sys
import asyncio

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from database.db_manager import DatabaseManager
from services.db_backup_service import DatabaseBackupService


def test_get_database_file_path_sqlite(tmp_path):
    db_file = tmp_path / "spotify_bot.db"
    # Делаем URL совместимым с SQLAlchemy (в URL используем прямые слэши)
    db_file_url_path = str(db_file).replace("\\", "/")
    url = f"sqlite+aiosqlite:///{db_file_url_path}"

    db = DatabaseManager(database_url=url)
    try:
        resolved = db.get_database_file_path()
        assert resolved is not None
        assert resolved == os.path.abspath(str(db_file))
    finally:
        asyncio.run(db.close())


def test_get_database_file_path_non_sqlite(tmp_path):
    tmp_path_str = str(tmp_path).replace("\\", "/")
    db = DatabaseManager(database_url=f"sqlite+aiosqlite:///{tmp_path_str}/x.db")
    try:
        db.database_url = "postgresql+asyncpg://user:pass@localhost/db"
        assert db.get_database_file_path() is None
    finally:
        asyncio.run(db.close())


def test_backup_service_disabled_on_none_db_path():
    svc = DatabaseBackupService(storage_service=object(), db_path=None, db_manager=None)
    assert svc.is_running is False
    assert svc.backup_file_id is None

