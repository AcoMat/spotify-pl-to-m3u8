import os
import unicodedata
import re
import logging
from typing import List, Dict, Tuple, Optional, Set, Any
from pathlib import Path

import requests
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from rapidfuzz import fuzz


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """
    Normalize text by removing accents, special characters, and common music-related terms.
    
    Args:
        text: The text to normalize
        
    Returns:
        Normalized text string
    """
    if not text:
        return ""
        
    # Convert to lowercase and normalize unicode characters
    text = text.lower()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    
    # Remove special characters
    text = re.sub(r'[&\-\';\.,()]', '', text)
    text = re.sub(r' x ', '', text)
    
    # Remove common music-related terms
    terms_to_remove = [r'\bremaster\b', r'\bremastered\b', r'\bversion\b', 
                      r'\bedition \b', r'\[.*?\]', r'\bfeat\b', r'\bft\.\b']
    for term in terms_to_remove:
        text = re.sub(term, '', text)
    
    # Remove all spaces
    text = text.replace(" ", "")
    return text


def create_index(base_directory: str) -> List[Dict[str, str]]:
    """
    Create an index of all MP3 files in the directory with their metadata.
    
    Args:
        base_directory: Path to the music library
        
    Returns:
        List of dictionaries containing metadata for each MP3 file
    """
    index = []
    base_path = Path(base_directory)
    
    logger.info(f"Creating index from {base_directory}")
    
    for file_path in base_path.glob('**/*.mp3'):
        try:
            relative_path = str(file_path.relative_to(base_path))
            audio = ID3(file_path)
            
            file_artist = normalize_text(audio.get('TPE1', [None]).text[0] if audio.get('TPE1', None) else '')
            file_song = normalize_text(audio.get('TIT2', [None]).text[0] if audio.get('TIT2', None) else '')
            file_album = normalize_text(audio.get('TALB', [None]).text[0] if audio.get('TALB', None) else '')
            
            index.append({
                'artist': file_artist,
                'song': file_song,
                'album': file_album,
                'path': relative_path
            })
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
    
    logger.info(f"Indexed {len(index)} MP3 files")
    return index


def find_mp3_file(index: List[Dict[str, str]], artist: str, song: str, album: str) -> Optional[str]:
    """
    Find the best matching MP3 file in the index based on artist, song and album.
    
    Args:
        index: List of dictionaries containing metadata for each MP3 file
        artist: Artist name to search for
        song: Song title to search for
        album: Album name to search for
        
    Returns:
        The path to the best matching MP3 file, or None if no match found
    """
    threshold = 86
    search_string = f"{artist}{song}{album}"
    
    # First try exact match with combined string
    for entry in index:
        entry_string = f"{entry['artist']}{entry['song']}{entry['album']}"
        combined_score = fuzz.ratio(search_string, entry_string)
        
        if combined_score >= threshold:
            return entry['path']
    
    # Then try with song and album match
    for entry in index:
        song_score = fuzz.ratio(song, entry['song'])
        album_score = fuzz.ratio(album, entry['album'])
        
        if song_score >= threshold and album_score >= threshold:
            return entry['path']
    
    # Finally try with artist and song match
    for entry in index:
        artist_score = fuzz.ratio(artist, entry['artist'])
        song_score = fuzz.ratio(song, entry['song'])
        
        if artist_score >= threshold and song_score >= threshold:
            return entry['path']
    
    return None


def search_songs_from_track_list(base_directory: str, tracks: List[str]) -> Tuple[List[str], List[str]]:
    """
    Search for MP3 files in the music library that match the tracks list.
    
    Args:
        base_directory: Path to the music library
        tracks: List of tracks in format "artist --- song --- album"
        
    Returns:
        Tuple containing (list of found paths, list of not found tracks)
    """
    index = create_index(base_directory)
    results = []
    not_found = []
    
    total_tracks = len(tracks)
    logger.info(f"Searching for {total_tracks} tracks")
    
    for i, track in enumerate(tracks, 1):
        if i % 10 == 0:
            logger.info(f"Processed {i}/{total_tracks} tracks")
            
        try:
            track_parts = track.split(' --- ', 2)
            if len(track_parts) != 3:
                logger.warning(f"Invalid track format: {track}")
                continue
                
            artist, song, album = map(lambda x: normalize_text(x.strip()), track_parts)
            
            result = find_mp3_file(index, artist, song, album)
            if result:
                results.append(result)
            else:
                not_found.append(f"Not found: Artist: {track_parts[0]}, Song: {track_parts[1]}, Album: {track_parts[2]}")
        except Exception as e:
            logger.error(f"Error processing track '{track}': {e}")
            
    logger.info(f"Found {len(results)}/{total_tracks} tracks")
    return results, not_found


def gen_m3u8_playlist(base_directory: str, found_songs: List[str], 
                     not_found_songs: List[str], output_dir: str, 
                     playlist_name: str) -> str:
    """
    Generate an M3U8 playlist file from the list of found and not found songs.
    
    Args:
        base_directory: Path to the music library
        found_songs: List of paths to found MP3 files
        not_found_songs: List of descriptions of songs that weren't found
        output_dir: Directory to save the playlist
        playlist_name: Name of the playlist
        
    Returns:
        Path to the generated playlist file
    """
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    
    # Sanitize playlist name to be filesystem safe
    safe_playlist_name = re.sub(r'[^\w\s-]', '', playlist_name).strip()
    safe_playlist_name = re.sub(r'[-\s]+', '-', safe_playlist_name)
    
    output_file = output_dir_path / f"{safe_playlist_name}.m3u8"
    
    with open(output_file, 'w', encoding='utf-8') as playlist_file:
        playlist_file.write("#EXTM3U\n")
        
        for mp3_path in found_songs:
            full_path = os.path.join(base_directory, mp3_path)
            try:
                audio = ID3(full_path)
                duration = int(MP3(full_path).info.length)
                
                title = audio.get('TIT2', [None]).text[0] if audio.get('TIT2', None) else 'Unknown Title'
                artist = audio.get('TPE1', [None]).text[0] if audio.get('TPE1', None) else 'Unknown Artist'
                
                playlist_file.write(f"#EXTINF:{duration},{artist} - {title}\n")
                playlist_file.write(mp3_path + '\n')
            except Exception as e:
                logger.error(f"Error adding {mp3_path} to playlist: {e}")
        
        # Add comments for songs that weren't found
        if not_found_songs:
            playlist_file.write("\n# Songs not found:\n")
            for item in not_found_songs:
                playlist_file.write(f"# {item}\n")
    
    logger.info(f"Playlist generated at: {output_file}")
    return str(output_file)


class SpotifyClient:
    """Class to handle Spotify API interactions"""
    
    def __init__(self, client_id: str, client_secret: str):
        """
        Initialize the Spotify client.
        
        Args:
            client_id: Spotify API client ID
            client_secret: Spotify API client secret
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = self._get_access_token()
        
    def _get_access_token(self) -> str:
        """
        Get an access token from Spotify API.
        
        Returns:
            Access token string
        
        Raises:
            RuntimeError: If token request fails
        """
        url = 'https://accounts.spotify.com/api/token'
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            response_data = response.json()
            return response_data['access_token']
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get Spotify access token: {e}")
            raise RuntimeError("Failed to authenticate with Spotify API") from e
            
    def get_playlist_tracks(self, playlist_id: str) -> List[Dict[str, Any]]:
        """
        Get all tracks from a Spotify playlist.
        
        Args:
            playlist_id: Spotify playlist ID
            
        Returns:
            List of tracks from the playlist
            
        Raises:
            RuntimeError: If playlist request fails
        """
        url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
        headers = {'Authorization': f'Bearer {self.access_token}'}
        limit = 100  # Maximum allowed by Spotify API
        offset = 0
        all_tracks = []
        
        try:
            while True:
                params = {'limit': limit, 'offset': offset}
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                tracks = data['items']
                all_tracks.extend(tracks)
                
                if len(tracks) < limit:
                    break
                    
                offset += limit
                
            return all_tracks
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get playlist tracks: {e}")
            raise RuntimeError(f"Failed to fetch tracks from playlist {playlist_id}") from e
            
    def get_playlist_name(self, playlist_id: str) -> str:
        """
        Get the name of a Spotify playlist.
        
        Args:
            playlist_id: Spotify playlist ID
            
        Returns:
            Name of the playlist
            
        Raises:
            RuntimeError: If playlist request fails
        """
        url = f'https://api.spotify.com/v1/playlists/{playlist_id}'
        headers = {'Authorization': f'Bearer {self.access_token}'}
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            return data['name']
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get playlist name: {e}")
            raise RuntimeError(f"Failed to fetch playlist information for {playlist_id}") from e
            
    @staticmethod
    def extract_playlist_id(spotify_url: str) -> str:
        """
        Extract playlist ID from a Spotify URL.
        
        Args:
            spotify_url: Spotify playlist URL
            
        Returns:
            Playlist ID
            
        Raises:
            ValueError: If the URL is invalid
        """
        match = re.search(r'playlist/([a-zA-Z0-9]+)', spotify_url)
        if match:
            return match.group(1)
        raise ValueError("Invalid Spotify URL. Could not extract playlist ID.")


def format_track_info(track_data: Dict[str, Any]) -> str:
    """
    Format track information from Spotify API response.
    
    Args:
        track_data: Track data from Spotify API
        
    Returns:
        Formatted string "artist --- song --- album"
    """
    if not track_data.get('track'):
        return ""
        
    track_info = track_data['track']
    artists = ', '.join(artist['name'] for artist in track_info['artists'])
    song_name = track_info['name']
    album_name = track_info['album']['name']
    
    return f"{artists} --- {song_name} --- {album_name}"