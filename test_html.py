"""
Проверка HTML структуры Spotify страницы
"""
import requests
from bs4 import BeautifulSoup

url = "https://open.spotify.com/track/33uCmVJE2HTSnWx8k64TCQ"

print("🔍 Проверка HTML структуры Spotify\n")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

response = requests.get(url, headers=headers, timeout=10)
soup = BeautifulSoup(response.text, 'html.parser')

print("📋 Meta теги:\n")

# Все meta теги с property
for meta in soup.find_all('meta', property=True):
    print(f"   {meta.get('property')}: {meta.get('content', '')[:100]}")

print("\n📋 Title тег:\n")
title = soup.find('title')
if title:
    print(f"   {title.text}")

print("\n📋 Все meta теги с name:\n")
for meta in soup.find_all('meta', attrs={'name': True}):
    print(f"   {meta.get('name')}: {meta.get('content', '')[:100]}")
