import os
import sys
import asyncio
sys.path.append(os.getcwd())
import yt_dlp

async def debug_options():
    url = "https://www.youtube.com/watch?v=4m9Ql32tgbw"
    
    # Let's try what test_format2.py had exactly plus format: bestaudio/best
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': False,
        'extractor_args': {
            'youtube': {
                # Notice we completely omit 'player_client'
                'skip': ['translated_subs'],
            }
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"\n[Test 1] Extracting info for {url} WITHOUT cookies or player_client...")
            info = ydl.extract_info(url, download=False)
            print("\nSUCCESS! Formats found:")
            if info and 'formats' in info:
                for f in info['formats']:
                    print(f.get('format_id', ''), f.get('ext', ''), f.get('acodec', ''), f.get('vcodec', ''))
            print("\nBEST AUDIO FORMAT:", info.get('format_id'))
    except yt_dlp.utils.DownloadError as e:
        print(f"\nDOWNLOAD ERROR: {e}")
        
    print("\n-------------------------------\n")
        
    # Test 2: With cookies
    ydl_opts['cookiefile'] = os.path.join(os.getcwd(), 'cookies.txt')
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"\n[Test 2] Extracting info for {url} WITH cookies...")
            info = ydl.extract_info(url, download=False)
            print("\nSUCCESS! Formats found:")
            if info and 'formats' in info:
                for f in info['formats']:
                    print(f.get('format_id', ''), f.get('ext', ''), f.get('acodec', ''), f.get('vcodec', ''))
            print("\nBEST AUDIO FORMAT:", info.get('format_id'))
    except yt_dlp.utils.DownloadError as e:
        print(f"\nDOWNLOAD ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(debug_options())
