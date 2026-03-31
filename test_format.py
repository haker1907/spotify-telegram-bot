import sys
import yt_dlp

def test_extract():
    url = "https://www.youtube.com/watch?v=4m9Ql32tgbw"
    
    ydl_opts = {
        'format': 'best',
        'quiet': False,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios'],
                'skip': ['translated_subs'],
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36',
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Extracting info for {url} with best format...")
            info = ydl.extract_info(url, download=False)
            print("SUCCESS! Formats found:")
            if info and 'formats' in info:
                for f in info['formats']:
                    print(f.get('format_id', ''), f.get('ext', ''), f.get('acodec', ''), f.get('vcodec', ''))
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_extract()
