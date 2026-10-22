"""Download one MLHD+ partial shard (~2GB) and one complete shard (~15GB).

Enough to see both formats side by side without pulling all 32 shards (~272GB). Used for the
stage-1 EDA in notebooks/01_explore_data_format.ipynb, before any loader code is written.

Usage:
    python scripts/fetch_sample_data.py
"""

from __future__ import annotations

from download_data import DATASETS, download_file, list_dir, resolve_index_url, verify_file

SAMPLE_SHARDS = ["mlhdplus-partial-0.tar", "mlhdplus-complete-0.tar"]


def main() -> None:
    info = DATASETS["mlhd"]
    base_url = resolve_index_url(info)
    files = [e for e in list_dir(base_url) if not e.endswith("/")]
    dest_paths = {name: download_file(base_url, name, info["dest"]) for name in SAMPLE_SHARDS}

    print("Verifying checksums...")
    for name in SAMPLE_SHARDS:
        verify_file(base_url, name, dest_paths[name], files)


if __name__ == "__main__":
    main()
