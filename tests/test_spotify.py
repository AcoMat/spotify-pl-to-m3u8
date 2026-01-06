from unittest.mock import patch, MagicMock
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import spotify_service

# Run integration tests with: pytest -m integration
# Skip integration tests with: pytest -m "not integration"


def test_smoke_get_playlist():
    """Smoke test: Verify basic get_playlist functionality works end-to-end."""
    playlist_id = "3cEYpjA9oz9GiPac4AsH4n"
    
    mock_auth_response = MagicMock()
    mock_auth_response.json.return_value = {"access_token": "test_token"}
    
    mock_info_response = MagicMock()
    mock_info_response.json.return_value = {
        "name": "Test Playlist",
        "href": "https://api.spotify.com/v1/playlists/3cEYpjA9oz9GiPac4AsH4n",
        "external_urls": {"spotify": "https://open.spotify.com/playlist/3cEYpjA9oz9GiPac4AsH4n"},
        "tracks": {"total": 2}
    }
    
    mock_tracks_response = MagicMock()
    mock_tracks_response.json.return_value = {
        "total": 2,
        "items": [
            {
                "track": {
                    "id": "track1",
                    "name": "Song 1",
                    "duration_ms": 200000,
                    "track_number": 1,
                    "album": {"name": "Album 1", "release_date": "2024-01-01"},
                    "artists": [{"name": "Artist 1"}]
                }
            },
            {
                "track": {
                    "id": "track2",
                    "name": "Song 2",
                    "duration_ms": 180000,
                    "track_number": 2,
                    "album": {"name": "Album 2", "release_date": "2024-02-01"},
                    "artists": [{"name": "Artist 2"}]
                }
            }
        ]
    }
    
    with patch('spotify_service.requests.post', return_value=mock_auth_response):
        with patch('spotify_service.requests.get') as mock_get:
            mock_get.side_effect = [mock_info_response, mock_tracks_response]
            
            result = spotify_service.get_playlist(playlist_id)
            
            assert result["name"] == "Test Playlist"
            assert len(result["tracks"]) == 2
            assert result["tracks"][0]["title"] == "Song 1"
            assert result["tracks"][1]["id"] == "track2"


def test_get_playlist_tracks_with_pagination():
    """Test that get_playlist_tracks correctly handles pagination across multiple API calls."""
    mock_access_token = "mock_token_12345"
    playlist_id = "3cEYpjA9oz9GiPac4AsH4n"
    
    # Mock responses for paginated API calls
    first_response = {
        "total": 150,
        "items": [
            {
                "track": {
                    "id": f"track_{i}",
                    "name": f"Song {i}",
                    "duration_ms": 180000 + i * 1000,
                    "track_number": i,
                    "album": {"name": f"Album {i}", "release_date": "2024-01-01"},
                    "artists": [{"name": f"Artist {i}"}]
                }
            }
            for i in range(100)
        ]
    }
    
    second_response = {
        "total": 150,
        "items": [
            {
                "track": {
                    "id": f"track_{i}",
                    "name": f"Song {i}",
                    "duration_ms": 180000 + i * 1000,
                    "track_number": i,
                    "album": {"name": f"Album {i}", "release_date": "2024-01-01"},
                    "artists": [{"name": f"Artist {i}"}]
                }
            }
            for i in range(100, 150)
        ]
    }
    
    with patch('spotify_service.requests.get') as mock_get:
        # Configure mock to return different responses for each call
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: first_response),
            MagicMock(status_code=200, json=lambda: second_response)
        ]
        
        tracks = spotify_service.get_playlist_tracks(playlist_id, mock_access_token)
        
        # Verify pagination worked correctly
        assert len(tracks) == 150
        assert tracks[0]["id"] == "track_0"
        assert tracks[99]["id"] == "track_99"
        assert tracks[149]["id"] == "track_149"
        
        # Verify offset parameter was used in second call
        assert mock_get.call_count == 2
        second_call_params = mock_get.call_args_list[1][1]['params']
        assert second_call_params['offset'] == 100


def test_get_access_token_error_handling():
    """Test that get_access_token raises appropriate errors when API fails."""
    
    # Test missing credentials - need to reload module to pick up env changes
    with patch.dict(os.environ, {}, clear=True):
        # Force re-evaluation of CLIENT_ID and CLIENT_SECRET
        with patch('spotify_service.CLIENT_ID', None):
            with patch('spotify_service.CLIENT_SECRET', None):
                with pytest.raises(RuntimeError, match="SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set"):
                    spotify_service.get_access_token()
    
    # Test API request failure
    with patch.dict(os.environ, {'SPOTIFY_CLIENT_ID': 'test_id', 'SPOTIFY_CLIENT_SECRET': 'test_secret'}):
        with patch('spotify_service.CLIENT_ID', 'test_id'):
            with patch('spotify_service.CLIENT_SECRET', 'test_secret'):
                with patch('spotify_service.requests.post') as mock_post:
                    import requests
                    mock_post.side_effect = requests.RequestException("Network error")
                    
                    with pytest.raises(RuntimeError, match="Failed to obtain access token"):
                        spotify_service.get_access_token()
    
    # Test invalid JSON response
    with patch.dict(os.environ, {'SPOTIFY_CLIENT_ID': 'test_id', 'SPOTIFY_CLIENT_SECRET': 'test_secret'}):
        with patch('spotify_service.CLIENT_ID', 'test_id'):
            with patch('spotify_service.CLIENT_SECRET', 'test_secret'):
                with patch('spotify_service.requests.post') as mock_post:
                    mock_response = MagicMock()
                    mock_response.json.return_value = {"error": "invalid_client"}
                    mock_post.return_value = mock_response
                    
                    with pytest.raises(RuntimeError, match="Unexpected response from Spotify token endpoint"):
                        spotify_service.get_access_token()


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get('SPOTIFY_CLIENT_ID') or not os.environ.get('SPOTIFY_CLIENT_SECRET'),
    reason="Spotify credentials not set in environment variables"
)
def test_integration_get_playlist():
    """Integration test: Fetch a real Spotify playlist.
    
    This test requires SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables.
    """
    playlist_id = '3cEYpjA9oz9GiPac4AsH4n'
    
    try:
        result = spotify_service.get_playlist(playlist_id)
        
        # Verify basic structure
        assert "name" in result
        assert "tracks" in result
        assert isinstance(result["tracks"], list)
        assert len(result["tracks"]) > 0
        
        # Verify track structure
        first_track = result["tracks"][0]
        assert "id" in first_track
        assert "title" in first_track
        assert "artist" in first_track
        assert "album_name" in first_track
        assert "duration_ms" in first_track
        assert isinstance(first_track["duration_ms"], int)
        assert first_track["duration_ms"] > 0
        
        # Verify data types
        assert isinstance(first_track["title"], str)
        assert len(first_track["title"]) > 0
        assert first_track["artist"] is not None
        
        print(f"✓ Successfully fetched playlist: {result['name']}")
        print(f"✓ Total tracks: {len(result['tracks'])}")
        print(f"✓ First track: {first_track['title']} by {first_track['artist']}")
        
    except RuntimeError as e:
        pytest.fail(f"Integration test failed: {str(e)}")