# Dörtyol Reality Engine

Truth-first digital twin prototype for Dörtyol, Hatay and the western Amanos Mountains.

## Current live layers
- 3D terrain from the public AWS Terrain Tiles dataset.
- OpenStreetMap context.
- Panoramax federated STAC viewer for real geotagged ground imagery.
- Mobile walk-style camera controls.

## Non-negotiable rule
No generated scenery is allowed to masquerade as reality. Areas without verified ground imagery remain TERRAIN ONLY / UNKNOWN.

## Cloud pipeline
The `Dörtyol Reality Coverage Scan` GitHub Action scans the Dörtyol–Amanos working envelope for public ground imagery and writes `coverage.json`. Future adapters will add authorized Mapillary data and user-supplied phone/360/drone captures, then feed verified images into MapAnything/VGGT-Ω -> GLOMAP/COLMAP -> gsplat -> 3D Tiles.
