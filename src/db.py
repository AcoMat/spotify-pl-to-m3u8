
import sqlite3
from mutagen import File
from mutagen.id3 import ID3
from pathlib import Path
import platformdirs

def get_database_path():
    """Get the database path using platformdirs."""
    data_dir = Path(platformdirs.user_data_dir("spot-the-local", "spot-the-local"))
    data_dir.mkdir(parents=True, exist_ok=True)
    print( f"Database directory: {data_dir}" )
    return data_dir / "music_index.db"

def init_database(db_path):
    """Initialize SQLite database with music table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id TEXT,
            title TEXT,
            album TEXT,
            album_artist TEXT,
            track TEXT,
            year TEXT,
            duration INTEGER,
            path TEXT UNIQUE
        )
    """)
    
    conn.commit()
    return conn

AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".ogg", ".m4a"}

def find_audio_files(local_library_path):
    if not local_library_path:
        raise ValueError("local_library_path is not defined.")

    for path in Path(local_library_path).rglob("*"):
        if path.suffix.lower() in AUDIO_EXTENSIONS:
            yield path

def read_metadata(path: Path):
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
    duration = int(audio.info.length) if audio.info else None
    track_id = None

    # MP3 → ID3 (WOAS)
    if path.suffix.lower() == ".mp3":
        try:
            id3 = ID3(path)
            woas = id3.get("WOAS")
            if woas:
                track_id = woas.url.rstrip("/").split("/")[-1]
        except Exception:
            pass

    # M4A / MP4 → ©url
    elif path.suffix.lower() in {".m4a", ".mp4"}:
        url = audio.tags.get("©url", [None])[0] if audio.tags else None
        if url and "spotify.com" in url:
            track_id = url.rstrip("/").split("/")[-1]

    # FLAC / OGG / OPUS → URL
    else:
        url = get("url") or get("source")
        if url and "spotify.com" in url:
            track_id = url.rstrip("/").split("/")[-1]

    return {
        "track_id": track_id,
        "title": title,
        "album": album,
        "album_artist": album_artist,
        "track": track,
        "year": year,
        "duration": duration,
        "path": str(path),
    }

def index_library_to_sqlite(root):
    """Index all music files in the library to SQLite."""
    db_path = get_database_path()
    conn = init_database(db_path)
    cursor = conn.cursor()
    
    for file_path in find_audio_files(root):
        meta = read_metadata(file_path)
        if meta:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO tracks (track_id, title, album, album_artist, track, year, duration, path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    meta['track_id'],
                    meta['title'],
                    meta['album'],
                    meta['album_artist'],
                    meta['track'],
                    meta['year'],
                    meta['duration'],
                    meta['path']
                ))
            except sqlite3.Error as e:
                print(f"Error indexing {file_path}: {e}")
    
    conn.commit()
    conn.close()

def query_library(track):
    """
    Query the indexed library.
    """
    
    if not track:
        raise ValueError("track is not defined.")
    
    db_path = get_database_path()
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}. Run index_library_to_sqlite first.")
    
    if  track.get('track_id') is not None:
        query = "SELECT * FROM tracks WHERE track_id = ?"
        params = (track['track_id'],)
    else:
        query = "SELECT * FROM tracks WHERE title = ? AND album = ?"
        params = (track['name'], track['album']['name'])
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    
    return results
        