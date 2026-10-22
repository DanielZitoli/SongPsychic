"""Fetch raw datasets into data/raw/ from data.metabrainz.org (public, no signup needed).

Usage:
    python scripts/download_data.py --dataset musicbrainz --list
    python scripts/download_data.py --dataset musicbrainz --files mbdump.tar.bz2 mbdump-derived.tar.bz2
    python scripts/download_data.py --dataset canonical          # fetches all files, small dataset
    python scripts/download_data.py --dataset mlhd --list
    python scripts/download_data.py --dataset mlhd --files mlhdplus-partial-0.tar

`musicbrainz` and `canonical` are split into dated snapshot subdirectories; this script always
uses the latest one. `mlhd` is a flat, one-off dump (last updated 2023) and is large (complete
shards are ~15GB each, 240GB total) — `--files` is required so nothing huge downloads by accident.

Files already present in data/raw/ are left alone (not re-downloaded). After downloading, every
requested file — including ones that were already there — is checked against the dataset's
published SHA256 (a manifest like `SHA256SUMS`, or a per-file `.sha256` sidecar, depending on the
dataset); a mismatch fails loud instead of leaving a silently corrupt file in data/raw/.

See data/README.md for what each dataset contains and its license.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import urllib.request
from pathlib import Path

DATA_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

DATASETS = {
    "musicbrainz": {
        "index_url": "https://data.metabrainz.org/pub/musicbrainz/data/fullexport/",
        "dated_subdir": True,
        "dest": DATA_RAW / "musicbrainz",
    },
    "canonical": {
        "index_url": "https://data.metabrainz.org/pub/musicbrainz/canonical_data/",
        "dated_subdir": True,
        "dest": DATA_RAW / "canonical",
    },
    "mlhd": {
        "index_url": "https://data.metabrainz.org/pub/musicbrainz/listenbrainz/mlhd/",
        "dated_subdir": False,
        "dest": DATA_RAW / "mlhd",
    },
}

_HREF_RE = re.compile(r'href="([^"]+)"')
_MANIFEST_NAMES = ("SHA256SUMS", "sha256sums")
_manifest_cache: dict[str, dict[str, str]] = {}


def list_dir(url: str) -> list[str]:
    """Return the entry names (files and subdir/ names) linked from a directory index page."""
    with urllib.request.urlopen(url) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    entries = [href for href in _HREF_RE.findall(html) if href not in ("../", "/")]
    return entries


def resolve_index_url(info: dict) -> str:
    """For snapshot-dumped datasets, find the latest dated subdirectory."""
    if not info["dated_subdir"]:
        return info["index_url"]
    subdirs = sorted(e for e in list_dir(info["index_url"]) if e.endswith("/"))
    if not subdirs:
        raise RuntimeError(f"No dated snapshot subdirectories found at {info['index_url']}")
    latest = subdirs[-1]
    return info["index_url"] + latest


def download_file(base_url: str, name: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / name
    if dest_path.exists():
        print(f"Already have {dest_path}, skipping download")
        return dest_path
    url = base_url + name
    print(f"Downloading {url} -> {dest_path}")
    urllib.request.urlretrieve(url, dest_path)
    return dest_path


def _is_checksum_artifact(name: str) -> bool:
    """Manifests and signature files have nothing to verify them against."""
    return name.endswith((".asc", ".sha256", ".md5")) or name.lower() in ("sha256sums", "md5sums")


def _fetch_manifest(url: str) -> dict[str, str]:
    if url not in _manifest_cache:
        with urllib.request.urlopen(url) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        manifest = {}
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            digest, _, fname = line.partition(" ")
            manifest[fname.lstrip("*").strip()] = digest
        _manifest_cache[url] = manifest
    return _manifest_cache[url]


def find_checksum(base_url: str, name: str, files: list[str]) -> str | None:
    """Look up the published SHA256 for `name`: a `<name>.sha256` sidecar, or a SHA256SUMS-style
    manifest, whichever this dataset's directory has."""
    sidecar = f"{name}.sha256"
    if sidecar in files:
        with urllib.request.urlopen(base_url + sidecar) as resp:
            return resp.read().decode("utf-8", errors="replace").split()[0]
    for manifest_name in _MANIFEST_NAMES:
        if manifest_name in files:
            digest = _fetch_manifest(base_url + manifest_name).get(name)
            if digest:
                return digest
    return None


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(base_url: str, name: str, dest_path: Path, files: list[str]) -> None:
    if _is_checksum_artifact(name):
        return
    expected = find_checksum(base_url, name, files)
    if expected is None:
        print(f"  no published checksum for {name}, skipping verification")
        return
    actual = sha256_of(dest_path)
    if actual.lower() != expected.lower():
        raise SystemExit(f"Checksum mismatch for {name}: expected {expected}, got {actual}")
    print(f"  checksum OK ({actual[:12]}...)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", required=True, choices=sorted(DATASETS))
    parser.add_argument("--list", action="store_true", help="List available files and exit")
    parser.add_argument("--files", nargs="+", help="Specific file names to download (default: all)")
    args = parser.parse_args()

    info = DATASETS[args.dataset]
    base_url = resolve_index_url(info)
    files = [e for e in list_dir(base_url) if not e.endswith("/")]

    if args.list:
        print(f"Files at {base_url}:")
        for f in files:
            print(f"  {f}")
        return

    if args.files:
        missing = [f for f in args.files if f not in files]
        if missing:
            raise SystemExit(f"Not found at {base_url}: {missing}\nRun with --list to see what's available.")
        to_fetch = args.files
    elif args.dataset == "mlhd":
        raise SystemExit(
            "mlhd is ~272GB across all shards — pass --files with specific shard names "
            "(e.g. mlhdplus-partial-0.tar) or run with --list to see options."
        )
    else:
        to_fetch = files

    dest_paths = {name: download_file(base_url, name, info["dest"]) for name in to_fetch}

    print("Verifying checksums...")
    for name in to_fetch:
        verify_file(base_url, name, dest_paths[name], files)


if __name__ == "__main__":
    main()
