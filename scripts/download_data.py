#!/usr/bin/env python3
"""Download the demo sidewalk LiDAR point cloud (LAZ).

Fetches the example point cloud published by the International Federation of
Pedestrians (IFP) from:

    https://data.ifpedestrians.org/etc/sidewalk_demo.laz

The file (~370 MB compressed, ~2 GB decompressed) is a handheld mobile-mapping
scan of a street segment, used here as an open teaching example. The data
remains (c) IFP; this repository only stores the code to download, process and
visualise it.

Usage:
    python scripts/download_data.py [--url URL] [--out data/]
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "https://data.ifpedestrians.org/etc/sidewalk_demo.laz"
DEFAULT_OUT = "data/sidewalk_demo.laz"
CHUNK = 1024 * 1024


def sha256_file(path: pathlib.Path, chunk: int = CHUNK) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def download(url: str, out: pathlib.Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")

    def progress(blocks: int, block_size: int, total: int) -> None:
        if total > 0:
            done = min(blocks * block_size, total)
            sys.stdout.write(f"\rDownloading {done / 1e6:7.1f} / {total / 1e6:.1f} MB")
        else:
            sys.stdout.write(f"\rDownloading {blocks * block_size / 1e6:7.1f} MB")
        sys.stdout.flush()

    print(f"Source: {url}")
    try:
        urllib.request.urlretrieve(url, tmp, reporthook=progress)
    except (urllib.error.URLError, OSError) as e:  # network or DNS failure
        sys.stdout.write("\n")
        raise SystemExit(f"Download failed: {e}\n"
                         "Check your network connection and that the source URL is reachable.")
    sys.stdout.write("\n")
    tmp.replace(out)
    size = out.stat().st_size
    digest = sha256_file(out)
    print(f"Saved {out} ({size / 1e6:.1f} MB)")
    print(f"sha256: {digest}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default=DEFAULT_URL, help=f"Source URL (default: {DEFAULT_URL})")
    ap.add_argument("--out", default=DEFAULT_OUT, help=f"Output path (default: {DEFAULT_OUT})")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    if out.exists():
        print(f"{out} already exists ({out.stat().st_size / 1e6:.1f} MB); "
              "delete it to re-download.")
        return
    download(args.url, out)


if __name__ == "__main__":
    main()
