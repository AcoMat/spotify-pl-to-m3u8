# Spoty playlist to .m3u8

## Match your .mp3 files with your spotify playlist

### Configuration
You will need a .env file in the script directory with the variables:

| Key (config)                 | Commandline parameter                  |
|------------------------------|----------------------------------------|
| SPOTIFY_CLIENT_ID            | developer.spotify.com/dashboard        | 
|------------------------------|----------------------------------------|
| SPOTIFY_CLIENT_SECRET        | developer.spotify.com/dashboard        | 
|------------------------------|----------------------------------------|
| MUSIC_DIRECTORY              | Where the script will search the files | 
|------------------------------|----------------------------------------|
| OUTPUT_FILE_DIR              | Where the script will write the .m3u8  | 


### Usage

```
python spotify_playlist_to_m3u8.py --playlist_ur=`<spotify playlist ur>`
```
