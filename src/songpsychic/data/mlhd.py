"""Parse MLHD+ tar shards into a flat listens table.

Each shard is a .tar of per-user files, bucketed into hash-prefix directories (e.g.
``00/<uuid>.txt.zst``). Each per-user file is itself zstd-compressed, tab-separated, no header:
timestamp (unix epoch seconds), artist_mbid, release_mbid, recording_mbid. recording_mbid is
often empty in "partial" shards (unresolved) and almost always present in "complete" shards.
"""

from __future__ import annotations

import tarfile
from pathlib import Path

import pandas as pd
import zstandard

COLUMNS = ["user_id", "timestamp", "artist_mbid", "release_mbid", "recording_mbid"]


def _user_id_from_member_name(member_name: str) -> str:
    # "00/004927e0-092d-4eea-b928-eea7a8ca3b48.txt.zst" -> "004927e0-092d-4eea-b928-eea7a8ca3b48"
    return Path(member_name).name.removesuffix(".txt.zst")


def iter_shard(tar_path: Path, batch_size: int = 500):
    """Yield one DataFrame per `batch_size` users from an MLHD+ shard.

    A "complete" shard is ~15GB compressed; holding every row for the whole shard as Python
    objects before building one DataFrame would use far more memory than that (tuple/string
    object overhead dwarfs the raw bytes). Yielding in batches keeps peak memory bounded
    regardless of shard size — the caller decides whether to concat a few batches or stream each
    one straight to parquet.
    """
    rows: list[tuple[str, int, str | None, str | None, str | None]] = []
    users_in_batch = 0

    with tarfile.open(tar_path) as tar:
        for member in tar:
            if not member.isfile():
                continue
            user_id = _user_id_from_member_name(member.name)
            with tar.extractfile(member) as f:
                with zstandard.ZstdDecompressor().stream_reader(f) as reader:
                    text = reader.read().decode("utf-8")

            for line in text.splitlines():
                if not line:
                    continue
                timestamp, artist_mbid, release_mbid, recording_mbid = line.split("\t")
                rows.append((
                    user_id,
                    int(timestamp),
                    artist_mbid or None,
                    release_mbid or None,
                    recording_mbid or None,
                ))
            users_in_batch += 1

            if users_in_batch >= batch_size:
                yield pd.DataFrame(rows, columns=COLUMNS)
                rows = []
                users_in_batch = 0

    if rows:
        yield pd.DataFrame(rows, columns=COLUMNS)


def parse_shard(tar_path: Path, user_limit: int | None = None) -> pd.DataFrame:
    """Read an MLHD+ shard into one DataFrame.

    Only for small/sample shards or a capped `user_limit` — for a full "complete" shard, use
    `iter_shard` and write each batch to parquet instead of concatenating everything in memory.
    """
    batches = []
    users_seen = 0
    for batch in iter_shard(tar_path, batch_size=500):
        batches.append(batch)
        users_seen += batch["user_id"].nunique()
        if user_limit is not None and users_seen >= user_limit:
            break
    return pd.concat(batches, ignore_index=True)
