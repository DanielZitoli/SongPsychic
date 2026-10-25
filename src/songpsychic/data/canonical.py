"""Load the Canonical Data Dump CSVs and resolve MLHD+ recording MBIDs to item IDs.

``canonical_recording_redirect.csv`` maps a recording MBID to one ``canonical_recording_mbid``,
collapsing duplicate releases/remasters of the same song onto a single item ID — but it only
covers recordings that are part of a cleanly-organized release-group (~19% of all MusicBrainz
recordings; verified against the real dump). Singles, compilations, soundtracks etc. are mostly
absent. Requiring a canonical match would silently drop ~95% of real listens, so
`canonicalize_recordings` falls back to the original `recording_mbid` as the item ID when there's
no canonical entry, rather than dropping the row.
"""

from __future__ import annotations

import tarfile
from pathlib import Path

import pandas as pd
import zstandard


def extract_canonical_dump(archive_path: Path, dest_dir: Path) -> None:
    """Extract the canonical dump's 3 CSVs directly into `dest_dir`, flat.

    The archive's own internal layout is nested and dated
    (`musicbrainz-canonical-dump-<date>/canonical/*.csv`) — we write each CSV straight to
    `dest_dir/<name>.csv` by name instead of letting `tar.extractall` preserve that structure.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    with open(archive_path, "rb") as fh:
        with zstandard.ZstdDecompressor().stream_reader(fh) as reader:
            with tarfile.open(fileobj=reader, mode="r|") as tar:
                for member in tar:
                    if member.isfile() and member.name.endswith(".csv"):
                        with tar.extractfile(member) as f:
                            (dest_dir / Path(member.name).name).write_bytes(f.read())


def load_recording_redirect(canonical_dir: Path) -> pd.DataFrame:
    return pd.read_csv(canonical_dir / "canonical_recording_redirect.csv", dtype=str)


def load_musicbrainz_data(canonical_dir: Path) -> pd.DataFrame:
    return pd.read_csv(canonical_dir / "canonical_musicbrainz_data.csv", dtype=str)


def canonicalize_recordings(listens: pd.DataFrame, redirect: pd.DataFrame) -> pd.DataFrame:
    """Add an ``item_id`` column: the canonical recording ID where one exists, else the original
    ``recording_mbid`` unchanged.

    A listen with no ``recording_mbid`` to begin with (unresolved — always true for MLHD+
    "partial" shards, never true for "complete" ones) has no ``item_id`` either; that's the one
    case this can't paper over, since there's nothing to fall back to.
    """
    merged = listens.merge(
        redirect[["recording_mbid", "canonical_recording_mbid"]],
        on="recording_mbid",
        how="left",
    )
    merged["item_id"] = merged["canonical_recording_mbid"].fillna(merged["recording_mbid"])
    return merged
