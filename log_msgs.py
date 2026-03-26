"""
Скрипт для детального лога последних 50 сообщений
"""
import httpx
import config

def log_last_messages():
    base_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
    channel_id = config.STORAGE_CHANNEL_ID
    
    try:
        # Получаем ID последнего сообщения
        resp = httpx.post(f"{base_url}/sendMessage", data={
            'chat_id': channel_id,
            'text': '🧪 Тест...'
        }).json()
        
        last_id = resp['result']['message_id']
        bot_id = httpx.get(f"{base_url}/getMe").json()['result']['id']
        
        print(f"📋 Последние 50 сообщений в канале {channel_id}:")
        
        for i in range(50):
            msg_id = last_id - i
            r = httpx.post(f"{base_url}/forwardMessage", data={
                'chat_id': bot_id,
                'from_chat_id': channel_id,
                'message_id': msg_id
            }).json()
            
            if r.get('ok'):
                m = r['result']
                content_type = "Unknown"
                name = ""
                
                if m.get('audio'):
                    content_type = "🎵 AUDIO"
                    name = f"{m['audio'].get('performer')} - {m['audio'].get('title')}"
                elif m.get('document'):
                    content_type = "📄 DOCUMENT"
                    name = m['document'].get('file_name')
                elif m.get('text'):
                    content_type = "📝 TEXT"
                    name = m['text'][:30] + "..."
                
                print(f"   [{msg_id}] {content_type}: {name}")
            else:
                print(f"   [{msg_id}] ❌ Ошибка: {r.get('description')}")
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    log_last_messages()
