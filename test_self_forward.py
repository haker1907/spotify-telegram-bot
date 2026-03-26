"""
Тест метода Self-Forward для получения метаданных
"""
import httpx
import config

def test_self_forward():
    base_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
    channel_id = config.STORAGE_CHANNEL_ID
    
    # ID бэкапа
    msg_id = 3692  
    
    print(f"🧪 Тестирование Self-Forward в канале {channel_id}...")
    
    try:
        # Форвардим сообщение из канала в этот же канал
        resp = httpx.post(f"{base_url}/forwardMessage", data={
            'chat_id': channel_id,
            'from_chat_id': channel_id,
            'message_id': msg_id
        }).json()
        
        if resp.get('ok'):
            m = resp['result']
            new_msg_id = m['message_id']
            print(f"✅ УСПЕХ! Сообщение {msg_id} сдублировано как {new_msg_id}")
            
            if m.get('audio'):
                print(f"   🎵 AUDIO: {m['audio'].get('performer')} - {m['audio'].get('title')}")
            elif m.get('document'):
                print(f"   📄 DOCUMENT: {m['document'].get('file_name')}")
                
            # Сразу удаляем дубликат
            httpx.post(f"{base_url}/deleteMessage", data={
                'chat_id': channel_id,
                'message_id': new_msg_id
            })
            print(f"🗑️ Дубликат {new_msg_id} удален.")
        else:
            print(f"❌ Ошибка: {resp.get('description')}")
            
    except Exception as e:
        print(f"💥 Ошибка: {e}")

if __name__ == "__main__":
    test_self_forward()
