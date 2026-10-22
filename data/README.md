# Data

Nothing under `data/` is committed (see `.gitignore`) — this file is the exception, and the
record of where everything came from and how to get it back.

## Layout

- `raw/` — untouched downloads, exactly as fetched (archives, CSVs, dump directories).
- `interim/` — intermediate, partially-cleaned data (e.g. decompressed dumps, joined tables)
  that's expensive to regenerate but still not the final training format.
- `processed/` — final datasets ready for `scripts/train.py` / `scripts/evaluate.py`, plus the
  user/item ID maps saved alongside them.

## Sources

### MLHD+ — interactions (primary, stage 2+)
Per-user listening history with timestamps, canonicalized against MusicBrainz recording/artist/
release IDs. This is what collaborative filtering trains on.
- Docs: https://musicbrainz.org/doc/MLHD%2B
- Download (no signup): https://data.metabrainz.org/pub/musicbrainz/listenbrainz/mlhd/ — 16
  "complete" shards (`mlhdplus-complete-{0-9,a-f}.tar`, ~15GB each) and 16 "partial" shards
  (`mlhdplus-partial-{0-9,a-f}.tar`, ~2GB each). Start with a single partial shard for EDA/dev;
  the complete shards together are ~240GB. `md5sums`/`sha256sums` are in the same directory.
- License: **non-commercial use only**. Fine for this learning project; don't redistribute the
  raw files.
- Goes in `data/raw/mlhd/`.

### MusicBrainz database dump — metadata (stage 3+)
Artists, releases, recordings, relationships, and user tags/genres.
- Docs: https://musicbrainz.readthedocs.io/en/latest/musicbrainz_database/download.html
- Download (no signup): https://data.metabrainz.org/pub/musicbrainz/data/fullexport/ (PostgreSQL,
  latest dated subdirectory) or https://data.metabrainz.org/pub/musicbrainz/data/json-dumps/
  (JSON). Core data (`mbdump.tar.bz2`) is CC0; tags/ratings (`mbdump-derived.tar.bz2`) are
  CC BY-NC-SA 3.0 — keep these licenses separate if the derived data is ever reused elsewhere.
- Goes in `data/raw/musicbrainz/`.

### Canonical Data Dump — ID mapping helper
Picks one canonical recording/release per release-group (collapsing remasters, live versions,
re-releases etc.), so the same song isn't fragmented into multiple items. Use it to resolve MLHD+
MBIDs before joining against the full MusicBrainz metadata dump.
- Docs: https://musicbrainz.org/doc/Canonical_MusicBrainz_data
- Download (no signup): https://data.metabrainz.org/pub/musicbrainz/canonical_data/ (latest dated
  subdirectory; one `.tar.zst` archive containing three CSVs — release redirect, recording
  redirect, and flattened metadata).
- License: CC0.
- Goes in `data/raw/canonical/`.

**Do you need both the standard dump and the canonical dump?** Yes, they serve different jobs.
The standard dump is the full, undeduplicated database — every version of every release and
recording. The canonical dump is a small derived table on top of it that just says "treat these N
MBIDs as the same recording, and here's the one to prefer." Use the canonical dump to collapse
MLHD+ listens onto one ID per song, then use the standard dump to pull that song's actual
artist/tag/genre metadata.

### Optional, later stages
- **AcousticBrainz** (audio features for content-based embeddings, frozen since 2022): archive
  copy via the MediaEval "AcousticBrainz Genre Dataset" on Zenodo —
  https://zenodo.org/records/2553414
- **CritiqueBrainz** (review text / explicit ratings): no bulk dump, pull via the API —
  https://critiquebrainz.readthedocs.io/api/endpoints.html

## Reproducing

Everything above is fetchable with `python scripts/download_data.py --dataset <name>`, which lists
the files currently available at the relevant `data.metabrainz.org` directory and downloads the
ones requested with `--files` (or all of them, for `musicbrainz`/`canonical`, if `--files` is
omitted — MLHD+ always requires an explicit `--files` since downloading all 32 shards by accident
would be ~272GB).
