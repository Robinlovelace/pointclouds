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
    2: "Sidewalk (pedestrian footway)",
    5: "Tree cover",
    11: "Pavement (roadway / carriageway)",
}


def voxel_decimate(points: np.ndarray, max_points: float) -> tuple[np.ndarray, float]:
    """Adaptive voxel-grid decimation.

    Keeps the first point falling inside each voxel of side `size`, growing the
    voxel size until at most `max_points` points remain. Deterministic. The
    voxel key is a mixed-radix integer (ix * ny * nz + iy * nz + iz), which is
    injective by construction, unlike a composite-linear key.
    """
    xyz = points
    lo = xyz.min(axis=0)
    for size in (0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0):
        idx = np.floor((xyz - lo) / size).astype(np.int64)
        nx, ny, nz = (int(v) for v in (idx.max(axis=0) + 1))
        if nx * ny * nz >= 2**63:
            continue  # would overflow int64 keys; try a larger voxel size
        keys = (idx[:, 0] * ny + idx[:, 1]) * nz + idx[:, 2]
        _, first = np.unique(keys, return_index=True)
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
    if not src.is_file():
        raise SystemExit(f"Input not found: {src}\n"
                         "Run scripts/download_data.py first (see README.md).")
    outdir = pathlib.Path(args.output)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Reading {src} ...")
    las = laspy.read(src)
    header = las.header
    n_full = len(las)
    print(f"  {n_full:,} points, version {header.version}, point format {header.point_format.id}")

    required = ["sidewalk_width_discrete", "Verticality"]
    missing = [d for d in required if d not in las.point_format.dimension_names]
    if missing:
        available = [d.name for d in las.point_format.dimensions]
        raise SystemExit(f"This LAZ lacks the expected extra dimension(s) {missing}.\n"
                         f"Dimensions present: {available}")

    xyz = np.column_stack([las.x, las.y, las.z]).astype(np.float32)
    if not np.isfinite(xyz).all():
        finite = np.isfinite(xyz).all(axis=1)
        print(f"  dropping {(~finite).sum():,} points with non-finite coordinates")
        xyz = xyz[finite]
        las.points = las.points[finite]
    rgb8 = (np.column_stack([las.red, las.green, las.blue]) >> 8).astype(np.uint8)
    intensity = np.asarray(las.intensity)
    # LAS intensity may be 8- or 16-bit depending on the source; scale
    # consistently into 0-255 rather than truncating mod 256.
    if intensity.max() <= 255:
        intensity = intensity.astype(np.uint8)
    else:
        intensity = (intensity.astype(np.float32) / 65535 * 255).astype(np.uint8)
    cls = np.asarray(las.classification).astype(np.uint8)
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

    # Interleaved binary (little-endian): position, rgb, class, intensity,
    # width, verticality. NaN width/verticality means "no data" for that point
    # (the field is only computed where relevant); the viewer renders those as
    # grey rather than mapping them onto the colour ramps.
    rec = np.zeros(n, dtype=np.dtype([
        ("xyz", "<f4", 3),
        ("rgb", "u1", 3),
        ("cls", "u1"),
        ("intensity", "u1"),
        ("width", "<f4"),
        ("vert", "<f4"),
    ]))
    if rec.itemsize != RECORD_BYTES:
        raise RuntimeError(f"record size {rec.itemsize} != {RECORD_BYTES}")
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
            "location": "József Street, Budapest",
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
                     "aggregated along the sidewalk axis (lower = tighter); "
                     "NaN = not computed for this point (rendered grey)",
            "verticality": "0 = horizontal surface, 1 = vertical surface; "
                           "NaN = not computed (rendered grey)",
            "intensity": "near-infrared return strength, 0-255",
            "omitted": "the LAZ also carries 'object nr' (per-object segment id) "
                       "and 'sidewalk_width' (continuous clear width); neither "
                       "is needed for this viewer and both are dropped to keep "
                       "the binary compact",
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
