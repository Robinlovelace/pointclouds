# pointclouds

An open teaching resource for working with 3D LiDAR point clouds of streets.

This repository contains the code to **download, process and visualise** a real
example point cloud: a handheld laser scan of a street section (József Street,
Budapest, May 2026), published by the International Federation of Pedestrians
(IFP) as a demonstration of their sidewalk survey workflow. The cloud carries
per-point **classification** codes, **sidewalk clear-width** estimates,
**verticality** and photographic colour, which makes it a good worked example
for learning how street-scene point clouds are analysed.

## Quick start

```bash
# 1. download the data (~370 MB compressed)
python scripts/download_data.py

# 2. decimate and convert to a compact web-friendly binary
python scripts/process_data.py

# 3. view (any static file server works, e.g.)
python -m http.server -d viz 8000
# then open http://localhost:8000
```

Python 3.10+ with `laspy`, `lazrs` and `numpy` is required:

```bash
pip install laspy lazrs numpy
```

No JavaScript build step is needed: the visualiser in `viz/` is plain HTML +
[three.js](https://threejs.org) loaded from a CDN.

## The data

- Source: <https://data.ifpedestrians.org/etc/sidewalk_demo.laz>
- 59,394,466 points, LAS 1.2 point format 2, compressed 371 MB (~2 GB decoded)
- Per-point fields used here:

| Field | Meaning |
| :--- | :--- |
| `X, Y, Z` | position in the scanner's local frame |
| `red, green, blue` | photographic colour from timelapse images |
| `classification` | 0 = not classified (noise/irrelevant), 1 = objects and facades, 2 = sidewalk, 5 = tree cover, 11 = pavement |
| `intensity` | near-infrared return strength |
| `sidewalk_width_discrete` | usable clear width (m), aggregated along the sidewalk axis |
| `Verticality` | 0 = horizontal surface, 1 = vertical surface |

## Repository layout

```
scripts/download_data.py   download the LAZ into data/ (not committed)
scripts/process_data.py    voxel-decimate and write viz/pc.bin + manifest.json
viz/index.html             self-contained three.js viewer (colour modes,
                           class visibility filters, point size)
viz/pc.bin, manifest.json  generated outputs (not committed; regenerate with
                           step 2 above)
```

The `data/` and `viz/pc.bin` outputs are gitignored: the cloud is large and
remains the property of IFP, so it is fetched from the source at run time
rather than stored here.

## Licences

- Code in this repository: MIT (see `LICENSE`).
- Point cloud data: (c) International Federation of Pedestrians (IFP), shared
  for demonstration and teaching purposes - consult IFP for any other reuse.
