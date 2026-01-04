import requests
import os

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")

BASE_PLAYLIST_URL = "https://api.spotify.com/v1/playlists/"

def get_access_token():
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in environment variables")

    try:
        auth_response = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=(CLIENT_ID, CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        auth_response.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError("Failed to obtain access token") from e

    try:
        auth_response_data = auth_response.json()
        return auth_response_data['access_token']
    except (ValueError, KeyError) as e:
        raise RuntimeError("Unexpected response from Spotify token endpoint") from e

def get_playlist_info(playlist_id: str, access_token: str):
    """
    Fetch basic information about a Spotify playlist.
    :param playlist_id: The Spotify ID of the playlist.
    :param access_token: A valid Spotify API access token.
    :return: A dictionary with playlist information.
    """
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    params = {
        'fields': 'name,tracks.total,href,external_urls.spotify'
    }
    try:
        response = requests.get(
            f"{BASE_PLAYLIST_URL}{playlist_id}",
            headers=headers,
            params=params,
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError("Failed to fetch playlist info from Spotify") from e

    return response.json()

def get_playlist_tracks(playlist_id: str, access_token: str) -> list[dict]:
    """Fetch all tracks from a Spotify playlist, flattened for downstream use."""
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    params = {
        "fields": (
            "total,items("
            "track.id,track.name,track.duration_ms,track.track_number,"
            "track.album(name,release_date),"
            "track.artists(name)"
            ")"
        )
    }

    tracks: list[dict] = []
    total_tracks = None

    while total_tracks is None or len(tracks) < total_tracks:
        if tracks:
            params['offset'] = len(tracks)
        response = requests.get(
            f"{BASE_PLAYLIST_URL}{playlist_id}/tracks",
            headers=headers,
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        chunk = response.json()
        if total_tracks is None:
            total_tracks = chunk.get('total', 0)

        for item in chunk.get('items', []):
            tracks.append({
                "id": item.get('track').get("id"),
                "title": item.get('track').get("name"),
                "album": item.get('track').get('album').get("name"),
                "release_date": item.get('track').get('album').get("release_date"),
                "artist": ", ".join(a.get('name') for a in item.get('track').get('artists') if a.get('name')) or None,
                "duration_ms": item.get('track').get("duration_ms"),
                "track_number": item.get('track').get("track_number"),
            })

    return tracks

def get_playlist(playlist_id: str) -> dict:
    """Fetch complete playlist information including tracks from a Spotify playlist URL."""
    access_token = get_access_token()
    playlist = get_playlist_info(playlist_id, access_token)
    playlist_tracks = get_playlist_tracks(playlist_id, access_token)
    playlist['tracks'] = playlist_tracks
    return playlist
    