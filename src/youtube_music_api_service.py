from ytmusicapi import YTMusic

ytmusic = YTMusic()

def get_playlist(playlist_id: str) -> list[dict]:
    """Fetch a playlist info with all tracks from a YouTube Music playlist, flattened for downstream use."""
    tracks: list[dict] = []
    playlist_name = None
    total_tracks = None

    while total_tracks is None or total_tracks < len(tracks):
        api_res = ytmusic.get_playlist(playlist_id)
        if total_tracks is None or playlist_name is None:
            total_tracks = api_res.get('trackCount', 0)
            playlist_name = api_res.get('title')
        for item in api_res.get('tracks', []):
            tracks.append({
                "id": item.get("videoId"),
                "title": item.get("title"),
                "album": item.get("album", {}).get("name"),
                "release_date": item.get("album", {}).get("year"),
                "artist": ", ".join(artist.get("name") for artist in item.get("artists", [])),
                "duration_ms": int(item.get("duration_seconds", 0)) * 1000,
            })

    return {
        "name": playlist_name,
        "tracks": tracks,
    }