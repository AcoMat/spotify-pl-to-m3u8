
import sqlite3
from mutagen import File
from mutagen.id3 import ID3
from pathlib import Path
import platformdirs
from util import _normalize_text

def get_database_path():
    """Get the database path using platformdirs."""
    data_dir = Path(platformdirs.user_data_dir("spot-the-local"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "music_index.db"

def _init_database(db_path):
    """Initialize SQLite database with track table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spotify_id TEXT UNIQUE,
            title TEXT,
            album TEXT,
            album_artist TEXT,
            track TEXT,
            year TEXT,
            duration_ms INTEGER,
            path TEXT UNIQUE
        )
    """)
    
    conn.commit()
    return conn


def _get_database_connection():
    """
    Returns:
        sqlite3.Connection: Database connection
    """
    db_path = get_database_path()
    db_exists = db_path.exists()
    
    if not db_exists:
        conn = _init_database(db_path)
        return conn
    else:
        return sqlite3.connect(db_path)

AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".ogg", ".m4a"}

def _find_audio_files(local_library_path):
    """Recursively find audio files in the given directory."""
    if not local_library_path:
        raise ValueError("local_library_path is not defined.")

    for path in Path(local_library_path).rglob("*"):
        if path.suffix.lower() in AUDIO_EXTENSIONS:
            yield path

def _read_metadata(path: Path) -> dict | None:
    """Read metadata from an audio file using mutagen."""
    audio = File(path, easy=True)
    if audio is None:
        return None

    def get(key):
        return audio.get(key, [None])[0]

    album = get("album")
    album_artist = get("albumartist")
    title = get("title")
    track = get("tracknumber")
    year = get("date")
    duration_ms = int(audio.info.length * 1000) if audio.info else None
    spotify_id = None

    # MP3 → ID3 (WOAS)
    if path.suffix.lower() == ".mp3":
        try:
            id3 = ID3(path)
            woas = id3.get("WOAS")
            if woas:
                spotify_id = woas.url.rstrip("/").split("/")[-1]
        except Exception:
            pass

    # M4A / MP4 → ©url
    elif path.suffix.lower() in {".m4a", ".mp4"}:
        url = audio.tags.get("©url", [None])[0] if audio.tags else None
        if url and "spotify.com" in url:
            spotify_id = url.rstrip("/").split("/")[-1]

    # FLAC / OGG / OPUS → URL
    else:
        url = get("url") or get("source")
        if url and "spotify.com" in url:
            spotify_id = url.rstrip("/").split("/")[-1]

    return {
        "spotify_id": spotify_id,
        "title": title,
        "album": album,
        "album_artist": album_artist,
        "track": track,
        "year": year,
        "duration_ms": duration_ms,
        "path": str(path),
    }

def _fill_database_with_tracks(conn, root):
    """Internal function to populate an existing database connection."""
    cursor = conn.cursor()
    
    for file_path in _find_audio_files(root):
        meta = _read_metadata(file_path)
        if meta:
            # Normalize text fields
            meta['spotify_id'] = _normalize_text(meta.get('spotify_id'))
            meta['title'] = _normalize_text(meta.get('title'))
            meta['album'] = _normalize_text(meta.get('album'))
            meta['album_artist'] = _normalize_text(meta.get('album_artist'))
            meta['track'] = _normalize_text(meta.get('track'))
            meta['year'] = _normalize_text(meta.get('year'))
            
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO tracks (spotify_id, title, album, album_artist, track, year, duration_ms, path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    meta['spotify_id'],
                    meta['title'],
                    meta['album'],
                    meta['album_artist'],
                    meta['track'],
                    meta['year'],
                    meta['duration_ms'],
                    meta['path']
                ))
            except sqlite3.Error as e:
                print(f"Error indexing {file_path}: {e}")
    
    conn.commit()

def refresh_db_with_local(root):
    """Insert all local music to the db for forward querys."""
    conn = _get_database_connection()
    _fill_database_with_tracks(conn, root)
    conn.close()

def get_track_from_local(track: dict):
    """
    Query the database for a single track by Spotify ID or by title and album.
    Returns matched track info or None if not found.
    """
    if not track:
        raise ValueError("track is not defined.")

    conn = _get_database_connection()
    cursor = conn.cursor()

    spotify_id = track.get("id") or track.get("spotify_id")
    album = track.get("album") if isinstance(track, dict) else None
    album_name = album.get("name") if isinstance(album, dict) else album
    title = track.get("name") or track.get("title")
    
    rows = []
    
    if spotify_id:
        spotify_id = _normalize_text(spotify_id)
        query = "SELECT * FROM tracks WHERE spotify_id = ?"
        params = (spotify_id,)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
    if len(rows) == 0 and title and album_name:
        title = _normalize_text(title)
        album_name = _normalize_text(album_name)
        query = "SELECT * FROM tracks WHERE title = ? AND album = ?"
        params = (title, album_name)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
    if len(rows) == 0 or len(rows) != 1:
        conn.close()
        return None
    
    row = rows[0]
    conn.close()
    return {
        "spotify_id": row[1],
        "title": row[2],
        "album": row[3],
        "album_artist": row[4],
        "track": row[5],
        "year": row[6],
        "duration_ms": row[7],
        "path": row[8],
    }
        