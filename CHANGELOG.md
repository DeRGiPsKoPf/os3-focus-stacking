# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Compute interface specification (interface version 1): normative document,
  TypeScript types and helper HTTP API in `docs/spec/`.
- `tools/check_upstream.py` with `tools/upstream-baseline.json` to report
  upstream OpenScan3 / OpenScan3-Client changes to the files the spec depends on.
- `python/`: `os3stack` reference implementation (Step 1): OS3 v0.13.0's
  calibration and merging ported 1:1, batch discovery, calibration record
  output, CLI `os3stack stack <scan-dir>`, unit tests on synthetic images.
- `os3stack compare` (Step 2's pixel-diff tool, pulled forward): max/mean
  absolute deviation and share of differing pixels between two images, with
  an explicit, documented per-pixel difference threshold.
- `os3stack stack --calibration FILE`: use an existing calibration record
  (ours or OS3's own `calibration_scanXX.json`) instead of calibrating, to
  compare just the merge step against OS3's own stacked output.
- Tiled merging (Step 2): `os3stack.tiling` (tile geometry) and
  `stack_batch(..., tile_plan=...)`, CLI flags `--tile-width`/`--tile-height`/
  `--tile-overlap`. Tiled and untiled output are bit-for-bit identical for
  image sizes divisible by 4 (a warning is raised otherwise).

### Fixed

- Tiled merging computed each tile's downscaled focus-sharpness map from
  that tile's own cropped pixels, which resamples on the wrong grid and
  disagreed with the untiled result almost everywhere in the tile (70-97%
  differing pixels on a real photo, though within tolerance on the
  checkerboard synthetic test). Fixed by computing each source's low-res
  focus energy once for the whole image and slicing/upsizing it per tile.
  See ROADMAP.md's Step 2 entry and `compute-interface.md` §3.4.
