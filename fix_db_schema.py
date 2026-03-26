import asyncio
import os
import sys

# Добавляем корень проекта в sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import DatabaseManager

async def fix_schema():
    print("🛠️ Исправление схемы БД: добавление image_url в telegram_files...")
    db = DatabaseManager()
    await db.init_db()
    
    async with db.engine.begin() as conn:
        try:
            await conn.exec_driver_sql("ALTER TABLE telegram_files ADD COLUMN image_url VARCHAR(500)")
            print("✅ Столбец image_url успешно добавлен.")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("ℹ️ Столбец image_url уже существует.")
            else:
                print(f"❌ Ошибка: {e}")
                
    await db.close()

if __name__ == "__main__":
    asyncio.run(fix_schema())
