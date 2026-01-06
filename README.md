# spot-the-local

Convert Spotify and YouTube Music playlists to local M3U8 playlists.

## What it does

Takes a Spotify or YouTube Music playlist URL and generates an M3U8 playlist file using your local music library.

## Why not other alternative?

While there are other tools that can generate M3U playlists, it isually requires downloading all tracks from the source playlist before creating the playlist file. This approach is focused in only use your local music library, matching only the music that you have already downloaded.

## Installation

```bash
pip install -e .
```

## Usage

```bash
spot-the-local <playlist_url> [--music-dir PATH] [--output-dir PATH]
```

**Examples:**

```bash
# Spotify playlist
spot-the-local https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M

# YouTube Music playlist
spot-the-local https://music.youtube.com/playlist?list=PLWLPrGuMj5frfb4wkB7DiQzpPSERX8cLe

# Specify custom music directory
spot-the-local <playlist_url> --music-dir ~/Music
```

By default, it uses your OS user music directory for both the local music library and the output M3U8 file.

## Requirements

- Python 3.10+
- Local music files with metadata (artist, title, album)

## License

MIT
