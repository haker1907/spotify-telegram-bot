import sys
import yt_dlp

def test_extract():
    url = "https://www.youtube.com/watch?v=4m9Ql32tgbw"
    
    ydl_opts = {
        'format': 'best',
        'quiet': False,
        'extractor_args': {
            'youtube': {
                # We remove player_client to let yt-dlp use its defaults
                'skip': ['translated_subs'],
            }
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
            print("BEST AUDIO FORMAT FOUND:", info.get('format_id'))
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_extract()
