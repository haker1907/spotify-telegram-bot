"""
Тест извлечения метаданных через editMessageCaption
"""
import httpx
import config

def test_metadata_edit():
    base_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
    channel_id = config.STORAGE_CHANNEL_ID
    
    # ID бэкапа (точно сообщение бота)
    msg_id = 3692  
    
    print(f"🧪 Тестирование извлечения метаданных ID {msg_id} через редактирование...")
    
    try:
        # Сначала получаем текущую подпись (если есть)
        # Мы не можем ее получить просто так, но мы можем попробовать "обновить" ее
        # с добавлением пробела.
        
        # Попробуем просто editMessageCaption
        resp = httpx.post(f"{base_url}/editMessageCaption", data={
            'chat_id': channel_id,
            'message_id': msg_id,
            'caption': '🗄️ Database Backup - 2026-02-10 07:53:18 ' # добавили пробел в конце
        }).json()
        
        if resp.get('ok'):
            m = resp['result']
            print("✅ УСПЕХ! Метаданные получены:")
            if m.get('audio'):
                print(f"   🎵 AUDIO: {m['audio'].get('performer')} - {m['audio'].get('title')}")
            elif m.get('document'):
                print(f"   📄 DOCUMENT: {m['document'].get('file_name')} (Size: {m['document'].get('file_size')})")
            
            # Возвращаем как было (убираем пробел)
            httpx.post(f"{base_url}/editMessageCaption", data={
                'chat_id': channel_id,
                'message_id': msg_id,
                'caption': '🗄️ Database Backup - 2026-02-10 07:53:18'
            })
        else:
            print(f"❌ Ошибка: {resp.get('description')}")
            
    except Exception as e:
        print(f"💥 Ошибка: {e}")

if __name__ == "__main__":
    test_metadata_edit()
