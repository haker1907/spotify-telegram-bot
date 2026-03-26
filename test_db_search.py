import asyncio
import os
import sys

# Добавляем корень проекта в sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import DatabaseManager

async def test_db_search():
    print("🧪 Тестирование поиска по БД (Discover)...")
    db = DatabaseManager()
    await db.init_db()
    
    # 1. Попробуем найти что-то общее
    query = "the"
    print(f"🔍 Поиск по запросу: '{query}'")
    results = await db.search_telegram_files(query, limit=5)
    
    print(f"📊 Найдено результатов: {len(results)}")
    for i, track in enumerate(results, 1):
        print(f"   {i}. {track['artist']} - {track['name']} (ID: {track['id']})")
        
    if not results:
        print("💡 В базе данных пока нет треков или ничего не найдено по этому запросу.")
    
    await db.close()

if __name__ == "__main__":
    asyncio.run(test_db_search())
