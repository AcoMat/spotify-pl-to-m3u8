import sys
import api
import db

LOCAL_LIBRARY_ROOT = "D:/Music"

INPUT_PLAYLIST_URL = sys.argv[1] if len(sys.argv) > 1 else None
if INPUT_PLAYLIST_URL is None: raise ValueError("No playlist URL provided.")

LOCAL_PATHS = []
#   TODO: Multi-threading for faster processing


def gen_m3u8_file():
    pass


if __name__ == "__main__":
    #db.index_library_to_sqlite(LOCAL_LIBRARY_ROOT)
    
    access_token = api.get_access_token()
    # Extract playlist id from URL and strip query parameters (e.g., ?si=...)
    playlist_id = INPUT_PLAYLIST_URL.rstrip("/").split("/")[-1].split("?")[0]

    playlist_info = api.get_playlist_info(playlist_id, access_token)
    print(playlist_info)
    
    

    