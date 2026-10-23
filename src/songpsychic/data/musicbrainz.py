"""Load specific tables out of the MusicBrainz COPY-format dumps.

The dumps ship with no header row and no column names — the only source of truth for what each
column means is the MusicBrainz server schema (``admin/sql/CreateTables.sql``). The column lists
below were copied from there, for only the tables this project actually uses — not the full
~80-table schema.
"""

from __future__ import annotations

import csv
import tarfile
from pathlib import Path

import pandas as pd

# mbdump.tar.bz2 (core data, CC0)
CORE_TABLE_COLUMNS = {
    "artist": [
        "id", "gid", "name", "sort_name",
        "begin_date_year", "begin_date_month", "begin_date_day",
        "end_date_year", "end_date_month", "end_date_day",
        "type", "area", "gender", "comment", "edits_pending",
        "last_updated", "ended", "begin_area", "end_area",
    ],
    "artist_credit": ["id", "name", "artist_count", "ref_count", "created", "edits_pending", "gid"],
    "artist_credit_name": ["artist_credit", "position", "artist", "name", "join_phrase"],
    "isrc": ["id", "recording", "isrc", "edits_pending", "created"],
    "recording": [
        "id", "gid", "name", "artist_credit", "length", "comment",
        "edits_pending", "last_updated", "video",
    ],
    # Maps an old/merged-away recording MBID to the recording.id it now redirects to.
    "recording_gid_redirect": ["gid", "new_id", "created"],
}

# mbdump-derived.tar.bz2 (user tags/genres, CC BY-NC-SA)
DERIVED_TABLE_COLUMNS = {
    "artist_tag": ["artist", "tag", "count", "last_updated"],
    "tag": ["id", "name", "ref_count"],
}


def load_table(archive_path: Path, table_name: str, usecols: list[str] | None = None) -> pd.DataFrame:
    """Stream a single table out of a bz2-compressed MusicBrainz dump.

    Streams rather than calling ``getmembers()`` first — bz2 has no random access, so building a
    full member list means decompressing the entire multi-GB archive just to find one table.
    """
    columns = CORE_TABLE_COLUMNS.get(table_name) or DERIVED_TABLE_COLUMNS.get(table_name)
    if columns is None:
        raise ValueError(f"no known schema for table {table_name!r} — add it to musicbrainz.py")

    with tarfile.open(archive_path, mode="r|bz2") as tar:
        for member in tar:
            if member.name.endswith(f"/{table_name}"):
                f = tar.extractfile(member)
                return pd.read_csv(
                    f,
                    sep="\t",
                    header=None,
                    names=columns,
                    usecols=usecols,
                    na_values="\\N",
                    dtype=str,
                    # Postgres COPY text format has no quoting (only backslash-escaping) — a
                    # literal `"` in a free-text field like `comment` would otherwise desync
                    # pandas' default CSV quote handling and misalign columns.
                    quoting=csv.QUOTE_NONE,
                )

    raise ValueError(f"table {table_name!r} not found in {archive_path}")
