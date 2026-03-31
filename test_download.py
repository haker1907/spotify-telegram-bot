import os
import asyncio
import sys

# Добавляем текущую директорию в путь для импорта
sys.path.append(os.getcwd())

# Mock TELEGRAM_BOT_TOKEN for config
os.environ['TELEGRAM_BOT_TOKEN'] = '123:mock'

from services.download_service import DownloadService

async def test_robust_download():
    service = DownloadService()
    
    # Видео ID, который вызывал ошибку (Linkin Park - Numb)
    video_url = "https://www.youtube.com/watch?v=VK3SIu2_fdc"
    
    print(f"🧪 Testing robust download for: {video_url}")
    
    # Прямой вызов download_from_url
    result = await service.download_from_url(
        video_url, 
        quality='192', 
        file_format='mp3', 
        artist='Linkin Park', 
        track_name='Numb'
    )
    
    if result and 'file_path' in result:
        print(f"✅ SUCCESS: File downloaded to {result['file_path']}")
        print(f"📊 Title: {result['title']}")
        print(f"⚖️ Size: {result.get('file_size', 0)} bytes")
        
        # Cleanup
        if os.path.exists(result['file_path']):
            os.remove(result['file_path'])
            print(f"🗑️ Cleaned up test file.")
        return True
    else:
        print(f"❌ FAILURE: Download failed!")
        print(f"📝 Error: {result.get('error', 'Unknown error')}")
        return False

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    if loop.run_until_complete(test_robust_download()):
        sys.exit(0)
    else:
        sys.exit(1)
