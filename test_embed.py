"""
Проверка Embed HTML
"""
import requests
from bs4 import BeautifulSoup

track_id = "33uCmVJE2HTSnWx8k64TCQ"
embed_url = f"https://open.spotify.com/embed/track/{track_id}"

print(f"🔍 Проверка Embed страницы\n")
print(f"URL: {embed_url}\n")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

response = requests.get(embed_url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

print("📋 Meta теги:\n")
for meta in soup.find_all('meta'):
    if meta.get('property') or meta.get('name'):
        prop = meta.get('property') or meta.get('name')
        content = meta.get('content', '')[:150]
        print(f"   {prop}: {content}")

print("\n📋 Title:\n")
title = soup.find('title')
if title:
    print(f"   {title.text}")
