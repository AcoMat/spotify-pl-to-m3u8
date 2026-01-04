import os
import argparse
from pathlib import Path

from platformdirs import user_music_dir

import music_repository
import spotify_api_service
import youtube_music_api_service

# Default to the OS user music directory provided by platformdirs
DEFAULT_MUSIC_DIR = Path(user_music_dir())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an M3U8 playlist from a Spotify or YouTube Music playlist using local files.")
    parser.add_argument("playlist_url", help="Spotify or YouTube Music playlist URL")
    parser.add_argument("--music-dir", type=Path, default=DEFAULT_MUSIC_DIR, help="Path to your local music library. Defaults to the OS user music directory.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_MUSIC_DIR, help="Directory to write the generated M3U8 file. Defaults to the OS user music directory.")
    return parser.parse_args()


def _gen_m3u8_file(filename: str, matched_tracks: list[dict], missing_tracks: list[dict], output_base_root: Path):
    """Generate an M3U8 playlist file."""
    output_base_root.mkdir(parents=True, exist_ok=True)
    filename = output_base_root / filename
    with open(filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for track in matched_tracks:
            artist = track.get('artist') or track.get('album_artist') or "Unknown Artist"
            title = track.get('title') or track.get('name') or "Unknown Title"
            duration_ms = track.get('duration_ms') or 0
            f.write(f"#EXTINF:{duration_ms // 1000},{artist} - {title}\n")
            relative_path = os.path.relpath(track['path'], output_base_root)
            f.write(f"{relative_path}\n")
        
        if missing_tracks:
            f.write("\n# Missing Tracks\n")
            for track in missing_tracks:
                title = track.get('title') or track.get('name') or "Unknown Title"
                album = track.get('album', {}).get('name') if isinstance(track.get('album'), dict) else track.get('album', 'Unknown Album')
                f.write(f"# {title} - {album}\n")                

def main():
    args = _parse_args()

    music_repository.refresh_db_with_local(args.music_dir)

    input_playlist_url = args.playlist_url.lower()
    
    playlist = None
    
    if "spotify.com" in input_playlist_url:
        playlist_id = args.playlist_url.rstrip("/").split("/")[-1].split("?")[0] 
        playlist = spotify_api_service.get_playlist(playlist_id)
    elif "music.youtube.com" in input_playlist_url or ("youtube.com" in input_playlist_url and "list=" in input_playlist_url):
        playlist_id = args.playlist_url.split("list=")[-1].split("&")[0]  # Extract playlist ID from URL
        playlist = youtube_music_api_service.get_playlist(playlist_id)
    else:
        raise ValueError("Unsupported playlist URL. Provide a Spotify or YouTube Music playlist URL.")

    matched_tracks = []
    missing_tracks = []
    for track in playlist.get('tracks', []):
        local_track = music_repository.get_track_from_local(track)
        if local_track:
            if 'artist' not in local_track:
                local_track['artist'] = local_track.get('album_artist')
            matched_tracks.append(local_track)
        else:
            missing_tracks.append(track)
            
    _gen_m3u8_file(f"{playlist['name']}.m3u8", matched_tracks, missing_tracks, args.output_dir)

if __name__ == "__main__":
    main()