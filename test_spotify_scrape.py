
import requests
import re

url = "https://open.spotify.com/track/33uCmVJE2HTSnWx8k64TCQ"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

print(f"🔍 Checking Spotify Page: {url}\n")

response = requests.get(url, headers=headers)
html = response.text

# Try to find artist in meta tags
artist_match = re.search(r'<meta property="og:description" content="([^"]+)"', html)
if artist_match:
    print(f"Content: {artist_match.group(1)}")
    # Usually it looks like "Song · Artist · Year" or "Artist · Song · Album"
    parts = artist_match.group(1).split(" · ")
    if len(parts) >= 2:
        print(f"Possible artist: {parts[1]}")

# Another way: title tag often looks like "Track Name - song by Artist | Spotify"
title_match = re.search(r'<title>([^<]+)</title>', html)
if title_match:
    title_text = title_match.group(1)
    print(f"Title tag: {title_text}")
    if " - song by " in title_text:
        artist = title_text.split(" - song by ")[1].split(" | Spotify")[0]
        print(f"Artist from title: {artist}")
