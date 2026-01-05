import os
import sys
import argparse
from pathlib import Path

from platformdirs import user_music_dir

import music_repository
import spotify_service
import yt_music_service

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
                album = track.get('album_name', 'Unknown Album')
                f.write(f"# {title} - {album}\n")                

def main():
    args = _parse_args()

    # Validate playlist URL is provided
    if not args.playlist_url or not args.playlist_url.strip():
        print("Error: Playlist URL is required.", file=sys.stderr)
        sys.exit(1)

    # Validate music directory exists
    if not args.music_dir.exists():
        print(f"Error: Music directory does not exist: {args.music_dir}", file=sys.stderr)
        sys.exit(1)
    
    if not args.music_dir.is_dir():
        print(f"Error: Music directory path is not a directory: {args.music_dir}", file=sys.stderr)
        sys.exit(1)

    # Validate output directory exists or can be created
    if not args.output_dir.exists():
        try:
            args.output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Error: Cannot create output directory {args.output_dir}: {e}", file=sys.stderr)
            sys.exit(1)
    
    if not args.output_dir.is_dir():
        print(f"Error: Output directory path is not a directory: {args.output_dir}", file=sys.stderr)
        sys.exit(1)

    music_repository.refresh_db_with_local(args.music_dir)

    input_playlist_url = args.playlist_url.strip().lower()
    
    playlist = None
    
    if "spotify.com" in input_playlist_url:
        try:
            playlist_id = args.playlist_url.rstrip("/").split("/")[-1].split("?")[0]
            if not playlist_id:
                print("Error: Could not extract playlist ID from Spotify URL.", file=sys.stderr)
                sys.exit(1)
            playlist = spotify_service.get_playlist(playlist_id)
        except Exception as e:
            print(f"Error: Failed to retrieve Spotify playlist: {e}", file=sys.stderr)
            sys.exit(1)
    elif "music.youtube.com" in input_playlist_url or ("youtube.com" in input_playlist_url and "list=" in input_playlist_url):
        try:
            if "list=" not in args.playlist_url:
                print("Error: Could not find 'list=' parameter in YouTube URL.", file=sys.stderr)
                sys.exit(1)
            playlist_id = args.playlist_url.split("list=")[-1].split("&")[0]
            if not playlist_id:
                print("Error: Could not extract playlist ID from YouTube URL.", file=sys.stderr)
                sys.exit(1)
            playlist = yt_music_service.get_playlist(playlist_id)
        except Exception as e:
            print(f"Error: Failed to retrieve YouTube Music playlist: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Error: Unsupported playlist URL. Please provide a Spotify or YouTube Music playlist URL.", file=sys.stderr)
        sys.exit(1)

    # Validate playlist was retrieved successfully
    if not playlist:
        print("Error: Failed to retrieve playlist data.", file=sys.stderr)
        sys.exit(1)
    
    if 'name' not in playlist:
        print("Error: Playlist data is missing required 'name' field.", file=sys.stderr)
        sys.exit(1)

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