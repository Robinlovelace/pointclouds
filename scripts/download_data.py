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
TIMEOUT_S = 120

# Digest and size of the file as published on 2026-11-20; a mismatch means the
# source changed (or was replaced) and should be inspected before use.
EXPECTED_SHA256 = "72e5c0d5955904d341faeafcffda6f91a58ae9d106d97965c1978fcf9bbdfbf6"
EXPECTED_SIZE_BYTES = 371_501_974


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
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pointclouds/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp, tmp.open("wb") as f:
            if resp.status != 200:
                raise SystemExit(f"Download failed: HTTP {resp.status} for {url}")
            length = resp.headers.get("Content-Length")
            total = int(length) if length and length.isdigit() else 0
            done = 0
            while True:
                block = resp.read(CHUNK)
                if not block:
                    break
                f.write(block)
                done += len(block)
                if total:
                    sys.stdout.write(f"\rDownloading {done / 1e6:7.1f} / {total / 1e6:.1f} MB")
                else:
                    sys.stdout.write(f"\rDownloading {done / 1e6:7.1f} MB")
                sys.stdout.flush()
        sys.stdout.write("\n")
        tmp.replace(out)
    except (urllib.error.URLError, OSError) as e:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"Download failed: {e}\n"
                         "Check your network connection and that the source URL is reachable.")
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

    size = out.stat().st_size
    digest = sha256_file(out)
    print(f"Saved {out} ({size / 1e6:.1f} MB)")
    print(f"sha256: {digest}")
    if digest != EXPECTED_SHA256:
        raise SystemExit(
            f"Checksum mismatch: expected {EXPECTED_SHA256} (as published 2026-11-20).\n"
            f"Got {digest}. The source file may have changed - inspect it before use,\n"
            "or update EXPECTED_SHA256 in this script if the new file is verified.")
    if size != EXPECTED_SIZE_BYTES:
        print(f"Warning: size {size} differs from the published {EXPECTED_SIZE_BYTES} bytes.")


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
