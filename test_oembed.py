"""
Проверка oEmbed API ответа
"""
import requests
import json

url = "https://open.spotify.com/track/33uCmVJE2HTSnWx8k64TCQ"
oembed_url = f"https://open.spotify.com/oembed?url={url}"

print("🔍 Проверка Spotify oEmbed API\n")
print(f"URL: {oembed_url}\n")

response = requests.get(oembed_url)
data = response.json()

print("📋 Полный ответ:\n")
print(json.dumps(data, indent=2, ensure_ascii=False))
