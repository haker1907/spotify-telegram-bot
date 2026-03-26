"""
Улучшенный диагностический скрипт для поиска музыки в канале
"""
import httpx
import config
import time

def find_music_in_channel():
    base_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
    channel_id = config.STORAGE_CHANNEL_ID
    
    print(f"🔍 Исследование канала {channel_id}...")
    
    try:
        # 1. Находим текущий HEAD (отправляем сообщение)
        resp = httpx.post(f"{base_url}/sendMessage", data={
            'chat_id': channel_id,
            'text': '🧪 Диагностика диапазона...'
        }).json()
        
        if not resp.get('ok'):
            print(f"❌ Ошибка отправки: {resp.get('description')}")
            return
            
        head_id = resp['result']['message_id']
        print(f"📍 Текущий последний ID в канале: {head_id}")
        
        # Удаляем его
        httpx.post(f"{base_url}/deleteMessage", data={'chat_id': channel_id, 'message_id': head_id})
        
        # 2. Сканируем широкими шагами назад
        print(f"🔎 Сканируем историю (макс 10000 сообщений назад)...")
        
        # Получаем ID бота для forward'а
        bot_id = httpx.get(f"{base_url}/getMe").json()['result']['id']
        
        audio_found = []
        
        # Проверяем каждые 100 сообщений, чтобы найти, где вообще есть музыка
        for step in range(0, 10000, 200):
            msg_id = head_id - step
            if msg_id <= 0: break
            
            # Пробуем форварднуть группу из 5 сообщений вокруг этой точки
            found_in_block = False
            for i in range(5):
                check_id = msg_id - i
                if check_id <= 0: continue
                
                try:
                    r = httpx.post(f"{base_url}/forwardMessage", data={
                        'chat_id': bot_id,
                        'from_chat_id': channel_id,
                        'message_id': check_id
                    }, timeout=5.0).json()
                    
                    if r.get('ok') and r['result'].get('audio'):
                        audio = r['result']['audio']
                        print(f"🎵 Найдена музыка на ID {check_id}: {audio.get('performer')} - {audio.get('title')}")
                        audio_found.append(check_id)
                        found_in_block = True
                        break
                except:
                    continue
            
            if not found_in_block:
                if step % 1000 == 0:
                    print(f"⏳ Проверено до ID {msg_id}, пока ничего...")
                
        if audio_found:
            print(f"\n✅ ИТОГО: Музыка найдена в диапазоне ID {min(audio_found)} - {max(audio_found)}")
            print(f"💡 Вам нужно настроить Deep Sync на сканирование от {max(audio_found)}.")
        else:
            print("\n❌ Музыка не найдена во всей доступной истории (10000 сообщений).")
            print("Возможно, в этом канале действительно нет аудио-файлов, отправленных как 'Audio'.")

    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    find_music_in_channel()
