from unittest.mock import patch, MagicMock
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import yt_music_service

# Run integration tests with: pytest -m integration
# Skip integration tests with: pytest -m "not integration"

expected_output = {
    "id": "RDCLAK5uy_lWy02cQBnTVTlwuRauaGKeUDH3L6PXNxI",
    "title": "Feel-Good Classic Rock",
    "owned": False,
    "trackCount": 101,
    "year": "2024",
    "description": "Hold on to the feeling.\n#essentials #rock #happy",
    "duration": "6+ hours"
}

def test_smoke_get_playlist():
    """Smoke test: Verify basic get_playlist functionality works."""
    mock_playlist_id = "smoke_test_playlist"
    
    mock_api_response = {
        "title": "Smoke Test Playlist",
        "trackCount": 2,
        "tracks": [
            {
                "videoId": "video1",
                "title": "Test Song 1",
                "album": {"name": "Test Album", "year": 2024},
                "artists": [{"name": "Test Artist"}],
                "duration_seconds": 180
            },
            {
                "videoId": "video2",
                "title": "Test Song 2",
                "album": {"name": "Test Album 2", "year": 2023},
                "artists": [{"name": "Test Artist 2"}],
                "duration_seconds": 240
            }
        ]
    }
    
    with patch.object(yt_music_service.ytmusic, 'get_playlist', return_value=mock_api_response):
        result = yt_music_service.get_playlist(mock_playlist_id)
        
        assert result["name"] == "Smoke Test Playlist"
        assert len(result["tracks"]) == 2
        assert result["tracks"][0]["id"] == "video1"
        assert result["tracks"][0]["title"] == "Test Song 1"
        assert result["tracks"][1]["duration_ms"] == 240000


@pytest.mark.integration
def test_integration_get_playlist():
    """Integration test: Fetch a real YouTube Music playlist.
    
    Uses YouTube Music's "Feel-Good Classic Rock" playlist.
    Note: Track count and first song may change over time.
    """
    try:
        playlist = yt_music_service.get_playlist(expected_output["id"])
        
        # Verify basic structure
        assert "name" in playlist
        assert "tracks" in playlist
        assert playlist["name"] == expected_output["title"]
        
        # Verify tracks exist and have proper structure
        assert isinstance(playlist["tracks"], list)
        assert len(playlist["tracks"]) > 0
        
        # Note: Track count can change, so we check it's reasonable rather than exact
        assert len(playlist["tracks"]) >= 50, "Playlist should have at least 50 tracks"
        
        # Verify first track structure
        first_track = playlist["tracks"][0]
        assert "id" in first_track
        assert "title" in first_track
        assert "artist" in first_track
        assert "duration_ms" in first_track
        assert isinstance(first_track["duration_ms"], int)
        assert first_track["duration_ms"] > 0
        
        # Verify data types and content
        assert isinstance(first_track["title"], str)
        assert len(first_track["title"]) > 0
        
        print(f"✓ Successfully fetched playlist: {playlist['name']}")
        print(f"✓ Total tracks: {len(playlist['tracks'])}")
        print(f"✓ First track: {first_track['title']} by {first_track['artist']}")
        
    except Exception as e:
        pytest.fail(f"Integration test failed: {str(e)}")


def test_get_playlist_with_missing_data():
    """Test that get_playlist correctly handles tracks with missing or incomplete data."""
    mock_playlist_id = "test_playlist_123"
    
    mock_api_response = {
        "title": "Test Playlist",
        "trackCount": 3,
        "tracks": [
            {
                "videoId": "vid1",
                "title": "Complete Track",
                "album": {"name": "Album 1", "year": 2020},
                "artists": [{"name": "Artist 1"}, {"name": "Artist 2"}],
                "duration_seconds": 240
            },
            {
                "videoId": "vid2",
                "title": "Track Without Album",
                "album": None,
                "artists": [{"name": "Artist 3"}],
                "duration_seconds": 180
            },
            {
                "videoId": "vid3",
                "title": "Track Without Artists",
                "album": {"name": "Album 2"},
                "artists": [],
                "duration_seconds": 200
            }
        ]
    }
    
    with patch.object(yt_music_service.ytmusic, 'get_playlist', return_value=mock_api_response):
        result = yt_music_service.get_playlist(mock_playlist_id)
        
        assert result["name"] == "Test Playlist"
        assert len(result["tracks"]) == 3
        
        # Check first track with complete data
        assert result["tracks"][0]["id"] == "vid1"
        assert result["tracks"][0]["artist"] == "Artist 1, Artist 2"
        assert result["tracks"][0]["album_name"] == "Album 1"
        assert result["tracks"][0]["duration_ms"] == 240000
        
        # Check track with missing album
        assert result["tracks"][1]["album_name"] is None
        assert result["tracks"][1]["release_date"] is None
        
        # Check track with no artists
        assert result["tracks"][2]["artist"] == ""