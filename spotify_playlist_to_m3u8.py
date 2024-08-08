import os
import unicodedata
from mutagen.id3 import ID3
from rapidfuzz import fuzz
from mutagen.mp3 import MP3
import re
import requests
import argparse
from dotenv import load_dotenv


def normalize_text(text):
    text = text.lower()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    
    text = text.replace("&", "").replace("-", "").replace('\'', '').replace(';', '').replace(',', '').replace('.', '').replace(' x ','').replace('(','').replace(')','')
    
    text = re.sub(r'\bremaster\b', '', text)
    text = re.sub(r'\bremastered\b', '', text)
    text = re.sub(r'\bversion\b', '', text)
    text = re.sub(r'\bedition \b', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\bfeat\b', '', text)
    text = re.sub(r'\bft.\b', '', text)
    
    text = text.replace(" ", "")
    return text


def create_index(base_directory):
    index = []
    for root, dirs, files in os.walk(base_directory):
        for file in files:
            if file.lower().endswith('.mp3'):
                file_path = os.path.join(root, file)
                try:
                    audio = ID3(file_path)
                    file_artist = normalize_text(audio.get('TPE1', None).text[0] if audio.get('TPE1', None) else '')
                    file_song = normalize_text(audio.get('TIT2', None).text[0] if audio.get('TIT2', None) else '')
                    file_album = normalize_text(audio.get('TALB', None).text[0] if audio.get('TALB', None) else '')
                    relative_path = os.path.relpath(file_path, base_directory)
                    index.append({
                        'artist': file_artist,
                        'song': file_song,
                        'album': file_album,
                        'path': relative_path
                    })
                except Exception as e:
                    print(e)
    return index

def find_mp3_file(index, artist, song, album):
    threshold = 86
    found_paths = set()

    search_string = f"{artist}{song}{album}"
    
    for entry in index:
        artist_score = fuzz.ratio(artist, entry['artist'])
        song_score = fuzz.ratio(song, entry['song'])
        album_score = fuzz.ratio(album, entry['album'])

        entry_string = f"{entry['artist']}{entry['song']}{entry['album']}"
        combined_score = fuzz.ratio(search_string, entry_string)
        
        ## 3r metodo        
        if combined_score >= threshold and entry['path'] not in found_paths:
            found_paths.add(entry['path'])
            return entry['path']

        ## 1er metodo
        elif song_score >= threshold and album_score >= threshold and entry['path'] not in found_paths:
            found_paths.add(entry['path'])
            return entry['path']
        
        ## 2do metodo
        elif artist_score >= threshold and song_score >= threshold and entry['path'] not in found_paths:
            found_paths.add(entry['path'])
            return entry['path']
        
    return None


def search_songs_from_track_list(base_directory, tracks):
    index = create_index(base_directory)
    results = []
    not_found = []
    
    for track in tracks:
        try:
            artist, song, album = map(lambda x: normalize_text(x.strip()), track.split(' --- ', 2))
        except ValueError:
            print(f"Línea inválida en el archivo de canciones: {track}")
            continue

        result = find_mp3_file(index, artist, song, album)
        if result:
             results.append(result)
        else:
            not_found.append(f"No encontrado: Artista: {artist}, Canción: {song}, Álbum: {album}")

    return [results, not_found]


# Generar el archivo .m3u8
def gen_m3u8_playlist(base_directory, searched_songs, output_playlist_dir, playlist_name):
    output_playlist_file = os.path.join(output_playlist_dir, f"{playlist_name}.m3u8")
    with open(output_playlist_file, 'w', encoding='utf-8') as playlist_file:
        playlist_file.write("#EXTM3U\n")
        for mp3 in searched_songs[0]:
            audio = ID3(os.path.join(base_directory, mp3))
            duration = MP3(os.path.join(base_directory, mp3)).info.length
            title = audio.get('TIT2', None).text[0] if audio.get('TIT2', None) else 'Unknown Title'
            artist = audio.get('TPE1', None).text[0] if audio.get('TPE1', None) else 'Unknown Artist'
            playlist_file.write(f"#EXTINF:{int(duration)},{artist} - {title}\n")
            playlist_file.write(mp3 + '\n')
        for not_found_item in searched_songs[1]:
            playlist_file.write(f"# {not_found_item}\n")

    print(f"Playlist generada en: {output_playlist_file}")


###                             SPOTIFY
# Función para obtener el token de acceso
def get_access_token(client_id, client_secret):
    url = 'https://accounts.spotify.com/api/token'
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret
    }
    response = requests.post(url, headers=headers, data=data)
    response_data = response.json()
    return response_data['access_token']

# Función para obtener las canciones de una playlist
def get_playlist(playlist_id, access_token):
    url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    limit = 50
    offset = 0
    all_raw_tracks = []

    while True:
        params = {
            'limit': limit,
            'offset': offset
        }
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        tracks = data['items']
        all_raw_tracks.extend(tracks)
        if len(tracks) < limit:
            break
        offset += limit

    return all_raw_tracks


def get_playlist_id(spotify_url):
    # Utilizamos una expresión regular para extraer el ID de la playlist
    match = re.search(r'playlist/([a-zA-Z0-9]+)', spotify_url)
    if match:
        return match.group(1)
    else:
        raise ValueError("URL no válida. No se pudo encontrar el ID de la playlist.")
    
def get_playlist_name(playlist_id, access_token):
    url = f'https://api.spotify.com/v1/playlists/{playlist_id}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(url, headers=headers)
    data = response.json()
    playlist_name = data['name']
    return playlist_name


## EXECUTION

def main(playlist_url):
    # Tu ID de cliente y secreto de cliente de Spotify
    load_dotenv()
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    base_directory = os.getenv('MUSIC_DIRECTORY')
    output_playlist_dir = os.getenv('OUTPUT_FILE_DIR')

    # ID de la playlist 
    playlist_id = get_playlist_id(playlist_url)
    # Obtener token de acceso
    access_token = get_access_token(client_id, client_secret)

    # Obtener nombre y canciones de la playlist
    playlist_tracks = get_playlist(playlist_id, access_token)
    playlist_name = get_playlist_name(playlist_id, access_token)

    all_tracks = []
    for track in playlist_tracks:
        track_info = track['track']
        artists = ', '.join(artist['name'] for artist in track_info['artists'])
        song_name = track_info['name']
        album_name = track_info['album']['name']
        all_tracks.append(f"{artists} --- {song_name} --- {album_name}")

    searched_songs = search_songs_from_track_list(base_directory, all_tracks)
    gen_m3u8_playlist(base_directory, searched_songs, output_playlist_dir, playlist_name)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
      description="Script that "
    )
    parser.add_argument("--playlist_url", required=True, type=str)
    args = parser.parse_args()

    args = parser.parse_args()

    main(args.playlist_url)
