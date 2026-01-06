from ytmusicapi import YTMusic

ytmusic = YTMusic()

def get_playlist(playlist_id: str) -> list[dict]:
    """Fetch a playlist info with all tracks from a YouTube Music playlist, flattened for downstream use."""
    tracks: list[dict] = []
    playlist_name = None
    api_res = ytmusic.get_playlist(playlist_id, None, False, 0)

    return {
        "name": api_res.get("title", "Unnamed Playlist"),
        "tracks": api_res.get("tracks", []),
    }