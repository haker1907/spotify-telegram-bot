"""
YouTube Data API v3 Service - поиск видео через официальный API
"""
import os
import httpx
from typing import Optional, Dict, List


class YouTubeAPIService:
    """Сервис для работы с YouTube Data API v3"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('YOUTUBE_API_KEY')
        self.base_url = "https://www.googleapis.com/youtube/v3"
        self.quota_exceeded = False
        self._quota_warning_shown = False
        
        if not self.api_key:
            print("YOUTUBE_API_KEY not set. YouTube search will use fallback method.")
        else:
            print(f"YouTube API initialized (key: {self.api_key[:10]}...)")
    
    def search_video(self, query: str, max_results: int = 1) -> Optional[Dict]:
        """
        Поиск видео через YouTube API
        
        Args:
            query: Поисковый запрос (например, "Artist - Track Name")
            max_results: Количество результатов (по умолчанию 1)
            
        Returns:
            Dict с информацией о видео или None
        """
        if not self.api_key:
            print("YouTube API key not configured")
            return None
        if self.quota_exceeded:
            if not self._quota_warning_shown:
                print("YouTube API disabled for this runtime (quota exceeded). Using yt-dlp fallback.")
                self._quota_warning_shown = True
            return None
        
        try:
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'maxResults': max_results,
                'key': self.api_key,
                'videoCategoryId': '10',  # Music category
                'order': 'relevance'
            }
            
            response = httpx.get(
                f"{self.base_url}/search",
                params=params,
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'items' in data and len(data['items']) > 0:
                    item = data['items'][0]
                    video_id = item['id']['videoId']
                    snippet = item['snippet']
                    
                    return {
                        'video_id': video_id,
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'title': snippet.get('title'),
                        'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url'),
                        'channel': snippet.get('channelTitle'),
                        'published_at': snippet.get('publishedAt')
                    }
                else:
                    print(f"No results found for: {query}")
                    return None
            elif response.status_code == 403:
                error_data = response.json()
                error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason')
                
                if error_reason == 'quotaExceeded':
                    print("YouTube API quota exceeded. Try again tomorrow or increase quota.")
                    self.quota_exceeded = True
                    self._quota_warning_shown = False
                else:
                    print(f"YouTube API error 403: {error_reason}")
                return None
            else:
                print(f"YouTube API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Error searching YouTube API: {e}")
            return None
    
    def get_video_details(self, video_id: str) -> Optional[Dict]:
        """
        Получить детальную информацию о видео
        
        Args:
            video_id: ID видео на YouTube
            
        Returns:
            Dict с детальной информацией или None
        """
        if not self.api_key:
            return None
        
        try:
            params = {
                'part': 'snippet,contentDetails,statistics',
                'id': video_id,
                'key': self.api_key
            }
            
            response = httpx.get(
                f"{self.base_url}/videos",
                params=params,
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'items' in data and len(data['items']) > 0:
                    item = data['items'][0]
                    snippet = item['snippet']
                    content_details = item['contentDetails']
                    statistics = item.get('statistics', {})
                    
                    return {
                        'video_id': video_id,
                        'title': snippet.get('title'),
                        'description': snippet.get('description'),
                        'thumbnail': snippet.get('thumbnails', {}).get('maxres', {}).get('url') or 
                                   snippet.get('thumbnails', {}).get('high', {}).get('url'),
                        'channel': snippet.get('channelTitle'),
                        'duration': content_details.get('duration'),
                        'view_count': statistics.get('viewCount'),
                        'like_count': statistics.get('likeCount'),
                        'published_at': snippet.get('publishedAt')
                    }
                return None
            else:
                print(f"YouTube API error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error getting video details: {e}")
            return None
    
    def check_quota(self) -> bool:
        """
        Проверить, работает ли API (простой тест)
        
        Returns:
            True если API доступен
        """
        if not self.api_key:
            return False
        
        try:
            # Простой запрос для проверки квоты
            result = self.search_video("test", max_results=1)
            return result is not None
        except:
            return False
