
import re
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
            local_id INTEGER PRIMARY KEY AUTOINCREMENT,
            online_id TEXT UNIQUE,
            title TEXT,
            album_name TEXT,
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

    album_name = get("album")
    album_artist = get("albumartist")
    title = get("title")
    track = get("tracknumber")
    year = get("date")
    duration_ms = int(audio.info.length * 1000) if audio.info else None
    online_id = None

    # MP3 → ID3 (WOAS)
    if path.suffix.lower() == ".mp3":
        try:
            id3 = ID3(path)
            woas = id3.get("WOAS")
            if woas:
                online_id = woas.url.rstrip("/").split("/")[-1]
        except Exception:
            pass

    # M4A / MP4 → ©url
    elif path.suffix.lower() in {".m4a", ".mp4"}:
        url = audio.tags.get("©url", [None])[0] if audio.tags else None
        if url and "spotify.com" in url:
            online_id = url.rstrip("/").split("/")[-1]

    # FLAC / OGG / OPUS → URL
    else:
        url = get("url") or get("source")
        if url and "spotify.com" in url:
            online_id = url.rstrip("/").split("/")[-1]

    return {
        "online_id": online_id,
        "title": title,
        "album_name": album_name,
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
            meta['online_id'] = meta.get('online_id')
            meta['title'] = _normalize_text(meta.get('title'))
            meta['album_name'] = _normalize_text(meta.get('album_name'))
            meta['album_artist'] = _normalize_text(meta.get('album_artist'))
            meta['track'] = _normalize_text(meta.get('track'))
            meta['year'] = _normalize_text(meta.get('year'))
            
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO tracks (online_id, title, album_name, album_artist, track, year, duration_ms, path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    meta['online_id'],
                    meta['title'],
                    meta['album_name'],
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
    Query the database for a single track by multiple strategies.
    Returns matched track info or None if not found.
    """
    if not track:
        raise ValueError("track is not defined.")

    conn = _get_database_connection()
    cursor = conn.cursor()

    strategies = [
        lambda: _search_by_online_id(cursor, track),
        lambda: _search_by_title_album(cursor, track),
        lambda: _search_by_approx(cursor, track),
    ]
    
    for strategy in strategies:
        result = strategy()
        if result:
            return result
    
    conn.close()
    return None

def _search_by_online_id(cursor, track):
    online_id = track.get("id")
    query = "SELECT * FROM tracks WHERE online_id = ?"
    cursor.execute(query, (online_id,))
    res = cursor.fetchall()
    if len(res) != 1:
        return None
    row = res[0]
    
    #simple validation with title match
    title = _normalize_text(track.get("name") or track.get("title"))
    if title != row[2]:
        return None

    return {
        "online_id": row[1],
        "title": row[2],
        "album_name": row[3],
        "album_artist": row[4],
        "track": row[5],
        "year": row[6],
        "duration_ms": row[7],
        "path": row[8],
    }

def _search_by_title_album(cursor, track):
    title = track.get("name") or track.get("title")
    title = _normalize_text(title)
    album_name = _normalize_text(track.get("album_name"))
    query = "SELECT * FROM tracks WHERE title = ? AND album_name = ?"
    cursor.execute(query, (title, album_name))
    res = cursor.fetchall()
    if len(res) != 1:
        return None
    row = res[0]
    return {
        "online_id": row[1],
        "title": row[2],
        "album_name": row[3],
        "album_artist": row[4],
        "track": row[5],
        "year": row[6],
        "duration_ms": row[7],
        "path": row[8],
    }

def _search_by_approx(cursor, track):
    title = _normalize_text(track.get('name') or track.get('title'))
    
    if title is None:
        return None
    
    # Single comprehensive pattern to remove content in parentheses/brackets
    # Matches: years, dates, remaster terms, featuring, performance types, etc.
    title = re.sub(
        r'[\(\[]\s*(?:'
        r'\d{4}|'  # years
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|'  # dates
        r'(?:feat\.?|ft\.?|featuring|with|con|w/).*?|'  # featuring
        r'(?:live|acoustic|ac[uú]stic[ao]?|radio edit|unplugged|en vivo|'
        r'instrumental|a cappella|remix|remezcla|single|original mix|extended|oficial).*?|'  # performance types
        r'remaster(?:ed|izado)?.*?'  # remaster variations
        r')\s*[\)\]]',
        '', title, flags=re.IGNORECASE
    )
    # Remove standalone years and common edition terms
    title = re.sub(
        r'\b(?:\d{4}|remaster(?:ed|izado)?|deluxe|edition|edici[oó]n|version|versi[oó]n|'
        r'bonus tracks?|pistas adicionales?|expanded?|ampliado?|anniversary|aniversario)\b',
        '', title, flags=re.IGNORECASE
    )
    # Clean up empty brackets and extra whitespace/dashes
    title = re.sub(r'[\(\[]\s*[\)\]]|[-–—]\s*$', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    # Normalize artist and extract year from release_date
    artist = _normalize_text(track.get('artist')) if track.get('artist') else None
    release_date = track.get('release_date')
    year = release_date[:4] if release_date and len(release_date) >= 4 else None
    
    # Build query with approximate matching
    query = """
        SELECT * FROM tracks 
        WHERE title LIKE ? 
    """
    params = [f"%{title}%"]
    
    # Add optional artist matching
    if artist:
        query += " AND (album_artist LIKE ? OR album_artist IS NULL)"
        params.append(f"%{artist}%")
    
    duration_ms = track.get('duration_ms')
    # Add duration matching with ±5 seconds tolerance
    #if duration_ms:
    #    tolerance = 5000  # 5 seconds in milliseconds
    #    query += " AND (duration_ms BETWEEN ? AND ? OR duration_ms IS NULL)"
    #    params.extend([duration_ms - tolerance, duration_ms + tolerance])
    
    # Add year matching with ±1 year tolerance
    if year:
        query += " AND (year LIKE ? OR year LIKE ? OR year LIKE ? OR year IS NULL)"
        params.extend([f"%{int(year)-1}%", f"%{year}%", f"%{int(year)+1}%"])
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    
    if len(results) != 1:
        return None
    
    row = results[0]
    return {
        "online_id": row[1],
        "title": row[2],
        "album_name": row[3],
        "album_artist": row[4],
        "track": row[5],
        "year": row[6],
        "duration_ms": row[7],
        "path": row[8],
    }
    