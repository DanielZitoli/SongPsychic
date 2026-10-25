"""Build data/interim/ from data/raw/ — the real, reproducible pipeline.

Usage:
    python scripts/build_dataset.py --step mlhd
    python scripts/build_dataset.py --step musicbrainz
    python scripts/build_dataset.py --step all
    python scripts/build_dataset.py --step mlhd --limit-users 1000  # quick smoke test

See CLAUDE.md / data/README.md for what each table is and the canonical-coverage caveat.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pyarrow as pa
import pyarrow.parquet as pq

from songpsychic.data import canonical, mlhd, musicbrainz
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"

# Only "complete" shards resolve to the recording level — "partial" shards never do (verified:
# 0% vs 100% recording_mbid coverage), so they're excluded entirely. Picked up automatically as
# more get downloaded into data/raw/mlhd/.
MLHD_COMPLETE_SHARDS = sorted(RAW.glob("mlhd/mlhdplus-complete-*.tar"))

# usecols=None means "load every column"; `recording` only needs its id<->gid map here (the full
# table is 4.6GB and we don't use its other columns yet).
MUSICBRAINZ_CORE_TABLES = {
    "artist": None,
    "artist_credit": None,
    "artist_credit_name": None,
    "isrc": None,
    "recording": ["id", "gid"],
}
MUSICBRAINZ_DERIVED_TABLES = ["artist_tag", "tag"]


def build_mlhd_listens(shard_paths: list[Path], redirect_dir: Path, out_path: Path, user_limit: int | None = None) -> None:
    """Parse MLHD+ shards, resolve item_id, and write to one parquet file.

    Streams batch-by-batch rather than building one DataFrame for the whole shard — a full
    complete shard is on the order of a billion rows, which wouldn't fit in memory at once.
    """
    redirect = canonical.load_recording_redirect(redirect_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    writer: pq.ParquetWriter | None = None
    schema: pa.Schema | None = None
    users_seen = 0

    try:
        for shard_path in shard_paths:
            print(f"Processing {shard_path.name}...")
            for batch in mlhd.iter_shard(shard_path):
                resolved = canonical.canonicalize_recordings(batch, redirect)
                table = pa.Table.from_pandas(resolved, preserve_index=False)

                if schema is None:
                    schema = table.schema
                    # zstd over the pyarrow default (snappy) roughly halves file size on this
                    # UUID-heavy data — measured: 901MB -> 375MB on a 19M-row sample.
                    writer = pq.ParquetWriter(out_path, schema, compression="zstd")
                else:
                    table = table.cast(schema)
                writer.write_table(table)

                users_seen += batch["user_id"].nunique()
                print(f"  {users_seen:,} users, {batch.shape[0]:,} rows in this batch")
                if user_limit is not None and users_seen >= user_limit:
                    print(f"  reached --limit-users {user_limit}, stopping")
                    return
    finally:
        if writer is not None:
            writer.close()


def build_musicbrainz_tables(core_path: Path, derived_path: Path, out_dir: Path) -> None:
    """One-shot load the handful of MusicBrainz tables this project needs."""
    out_dir.mkdir(parents=True, exist_ok=True)

    for table_name, usecols in MUSICBRAINZ_CORE_TABLES.items():
        print(f"Loading {table_name}...")
        df = musicbrainz.load_table(core_path, table_name, usecols=usecols)
        df.to_parquet(out_dir / f"{table_name}.parquet", index=False)
        print(f"  {table_name}: {len(df):,} rows")

    for table_name in MUSICBRAINZ_DERIVED_TABLES:
        print(f"Loading {table_name}...")
        df = musicbrainz.load_table(derived_path, table_name)
        df.to_parquet(out_dir / f"{table_name}.parquet", index=False)
        print(f"  {table_name}: {len(df):,} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--step", choices=["mlhd", "musicbrainz", "all"], default="all")
    parser.add_argument("--limit-users", type=int, default=None, help="Stop after N users (mlhd step only, for smoke tests)")
    args = parser.parse_args()

    if args.step in ("mlhd", "all"):
        if not MLHD_COMPLETE_SHARDS:
            raise SystemExit("No complete MLHD+ shards found in data/raw/mlhd/ — run fetch_sample_data.py or download_data.py first")
        build_mlhd_listens(
            MLHD_COMPLETE_SHARDS,
            redirect_dir=INTERIM / "canonical",
            out_path=INTERIM / "mlhd_listens.parquet",
            user_limit=args.limit_users,
        )

    if args.step in ("musicbrainz", "all"):
        build_musicbrainz_tables(
            core_path=RAW / "musicbrainz" / "mbdump.tar.bz2",
            derived_path=RAW / "musicbrainz" / "mbdump-derived.tar.bz2",
            out_dir=INTERIM / "musicbrainz",
        )


if __name__ == "__main__":
    main()
