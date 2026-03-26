import yt_dlp
import os

def check_ydl():
    ydl_opts = {
        'quiet': False,
        'no_warnings': False,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Check extraction
        try:
            url = "https://www.youtube.com/watch?v=fJ9rUzIMcZQ"
            info = ydl.extract_info(url, download=False)
            print("✅ Successfully extracted info!")
            print(f"Title: {info.get('title')}")
            formats = info.get('formats', [])
            print(f"Number of formats: {len(formats)}")
        except Exception as e:
            print(f"❌ Extraction failed: {e}")

if __name__ == "__main__":
    print(f"Node.js check: {os.popen('node -v').read().strip()}")
    check_ydl()
