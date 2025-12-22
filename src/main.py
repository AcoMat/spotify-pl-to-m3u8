import sys
import spotify_api_client
import music_repository
import os

LOCAL_LIBRARY_ROOT = "D:/Music"
OUTPUT_M3U8_BASE_ROOT = "D:/Playlists"

INPUT_PLAYLIST_URL = sys.argv[1] if len(sys.argv) > 1 else None

LOCAL_PATHS = []
#   TODO: Multi-threading for faster processing


def gen_m3u8_file(filename: str, matched_tracks: list[dict], missing_tracks: list[dict]):
    """Generate an M3U8 playlist file."""
    os.makedirs(OUTPUT_M3U8_BASE_ROOT, exist_ok=True)
    filename = OUTPUT_M3U8_BASE_ROOT + "/" + filename
    with open(filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for track in matched_tracks:
            artist = track.get('artist') or track.get('album_artist') or "Unknown Artist"
            title = track.get('title') or track.get('name') or "Unknown Title"
            duration_ms = track.get('duration_ms') or 0
            f.write(f"#EXTINF:{duration_ms // 1000},{artist} - {title}\n")
            relative_path = os.path.relpath(track['path'], OUTPUT_M3U8_BASE_ROOT)
            f.write(f"{relative_path}\n")
        
        if missing_tracks:
            f.write("\n# Missing Tracks\n")
            for track in missing_tracks:
                title = track.get('title') or track.get('name') or "Unknown Title"
                album = track.get('album', {}).get('name') if isinstance(track.get('album'), dict) else track.get('album', 'Unknown Album')
                f.write(f"# {title} - {album}\n")
                


if __name__ == "__main__":
    INPUT_PLAYLIST_URL = "https://open.spotify.com/playlist/6ONi3FyejcKKTuEdwz7Nru?si=e0ee4d4ee7d546ec"
    if INPUT_PLAYLIST_URL is None: raise ValueError("No playlist URL provided.")
    
    music_repository.refresh_db_with_local(LOCAL_LIBRARY_ROOT)
    
    access_token = spotify_api_client.get_access_token()
    playlist_id = INPUT_PLAYLIST_URL.rstrip("/").split("/")[-1].split("?")[0] # URL Format
    playlist_info = spotify_api_client.get_playlist_info(playlist_id, access_token)
    playlist_tracks = spotify_api_client.get_playlist_tracks(playlist_id, access_token)
    
    matched_tracks = []
    missing_tracks = []
    for track in playlist_tracks:
        local_track = music_repository.get_track_from_local(track)
        if local_track:
            if 'artist' not in local_track:
                local_track['artist'] = local_track.get('album_artist')
            matched_tracks.append(local_track)
        else:
            missing_tracks.append(track)
            
    gen_m3u8_file(f"{playlist_info['name']}.m3u8", matched_tracks, missing_tracks)
            
        
            
    
    