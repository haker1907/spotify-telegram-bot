import os
import sys
import asyncio
sys.path.append(os.getcwd())
from services.download_service import DownloadService
import yt_dlp

async def debug_options():
    ds = DownloadService()
    url = "https://www.youtube.com/watch?v=4m9Ql32tgbw"
    ydl_opts = ds._get_base_ydl_opts("DJ Tchouzen", "Nulteex", "192", "mp3", [])
    
    print("YT-DLP OPTIONS BEING USED:")
    import pprint
    pprint.pprint(ydl_opts)
    
    # Try getting formats directly with these exact options
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"\nExtracting info for {url} ...")
            info = ydl.extract_info(url, download=False)
            print("\nSUCCESS! Formats found:")
            if info and 'formats' in info:
                for f in info['formats']:
                    print(f.get('format_id', ''), f.get('ext', ''), f.get('acodec', ''), f.get('vcodec', ''))
            print("\nBEST AUDIO FORMAT:", info.get('format_id'))
    except yt_dlp.utils.DownloadError as e:
        print(f"\nDOWNLOAD ERROR: {e}")
    except Exception as e:
        print(f"\nERROR: {e}")

if __name__ == "__main__":
    asyncio.run(debug_options())
