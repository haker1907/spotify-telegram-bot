
import os
import asyncio
import yt_dlp
import subprocess
import json

async def check_metadata():
    download_dir = "./test_meta"
    os.makedirs(download_dir, exist_ok=True)
    
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    quality = '9200'
    ffmpeg_args = ['-af', 'aresample=192000', '-sample_fmt', 's32']
    
    out_tmpl = os.path.join(download_dir, f"test_{quality}.%(ext)s")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': out_tmpl,
        'overwrites': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'flac',
        }],
        'postprocessor_args': {
            'ffmpeg': ffmpeg_args
        },
        'quiet': True,
    }
    
    print(f"📥 Downloading and converting to {quality}...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
        
    file_path = os.path.join(download_dir, f"test_{quality}.flac")
    
    print(f"\n🔍 Analyzing metadata for {file_path}...")
    try:
        cmd = [
            'ffprobe', 
            '-v', 'quiet', 
            '-print_format', 'json', 
            '-show_streams', 
            file_path
        ]
        result = subprocess.check_output(cmd).decode('utf-8')
        data = json.loads(result)
        
        stream = data['streams'][0]
        print(f"Sample Rate: {stream.get('sample_rate')} Hz")
        print(f"Bits per sample: {stream.get('bits_per_raw_sample') or stream.get('bits_per_sample')} bits")
        print(f"Codec: {stream.get('codec_name')}")
        
    except Exception as e:
        print(f"❌ Error checking metadata: {e}")

if __name__ == "__main__":
    asyncio.run(check_metadata())
