import requests
import os

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")

BASE_PLAYLIST_URL = "https://api.spotify.com/v1/playlists/"

def get_access_token():
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in environment")

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

def get_playlist_tracks(playlist_id, access_token):
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    params = {"fields": "items(track.album.name,track.album.release_date,track.track_number,track.duration_ms,track.name,track.id)"}
    response = requests.get(
        f"{BASE_PLAYLIST_URL}{playlist_id}/tracks",
        headers=headers,
        params=params,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()