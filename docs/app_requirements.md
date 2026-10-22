# Client-facing app requirements

Requirements for the eventual `api/` + `frontend/` (stage 6) — captured now, ahead of time, so ML
pipeline decisions don't box in the serving layer later. Nothing here is built yet.

## Features

- **Playlist import**
  - User exports their Spotify playlists via exportify.net (zip of CSVs), uploads to the site
  - Exportify CSVs give title + ISRC, no MBID — need ISRC→MBID resolution via MusicBrainz's `isrc`
    table (already planned to be pulled locally, see `CLAUDE.md`)

- **Cover art**
  - Show cover art per song in an uploaded playlist
  - Mapping (release → Cover Art Archive ID): MusicBrainz dump's `cover-art-archive` table
  - Actual image: live Cover Art Archive API call per song, not bulk-downloaded

- **Playlist analysis** (once a user selects one of their playlists)
  - Genre and artist breakdown
  - ML-powered clustering / sub-playlist generation from the playlist's songs

- **Playlist generation from a seed**
  - Given one or a few songs, generate a new playlist
  - Powered by the recommender models (which stage/model — TBD)
