#!/usr/bin/env python3
"""Process the sidewalk LAZ point cloud into a compact web-viewable binary.

Reads data/sidewalk_demo.laz, decimates it with an adaptive voxel grid, and
writes:

    viz/pc.bin        interleaved records, 25 bytes per point:
                      [0:12]   float32 x3   position (x, y, z)
                      [12:15]  uint8   x3   RGB colour
                      [15]     uint8        classification code
                      [16]     uint8        intensity (0-255)
                      [17:21]  float32      sidewalk_width_discrete (m)
                      [21:25]  float32      verticality (0=horizontal, 1=vertical)
    viz/manifest.json metadata for the visualiser (bounds, counts, legend).

Usage:
    python scripts/process_data.py [--input data/sidewalk_demo.laz]
                                   [--output viz] [--max-points 1500000]
"""
from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np
import laspy

RECORD_BYTES = 25

CLASS_NAMES = {
    0: "Not classified (noise / irrelevant)",
    1: "Objects and facades",
    2: "Sidewalk",
    5: "Tree cover",
    11: "Pavement",
}


def voxel_decimate(points: np.ndarray, max_points: float) -> tuple[np.ndarray, float]:
    """Adaptive voxel-grid decimation.

    Keeps the first point falling inside each voxel of side `size`, growing the
    voxel size until at most `max_points` points remain. Deterministic.
    """
    xyz = points
    lo = xyz.min(axis=0)
    for size in (0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0):
        keys = np.floor((xyz - lo) / size).astype(np.int64)
        keys *= np.array([np.iinfo(np.int64).max // (2**40 + 1),
                          2**20 + 1,
                          1])
        _, first = np.unique(keys.sum(axis=1), return_index=True)
        if len(first) <= max_points:
            sel = np.sort(first)
            return sel, size
    raise RuntimeError("Decimation failed even at 1 m voxels")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default="data/sidewalk_demo.laz")
    ap.add_argument("--output", default="viz")
    ap.add_argument("--max-points", type=int, default=1_500_000)
    args = ap.parse_args()

    src = pathlib.Path(args.input)
    outdir = pathlib.Path(args.output)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Reading {src} ...")
    las = laspy.read(src)
    header = las.header
    n_full = len(las)
    print(f"  {n_full:,} points, version {header.version}, point format {header.point_format.id}")

    xyz = np.column_stack([las.x, las.y, las.z]).astype(np.float32)
    rgb8 = (np.column_stack([las.red, las.green, las.blue]) >> 8).astype(np.uint8)
    cls = np.asarray(las.classification).astype(np.uint8)
    intensity = np.asarray(las.intensity).astype(np.uint8)
    width = np.asarray(las["sidewalk_width_discrete"]).astype(np.float32)
    vert = np.asarray(las["Verticality"]).astype(np.float32)

    counts_full = {int(c): int(k) for c, k in
                   zip(*np.unique(cls, return_counts=True))}

    print(f"Decimating to <= {args.max_points:,} points ...")
    sel, voxel_size = voxel_decimate(xyz, args.max_points)
    xyz, rgb8, cls, intensity, width, vert = (a[sel] for a in
                                              (xyz, rgb8, cls, intensity, width, vert))
    n = len(sel)
    print(f"  kept {n:,} points with {voxel_size} m voxels")

    # Interleaved binary: position, rgb, class, intensity, width, verticality.
    rec = np.zeros(n, dtype=np.dtype([
        ("xyz", np.float32, 3),
        ("rgb", np.uint8, 3),
        ("cls", np.uint8),
        ("intensity", np.uint8),
        ("width", np.float32),
        ("vert", np.float32),
    ]))
    assert rec.itemsize == RECORD_BYTES, f"record size {rec.itemsize} != {RECORD_BYTES}"
    rec["xyz"] = xyz
    rec["rgb"] = rgb8
    rec["cls"] = cls
    rec["intensity"] = intensity
    rec["width"] = width
    rec["vert"] = vert
    bin_path = outdir / "pc.bin"
    rec.tofile(bin_path)
    print(f"Wrote {bin_path} ({bin_path.stat().st_size / 1e6:.1f} MB)")

    counts_sampled = {int(c): int(k) for c, k in
                      zip(*np.unique(cls, return_counts=True))}
    manifest = {
        "source_url": "https://data.ifpedestrians.org/etc/sidewalk_demo.laz",
        "source_attribution": "Point cloud (c) International Federation of "
                              "Pedestrians (IFP). Shared for demonstration and "
                              "teaching purposes; contact IFP for reuse beyond "
                              "that scope.",
        "scan": {
            "location": "Jozsef Street, Budapest",
            "method": "handheld terrestrial laser scanning (street section, "
                      "captured on foot)",
            "date": "2026-05",
        },
        "full_point_count": n_full,
        "point_count": n,
        "voxel_size_m": voxel_size,
        "bounds_min": [float(v) for v in header.mins],
        "bounds_max": [float(v) for v in header.maxs],
        "classes": {str(k): {"name": CLASS_NAMES[k], "count_full": counts_full.get(k, 0),
                             "count_sampled": counts_sampled.get(k, 0)}
                    for k in sorted(set(counts_full) | set(counts_sampled))},
        "fields": {
            "width": "sidewalk_width_discrete: usable clear width in metres, "
                     "aggregated along the sidewalk axis (lower = tighter)",
            "verticality": "0 = horizontal surface, 1 = vertical surface",
            "intensity": "near-infrared return strength, 0-255",
        },
        "bin": {"path": "pc.bin", "record_bytes": RECORD_BYTES,
                "layout": ["xyz:3:f32", "rgb:3:u8", "cls:1:u8",
                           "intensity:1:u8", "width:1:f32", "vert:1:f32"]},
    }
    mpath = outdir / "manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {mpath}")


if __name__ == "__main__":
    main()
