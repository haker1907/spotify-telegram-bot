
import asyncio
import json
import os
import sys
import httpx
from bs4 import BeautifulSoup

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.spotify_service import SpotifyService

async def debug_artist_tracks():
    artist_url = "https://open.spotify.com/artist/6OTMjaRQ9kxdwoPRYTmyOM" 
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    }

    print(f"\n==================================================")
    print(f"TEST 1: Artist Embed (Current Method)")
    print(f"==================================================")
    
    service = SpotifyService()
    parsed = service.parse_spotify_url(artist_url)
    
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        embed_url = f"https://open.spotify.com/embed/artist/{parsed['id']}"
        print(f"Fetching {embed_url}...")
        resp = await client.get(embed_url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        script = soup.find('script', {'id': '__NEXT_DATA__'})
        
        track_id_to_check = None
        
        if script:
            data = json.loads(script.string)
            entity = data.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity', {})
            print("\n--- Current Service Output ---")
            info = await service.get_artist_info(artist_url)
            if info and info.get('tracks'):
                t0 = info['tracks'][0]
                result = f"Service Track 0 Image: {t0.get('image')}"
                print(result)
                with open("result.txt", "w") as f:
                    f.write(result)
            else:
                with open("result.txt", "w") as f:
                    f.write("No tracks found")
            tracks = entity.get('trackList', [])
            print(f"Found {len(tracks)} tracks")
            if tracks:
                t0 = tracks[0]
                print(f"First Track: {t0.get('title')} ({t0.get('uid')})")
                print(f"Has image/album? {'album' in t0 or 'visuals' in t0}")
                if 'uri' in t0:
                    track_id_to_check = t0['uri'].split(':')[-1]

        print(f"\n==================================================")
        print(f"TEST 2: Desktop Artist Page (New Potential Source)")
        print(f"==================================================")
        # Try scraping main page instead of embed
        print(f"Fetching {artist_url}...")
        resp = await client.get(artist_url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Desktop page structure is often different
        # Look for Spotify.Entity or __NEXT_DATA__ or similar
        script = soup.find('script', {'id': '__NEXT_DATA__'})
        if script:
            print("Found __NEXT_DATA__ on desktop page")
            data = json.loads(script.string)
            # Dump keys to explore
            print(f"Root keys: {list(data.keys())}")
            props = data.get('props', {}).get('pageProps', {})
            print(f"PageProps keys: {list(props.keys())}")
            
            # Look for hydration state
            if 'state' in props:
                print(f"State keys: {list(props['state'].keys())}")
            if 'initialState' in props:
                print(f"InitialState keys: {list(props['initialState'].keys())}")
            if 'hydrationData' in props:
                 print(f"HydrationData keys: {list(props['hydrationData'].keys())}")
        
        # Check for Spotify.Entity variable often used in older SPA
        scripts = soup.find_all('script')
        for s in scripts:
            if s.string and 'Spotify.Entity' in s.string:
                print("Found Spotify.Entity script")
                
        print(f"\n==================================================")
        print(f"TEST 3: Single Track Embed (Fallback Strategy)")
        print(f"==================================================")
        
        if track_id_to_check:
            track_embed_url = f"https://open.spotify.com/embed/track/{track_id_to_check}"
            print(f"Fetching {track_embed_url}...")
            resp = await client.get(track_embed_url)
            soup = BeautifulSoup(resp.text, 'html.parser')
            script = soup.find('script', {'id': '__NEXT_DATA__'})
            if script:
                data = json.loads(script.string)
                entity = data.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity', {})
                print(f"Track Entity keys: {list(entity.keys())}")
                if 'coverArt' in entity:
                    print(f"Found coverArt: {entity['coverArt'].get('sources', [{}])[0].get('url')}")
                elif 'visualIdentity' in entity:
                     print(f"Found visualIdentity: {entity['visualIdentity']}")
                     if 'image' in entity['visualIdentity']:
                         print(f"visualIdentity.image: {entity['visualIdentity']['image'][0].get('url') if isinstance(entity['visualIdentity']['image'], list) else entity['visualIdentity']['image'].get('url')}")
                elif 'visuals' in entity:
                     print(f"Found locals (visuals): {entity['visuals']}")
                elif 'album' in entity:
                    print(f"Found album: {entity['album'].get('images', [{}])[0].get('url')}")
                else:
                    print("No cover art found in track embed either")
        else:
            print("No track ID to test")

if __name__ == "__main__":
    asyncio.run(debug_artist_tracks())
