"""
Тест метода Edit Probe для получения информации о сообщении
"""
import httpx
import config

def test_edit_probe():
    base_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
    channel_id = config.STORAGE_CHANNEL_ID
    
    # Мы знаем, что бэкап лежит на 3688 (или около того)
    # Попробуем "отредактировать" его Reply Markup (даже если его нет)
    test_ids = [3688, 3682, 3667] 
    
    print(f"🧪 Тестирование Edit Probe в канале {channel_id}...")
    
    for msg_id in test_ids:
        try:
            # Пытаемся обновить Reply Markup на пустой
            # Это легальная операция, которая возвращает объект Message
            resp = httpx.post(f"{base_url}/editMessageReplyMarkup", data={
                'chat_id': channel_id,
                'message_id': msg_id,
                'reply_markup': '{"inline_keyboard": []}'
            }).json()
            
            if resp.get('ok'):
                m = resp['result']
                print(f"✅ [ID {msg_id}] Успех!")
                if m.get('audio'):
                    print(f"   🎵 Это AUDIO: {m['audio'].get('performer')} - {m['audio'].get('title')}")
                elif m.get('document'):
                    print(f"   📄 Это DOCUMENT: {m['document'].get('file_name')}")
                else:
                    print(f"   ❓ Это другое: {m.keys()}")
            else:
                print(f"   ❌ [ID {msg_id}] Ошибка: {resp.get('description')}")
                
        except Exception as e:
            print(f"   💥 [ID {msg_id}] Эксплойт не удался: {e}")

if __name__ == "__main__":
    test_edit_probe()
