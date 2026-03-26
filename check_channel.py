"""
Диагностический скрипт для проверки содержимого Telegram канала
"""
import httpx
import config

def check_channel_messages():
    """Проверить последние сообщения в канале"""
    base_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
    
    # Получаем информацию о закрепленном сообщении
    print("=" * 80)
    print("🔍 Checking Telegram Storage Channel")
    print("=" * 80)
    
    try:
        # 1. Получаем информацию о канале
        resp = httpx.get(f"{base_url}/getChat", params={'chat_id': config.STORAGE_CHANNEL_ID}, timeout=30.0)
        if resp.status_code == 200:
            chat_info = resp.json().get('result', {})
            print(f"\n📦 Channel Info:")
            print(f"   Title: {chat_info.get('title', 'N/A')}")
            print(f"   Type: {chat_info.get('type', 'N/A')}")
            
            pinned = chat_info.get('pinned_message')
            if pinned:
                print(f"\n📌 Pinned Message ID: {pinned.get('message_id')}")
                print(f"   Date: {pinned.get('date')}")
                if pinned.get('document'):
                    print(f"   Type: Document ({pinned['document'].get('file_name')})")
                elif pinned.get('audio'):
                    print(f"   Type: Audio")
        
        # 2. Пробуем получить несколько сообщений методом forwardMessage
        print(f"\n🔎 Scanning recent messages...")
        
        # Получаем ID бота
        bot_info = httpx.get(f"{base_url}/getMe", timeout=10.0).json()
        bot_id = bot_info.get('result', {}).get('id')
        
        if not bot_id:
            print("❌ Could not get bot ID")
            return
        
        # Пробуем последние 100 ID от закрепленного
        pinned_id = pinned.get('message_id', 100) if pinned else 100
        
        audio_count = 0
        document_count = 0
        other_count = 0
        
        print(f"\n📊 Scanning from ID {pinned_id} backwards...")
        
        for msg_id in range(pinned_id, max(0, pinned_id - 100), -1):
            try:
                resp = httpx.post(f"{base_url}/forwardMessage", data={
                    'chat_id': bot_id,
                    'from_chat_id': config.STORAGE_CHANNEL_ID,
                    'message_id': msg_id,
                    'disable_notification': True
                }, timeout=10.0)
                
                if resp.status_code == 200:
                    msg_data = resp.json().get('result', {})
                    
                    if msg_data.get('audio'):
                        audio = msg_data['audio']
                        audio_count += 1
                        print(f"   🎵 ID {msg_id}: {audio.get('performer', 'Unknown')} - {audio.get('title', 'Unknown')}")
                    elif msg_data.get('document'):
                        doc = msg_data['document']
                        document_count += 1
                        if msg_id % 20 == 0:  # Показываем только каждый 20-й документ
                            print(f"   📄 ID {msg_id}: {doc.get('file_name', 'Unknown')}")
                    else:
                        other_count += 1
                        
            except Exception as e:
                if msg_id % 50 == 0:
                    print(f"   ⚠️  ID {msg_id}: Error - {e}")
        
        print(f"\n📈 Summary (last 100 messages):")
        print(f"   🎵 Audio files: {audio_count}")
        print(f"   📄 Documents: {document_count}")
        print(f"   📝 Other: {other_count}")
        
        if audio_count == 0:
            print(f"\n⚠️  WARNING: No audio files found in recent history!")
            print(f"   This explains why Deep Sync found 0 tracks.")
            print(f"\n💡 Possible reasons:")
            print(f"   1. Music was never uploaded to this channel")
            print(f"   2. Music is in a different channel")
            print(f"   3. Music was deleted")
            print(f"   4. Channel ID is incorrect")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_channel_messages()
