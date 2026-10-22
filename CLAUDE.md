# SongPsychic

Music recommender built end to end as a way to learn how recommender systems work.
Priority is understanding: explain what each model does and why, and keep code readable.

## Stages
- 1 EDA + popularity baseline + evaluation harness
- 2 Collaborative filtering (ALS via `implicit`),
- 3 Content-based (tags / artist aggregates, later audio embeddings) 
- 4 Hybrid
- 5 Sequence-aware 
- 6 API + frontend.
**Current stage: 1.**

## Data

All datasets come from the MetaBrainz family (MusicBrainz and its sister projects), downloaded
directly (no account/signup needed) from [data.metabrainz.org](https://data.metabrainz.org/pub/musicbrainz/).
See [metabrainz.org/datasets/download](https://metabrainz.org/datasets/download) for the index.

### Interactions (collaborative filtering, stage 2+)
- **MLHD+** — the primary dataset. An improved re-release of the McGill DDMAL "Music Listening
  Histories Dataset": per-user, per-listen events with timestamps, cleaned up and canonicalized
  against MusicBrainz (redirects followed, recording/artist/release MBIDs corrected). Unlike the
  old Last.fm 360K dump, these listens *do* have timestamps, so splits can be time-based
  (leave-last-N-out per user) instead of the artist-holdout workaround.
  Docs: [musicbrainz.org/doc/MLHD+](https://musicbrainz.org/doc/MLHD%2B). Download:
  [data.metabrainz.org/pub/musicbrainz/listenbrainz/mlhd/](https://data.metabrainz.org/pub/musicbrainz/listenbrainz/mlhd/)
  — 16 "complete" shards (~15GB each) + 16 smaller "partial" shards (~2GB each); start with one
  partial shard while iterating. License: non-commercial use only — fine for this project, don't
  redistribute.

### Metadata (content-based, stage 3+)
- **MusicBrainz database** — core entity data: artists, releases, recordings, labels, and the
  relationships between them (collaborations, covers, remixes), plus user tags/genres. Available
  as PostgreSQL dumps (for a full local MB server) or as JSON document dumps. Full snapshot
  generated twice a week.
  Docs: [musicbrainz.readthedocs.io/.../download.html](https://musicbrainz.readthedocs.io/en/latest/musicbrainz_database/download.html).
  Download: [data.metabrainz.org/pub/musicbrainz/data/fullexport/](https://data.metabrainz.org/pub/musicbrainz/data/fullexport/)
  (PostgreSQL) or [.../data/json-dumps/](https://data.metabrainz.org/pub/musicbrainz/data/json-dumps/)
  (JSON). Core metadata (`mbdump.tar.bz2`) is CC0; tags/ratings (`mbdump-derived.tar.bz2`) are
  CC BY-NC-SA.
- **Canonical Data Dump** — picks one canonical recording/release per MusicBrainz release-group
  (collapsing remasters, live versions, re-releases etc. into a single representative version),
  plus a flattened CSV of their basic metadata (artist, title) for fuzzy matching. Use it to
  canonicalize the recording IDs in MLHD+ *before* joining against the full MusicBrainz dump, so a
  song isn't fragmented into multiple items by its different releases. CC0, updated twice a month.
  Docs: [musicbrainz.org/doc/Canonical_MusicBrainz_data](https://musicbrainz.org/doc/Canonical_MusicBrainz_data).
  Download: [data.metabrainz.org/pub/musicbrainz/canonical_data/](https://data.metabrainz.org/pub/musicbrainz/canonical_data/)
  (latest dated subdirectory, one `.tar.zst` archive of three CSVs).

  **Standard dump vs. canonical dump:** the standard dump is the full, authoritative database —
  every release, recording, and version that exists, with no deduplication. The canonical dump is
  a small *derived* lookup table on top of it, picking a single "preferred" recording/release per
  song so recommender items aren't split across duplicates. They answer different questions and
  you need both: canonical dump to decide what counts as "the same song," standard dump for the
  actual artist/tag/genre metadata once items are canonicalized.

### Optional extensions (later stages)
- **AcousticBrainz** — crowd-sourced low-level audio features (tempo, key, timbre, mood) for
  content-based audio embeddings. The project stopped accepting new submissions in 2022 but the
  existing archive is still queryable; the cleanest offline copy is the MediaEval "AcousticBrainz
  Genre Dataset" on Zenodo (~37GB, Bogdanov et al., ISMIR 2019).
  Site: [acousticbrainz.org](https://acousticbrainz.org/). Archive:
  [zenodo.org/records/2553414](https://zenodo.org/records/2553414).
- **CritiqueBrainz** — free-text reviews and ratings of releases, for experiments with
  review-text features or explicit ratings instead of implicit listens. No bulk dump; pull via the
  public API (`GET /review/`, paginated with `limit`/`offset`).
  Docs: [critiquebrainz.readthedocs.io/api/endpoints.html](https://critiquebrainz.readthedocs.io/api/endpoints.html).

Never commit anything under `data/` or `models/`. Everything must be reproducible from `scripts/`.

## Structure (create folders only when their stage starts)
- data/{raw,interim,processed}/  gitignored; data/README.md records sources and licenses
- scripts/  thin CLI entry points: download_data.py, build_dataset.py, train.py, evaluate.py
- src/songpsychic/  the real code: data/, evaluation/, models/, features/, utils/
- notebooks/  exploration only; logic worth keeping moves into src/
- models/  trained artifacts, gitignored
- experiments/  results table, one row per run
- api/ (FastAPI) and frontend/  added at the serving stage
- tests/  pytest

## Conventions
- Python 3.11+, type hints, small functions, docstrings explaining the *why* for recommender-specific logic.
- Every model implements `fit(train)` and `recommend(user, k)` (models/base.py).
- Evaluation: Recall@K, NDCG@K, catalog coverage, diversity. Always compare against the popularity baseline.
- Test the metrics and the splits (no train/test leakage) on tiny hand-computed examples.
- Save user/item ID maps alongside every processed dataset and model.

## Commands

Data (see `data/README.md` for what each dataset is and why):
```
python scripts/download_data.py --dataset mlhd --files mlhdplus-partial-0.tar  # start small
python scripts/download_data.py --dataset canonical
python scripts/download_data.py --dataset musicbrainz --files mbdump.tar.bz2 mbdump-derived.tar.bz2
```

(fill in as they exist: pytest, python scripts/build_dataset.py, python scripts/train.py, etc.)
