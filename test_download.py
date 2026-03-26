import asyncio
import os
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

from services.download_service import DownloadService

async def main():
    service = DownloadService()
    # Изначально проблемные треки:
    # 1. wHlAnhkLUvw (Dame Un Grrr)
    # 2. Tdt79d2BaoI (SAD ABOUT FUNK)
    # 3. OuG2g6n68-E (NO BALANCAR)
    target_url = "https://www.youtube.com/watch?v=OuG2g6n68-E"
    quality = "320"
    file_format = "mp3"
    
    print(f"🧪 Testing download for: {target_url}")
    # Используем новый метод для прямой загрузки по URL
    result = await service.download_from_url(target_url, quality, file_format)
    
    if result and 'file_path' in result:
        print(f"✅ Success! File downloaded to: {result['file_path']}")
        if os.path.exists(result['file_path']):
            print(f"📂 File verified on disk. Size: {os.path.getsize(result['file_path'])} bytes")
    else:
        print(f"❌ Download failed: {result.get('error') if result else 'Unknown error'}")

if __name__ == "__main__":
    asyncio.run(main())
