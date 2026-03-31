"""
Сервис для работы со Spotify ссылками БЕЗ API
Простой подход: используем oEmbed для названия, YouTube сам найдёт исполнителя
"""
import re
import json
import asyncio
from typing import Optional, Dict
import requests
import httpx
from bs4 import BeautifulSoup


class SpotifyService:
    """Сервис для извлечения информации из Spotify ссылок без API"""
    
    def __init__(self):
        self.session = requests.Session()
        print("✅ Spotify сервис инициализирован (oEmbed)")
    
    @staticmethod
    def parse_spotify_url(url: str) -> Optional[Dict[str, str]]:
        """
        Парсинг Spotify URL
        Возвращает: {'type': 'track'|'album'|'playlist', 'id': 'spotify_id'}
        """
        patterns = {
            'track': r'spotify\.com/track/([a-zA-Z0-9]+)',
            'album': r'spotify\.com/album/([a-zA-Z0-9]+)',
            'playlist': r'spotify\.com/playlist/([a-zA-Z0-9]+)',
            'artist': r'spotify\.com/artist/([a-zA-Z0-9]+)',
        }
        
        for content_type, pattern in patterns.items():
            match = re.search(pattern, url)
            if match:
                return {
                    'type': content_type,
                    'id': match.group(1)
                }
        
        return None
    
    async def get_track_info_from_url(self, url: str) -> Optional[Dict]:
        """
        Получить информацию о треке из Spotify URL
        Использует oEmbed API и Embed страницу для надежности
        """
        try:
            # Очищаем URL от параметров
            clean_url = url.split('?')[0]
            parsed = self.parse_spotify_url(clean_url)
            if not parsed or parsed['type'] != 'track':
                return None
            
            track_id = parsed['id']
            track_name = ""
            artist_name = ""
            image_url = ""
            
            # 1. Сначала пробуем oEmbed для базовой информации
            oembed_url = f"https://open.spotify.com/oembed?url={clean_url}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            }
            
            try:
                response = self.session.get(oembed_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    track_name = data.get('title', '').strip()
                    image_url = data.get('thumbnail_url')
            except Exception as e:
                print(f"⚠️ oEmbed failed: {e}")
            
            # 2. Если нужно больше данных или oEmbed подвел, используем Embed страницу
            try:
                embed_url = f"https://open.spotify.com/embed/track/{track_id}"
                async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
                    page_response = await client.get(embed_url, timeout=10.0)
                    if page_response.status_code == 200:
                        soup = BeautifulSoup(page_response.text, 'html.parser')
                        script_tag = soup.find('script', {'id': '__NEXT_DATA__', 'type': 'application/json'})
                        
                        if script_tag:
                            data = json.loads(script_tag.string)
                            entity = data.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity', {})
                            
                            if entity:
                                if not track_name:
                                    track_name = entity.get('name', '') or entity.get('title', '')
                                
                                # Извлекаем артистов
                                artists = entity.get('artists', [])
                                if artists:
                                    artist_name = ', '.join([a.get('name', '') for a in artists])
                                elif not artist_name:
                                    artist_name = entity.get('subtitle', '').replace('\u00a0', ' ')
                                
                                # Извлекаем картинку если нет
                                if not image_url:
                                    images = entity.get('visualIdentity', {}).get('image', [])
                                    if images:
                                        image_url = images[0].get('url')
            except Exception as e:
                print(f"⚠️ Embed scraping failed: {e}")
            
            if track_name:
                return {
                    'id': track_id,
                    'name': track_name,
                    'artist': artist_name or "Unknown Artist",
                    'image_url': image_url,
                    'spotify_url': clean_url
                }
            
            return None
            
        except Exception as e:
            print(f"❌ Ошибка при получении данных из Spotify: {e}")
            return None
    
    async def get_track_info(self, track_id: str) -> Optional[Dict]:
        """Получить информацию о треке по ID"""
        url = f"https://open.spotify.com/track/{track_id}"
        info = await self.get_track_info_from_url(url)
        if info and not info.get('id'):
            info['id'] = track_id
        return info
    
    async def search_track(self, query: str) -> list:
        """Алиас для веб-приложения"""
        return await self.search_tracks(query)

    async def _get_anonymous_token(self) -> Optional[str]:
        """Получить анонимный токен через Embed страницу"""
        try:
            # Используем популярный трек для получения токена
            embed_url = "https://open.spotify.com/embed/track/4cOdK2wGLETKBW3PvgPWqT" 
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            }
            
            async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
                response = await client.get(embed_url, timeout=10.0)
                if response.status_code != 200:
                    return None
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                script_tag = soup.find('script', {'id': '__NEXT_DATA__', 'type': 'application/json'})
                
                if script_tag:
                    data = json.loads(script_tag.string)
                    token = data.get('props', {}).get('pageProps', {}).get('state', {}).get('settings', {}).get('session', {}).get('accessToken')
                    return token
        except Exception as e:
            print(f"⚠️ Error getting anonymous token: {e}")
        return None

    async def search_tracks(self, query: str, limit: int = 10) -> list:
        """
        Поиск треков через Web API с анонимным токеном
        """
        token = await self._get_anonymous_token()
        if not token:
            print(f"⚠️ Поиск недоступен: не удалось получить токен")
            return []
            
        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            }
            
            async with httpx.AsyncClient(headers=headers) as client:
                # API поиск
                api_url = f"https://api.spotify.com/v1/search"
                params = {
                    'q': query,
                    'type': 'track',
                    'limit': limit
                }
                
                response = await client.get(api_url, params=params, timeout=10.0)
                if response.status_code == 429:
                    print("⚠️ Search API Rate Limited (429). Retrying with new token...")
                    token = await self._get_anonymous_token()
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        response = await client.get(api_url, params=params, timeout=10.0)
                
                if response.status_code != 200:
                    print(f"⚠️ Search API Error: {response.status_code} {response.text}")
                    return []
                
                data = response.json()
                items = data.get('tracks', {}).get('items', [])
                
                results = []
                for t in items:
                    # Извлекаем картинку
                    image_url = ""
                    images = t.get('album', {}).get('images', [])
                    if images:
                        image_url = images[0].get('url')
                        
                    results.append({
                        'id': t.get('id'),
                        'name': t.get('name'),
                        'artist': ", ".join([a.get('name', '') for a in t.get('artists', [])]),
                        'album': t.get('album', {}).get('name'),
                        'duration_ms': t.get('duration_ms'),
                        'image_url': image_url,
                        'preview_url': t.get('preview_url'),
                        'spotify_url': t.get('external_urls', {}).get('spotify')
                    })
                
                return results
                
        except Exception as e:
            print(f"❌ Search error: {e}")
            return []
    
    def is_playlist_url(self, url: str) -> bool:
        """
        Проверить, является ли URL ссылкой на Spotify плейлист
        
        Args:
            url: URL для проверки
            
        Returns:
            True если это ссылка на плейлист
        """
        parsed = self.parse_spotify_url(url)
        return parsed is not None and parsed['type'] == 'playlist'
    
    async def get_playlist_info(self, playlist_url: str) -> Optional[Dict]:
        """
        Получить информацию о плейлисте через веб-скрапинг
        """
        return await self._get_collection_info(playlist_url, 'playlist')

    async def get_album_info(self, album_url: str) -> Optional[Dict]:
        """
        Получить информацию об альбоме через веб-скрапинг
        """
        return await self._get_collection_info(album_url, 'album')

    async def get_artist_info(self, artist_url: str) -> Optional[Dict]:
        """
        Получить топ-треки артиста через веб-скрапинг
        """
        return await self._get_collection_info(artist_url, 'artist')

    async def _get_collection_info(self, url: str, collection_type: str) -> Optional[Dict]:
        """
        Универсальный метод получения информации о коллекции (плейлист, альбом, артист)
        Использует анонимный токен и Web API.
        """
        try:
            # Парсим URL
            parsed = self.parse_spotify_url(url)
            if not parsed or parsed['type'] != collection_type:
                return None
            
            entity_id = parsed['id']
            
            # 1. Получаем анонимный токен через Embed страницу
            embed_url = f"https://open.spotify.com/embed/{collection_type}/{entity_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            }
            
            async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
                response = await client.get(embed_url, timeout=30.0)
                if response.status_code != 200:
                    return None
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                script_tag = soup.find('script', {'id': '__NEXT_DATA__', 'type': 'application/json'})
                
                if not script_tag: return None
                data = json.loads(script_tag.string)
                token = data.get('props', {}).get('pageProps', {}).get('state', {}).get('settings', {}).get('session', {}).get('accessToken')
                
                if not token:
                    # Fallback для базовых данных без токена (если есть)
                    print(f"⚠️ No token for {collection_type}, falling back to static data")
                    entity = data.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity', {})
                    if not entity: return None
                    
                    tracks = []
                    track_list = entity.get('trackList', []) or entity.get('tracks', {}).get('items', [])
                    for idx, t in enumerate(track_list):
                        # В разных типах сущностей разная структура trackList
                        track_data = t.get('track') if 'track' in t else t
                        tracks.append({
                            'id': track_data.get('uri', '').split(':')[-1] if 'uri' in track_data else f"idx_{idx}",
                            'name': track_data.get('title') or track_data.get('name') or "Unknown",
                            'artist': (track_data.get('artists', [{}])[0].get('name') if 'artists' in track_data else track_data.get('subtitle', 'Unknown')).replace('\u00a0', ' '),
                            'image': None
                        })
                    return {'id': entity_id, 'name': entity.get('name') or entity.get('title'), 'tracks': tracks}

                # 2. Используем Web API с анонимным токеном
                api_headers = {"Authorization": f"Bearer {token}", "User-Agent": headers['User-Agent']}
                
                # Базовая инфо о сущности
                api_base = f"https://api.spotify.com/v1/{collection_type}s/{entity_id}"
                # Для артиста нам нужны top-tracks
                if collection_type == 'artist':
                    api_url = f"{api_base}/top-tracks?market=US"
                elif collection_type == 'album':
                    api_url = f"{api_base}/tracks?limit=50"
                else: # playlist
                    api_url = f"{api_base}/tracks?limit=100"

                # Получаем метаданные сущности (имя, картинка)
                meta_resp = await client.get(api_base, headers=api_headers)
                entity_name = "Unknown"
                entity_image = ""
                
                # Если анонимный API забанен (429), используем данные из HTML
                use_static_fallback = meta_resp.status_code != 200

                if meta_resp.status_code == 200:
                    meta = meta_resp.json()
                    entity_name = meta.get('name', 'Unknown')
                    images = meta.get('images', [])
                    if images: entity_image = images[0].get('url')

                # Получаем треки
                tracks = []
                
                if not use_static_fallback:
                    offset = 0
                    limit = 100
                    
                    while True:
                        current_api_url = api_url
                        if collection_type != 'artist':
                            current_api_url = f"{api_base}/tracks?offset={offset}&limit={limit}"
                        
                        tracks_resp = await client.get(current_api_url, headers=api_headers)
                        if tracks_resp.status_code != 200:
                            use_static_fallback = True
                            break
                            
                        t_data = tracks_resp.json()
                        items = t_data.get('tracks') if collection_type == 'artist' else t_data.get('items', [])
                        
                        if not items: break
                            
                        for item in items:
                            t = item.get('track') if collection_type == 'playlist' else item
                            if not t: continue
                            
                            artists = ", ".join([a.get('name', '') for a in t.get('artists', [])])
                            t_image = entity_image
                            if 'album' in t:
                                imgs = t.get('album', {}).get('images', [])
                                if imgs: t_image = imgs[0].get('url')
                            
                            tracks.append({
                                'id': t.get('id'),
                                'name': t.get('name'),
                                'artist': artists,
                                'image': t_image,
                                'album': t.get('album', {}).get('name') if 'album' in t else entity_name if collection_type == 'album' else None
                            })
                        
                        if collection_type == 'artist' or len(items) < limit or len(tracks) >= 1000:
                            break
                        offset += limit

                # Финальный fallback к статическим данным (если API не сработал на любом этапе)
                if use_static_fallback or not tracks:
                    print(f"🔄 Using static data extraction for {collection_type} (API rate limited)")
                    entity = data.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity', {})
                    if not entity: return None
                    
                    entity_name = entity.get('name') or entity.get('title') or "Unknown"
                    entity_image = ""
                    
                    # 1. Пробуем разные пути для картинки коллекции
                    # Для артистов: visualIdentity.image
                    viz = entity.get('visualIdentity', {})
                    if isinstance(viz, dict) and 'image' in viz:
                        img_data = viz['image']
                        if isinstance(img_data, list) and len(img_data) > 0:
                            entity_image = img_data[0].get('url') or ""
                        elif isinstance(img_data, dict):
                            entity_image = img_data.get('url') or ""
                    
                    # Если не нашли, пробуем visuals (старый формат или другой тип)
                    if not entity_image:
                        visuals = entity.get('visuals', {})
                        avatar = visuals.get('avatar') or visuals.get('avatarImage')
                        if isinstance(avatar, dict):
                            sources = avatar.get('sources', [])
                            if sources: entity_image = sources[0].get('url')
                        elif isinstance(avatar, list) and len(avatar) > 0:
                            entity_image = avatar[0].get('url')
                    
                    # Для альбомов/плейлистов: coverArt
                    if not entity_image:
                        cover = entity.get('coverArt', {})
                        sources = cover.get('sources', [])
                        if sources: entity_image = sources[0].get('url')
                    
                    # 2. Извлекаем треки
                    tracks = []
                    # Для артиста треки в tracks, для альбома в trackList или tracks
                    track_list = entity.get('tracks', {}).get('items', []) or entity.get('trackList', [])
                    if not track_list and 'tracks' in entity and isinstance(entity['tracks'], list):
                        track_list = entity['tracks']
                    
                    for idx, t in enumerate(track_list):
                        t_data = t.get('track') if 'track' in t else t
                        # Пробуем разные поля для имени и артиста
                        t_name = t_data.get('name') or t_data.get('title') or "Unknown"
                        t_artist = "Unknown"
                        if 'artists' in t_data:
                            t_artist = ", ".join([a.get('name', 'Unknown') for a in t_data['artists']])
                        elif 'subtitle' in t_data:
                            t_artist = t_data.get('subtitle')
                        
                        # Spotify ID из URI или как есть
                        t_id = t_data.get('id')
                        if not t_id and 'uri' in t_data:
                            t_id = t_data.get('uri').split(':')[-1]
                        
                        tracks.append({
                            'id': t_id or f"idx_{idx}",
                            'name': t_name,
                            'artist': t_artist.replace('\u00a0', ' '),
                            'image': entity_image # Default to artist image initially
                        })

                    # SPECIFIC FIX FOR ARTIST TRACKS:
                    # Artist "Top Tracks" in static data do NOT contain album art.
                    # We must fetch it individually from track embeds.
                    if collection_type == 'artist' and tracks:
                        print(f"🎨 Fetching missing album art for {len(tracks)} tracks concurrently...")
                        async def update_track_image(track):
                            if track['id'] and not track['id'].startswith('idx_'):
                                img = await self._get_track_image_from_embed(track['id'])
                                if img:
                                    track['image'] = img

                        # Run concurrent requests
                        await asyncio.gather(*[update_track_image(t) for t in tracks])

                return {
                    'id': entity_id,
                    'type': collection_type,
                    'name': entity_name,
                    'image': entity_image,
                    'tracks': tracks,
                    'total_tracks': len(tracks)
                }
        except Exception as e:
            print(f"❌ Error fetching {collection_type}: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _get_track_image_from_embed(self, track_id: str) -> Optional[str]:
        """
        Helper to fetch album art from single track embed.
        Needed because Artist page static data lacks individual track images.
        """
        try:
            url = f"https://open.spotify.com/embed/track/{track_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            }
            async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
                resp = await client.get(url, timeout=5.0)
                if resp.status_code != 200: return None
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                script = soup.find('script', {'id': '__NEXT_DATA__'})
                if not script: return None
                
                data = json.loads(script.string)
                entity = data.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity', {})
                
                # Priority: visualIdentity (new) -> coverArt -> album.images -> visuals
                if 'visualIdentity' in entity:
                    viz = entity['visualIdentity']
                    if 'image' in viz:
                        imgs = viz['image']
                        if isinstance(imgs, list) and imgs: return imgs[0].get('url')
                        elif isinstance(imgs, dict): return imgs.get('url')

                if 'coverArt' in entity:
                    srcs = entity['coverArt'].get('sources', [])
                    if srcs: return srcs[0].get('url')
                
                if 'album' in entity:
                    imgs = entity['album'].get('images', [])
                    if imgs: return imgs[0].get('url')

                return None
        except Exception as e:
            # Silent fail for individual image
            return None
