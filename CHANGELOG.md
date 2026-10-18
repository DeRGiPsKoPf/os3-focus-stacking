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
  `--tile-overlap`. Tiled and untiled output are always bit-for-bit
  identical, for any image size and any tile size/overlap.
- Step 3, in the OpenScan3-Client clone (`client/`, branch
  `feature/stacking-tab`, not yet published): a "Stacking" tab running
  against a mock compute backend — storage-target selection, progress,
  per-position results with download, abort. The compute interface types
  moved there (`app/src/stacking/compute/types.ts`);
  `docs/spec/compute-interface.ts` is now a pointer.

- Step 3a (client): live stacking of real scans, resume from the run file,
  one-click continue after a closed tab, per-scan "last run" notice, local
  folder as Source, delete toggle behind a confirmation dialog.
- Spec §5.4: run file format (`stacking_run_scanXX.json`) and resume rules —
  calibration reused, new calibration starts a new run file, entries checked by
  length and SHA-256, rewritten after every position.
- Step 3a (client): two-stage deletion (spec §5.3) — originals deleted per
  position after its result and the calibration record are verified and no
  OS3 stacking task needs them; still locked while compute is the mock.
- Spec §5.4: optional `originalsDeletedAt` per run-file entry; a missing
  result whose originals are deleted is reported as lost, not re-stacked.

### Changed

- Calibration pre-scan (`calibration-scan` policy) deferred out of Step 3a:
  live stacking calibrates from the first 3 positions only, until a
  `leading` vs. `spread` measurement shows the pre-scan is needed (spec §4.2,
  ROADMAP.md "Open decisions").
- The OpenScan3-Client clone is now its own repository (`os3-stacking-client`),
  checked out next to this one instead of inside it as `client/`. Docs and the
  `compute-interface.ts` pointer refer to `../os3-stacking-client`.
- The working copy moved off Google Drive to a local folder: Drive's sync
  client locked files in `node_modules` mid-write and made `npm install`
  fail reproducibly.
- Roadmap: the helper's scope is fixed as a small, optional companion, not a
  second control UI. It reverse-proxies the Pi's own OpenScan3-Client at
  `localhost:8742` so the page and its API share one origin (replacing the
  cross-origin pairing design from Step 0), and the Stacking tab turns
  helper features on per capability. Windows, macOS and Linux are equal
  targets. The Android helper and the server version (Step 7, covered by
  OpenScan Cloud) are dropped. `tools/upstream-baseline.json` now also
  watches the client's `app/src/stores/apiConfig.ts`.
- Roadmap: HTTPS on the Pi is needed after all (stock OS3 images serve HTTP
  only; the 2026-09-27 "already HTTPS" finding no longer holds). New Step 4a:
  per-device self-signed certificate and nginx on 443 as an upstream PR to
  `openscan3-system-config`, port 80 unchanged, plus an "Open the secure
  version" button in the Stacking tab.

### Fixed

- Tiled merging computed each tile's downscaled focus-sharpness map from
  that tile's own cropped pixels, which resamples on the wrong grid and
  disagreed with the untiled result almost everywhere in the tile (70-97%
  differing pixels on a real photo, though within tolerance on the
  checkerboard synthetic test). First fix (compute low-res focus energy once
  for the whole image, slice+upsize per tile) brought this down to 48-54% on
  a real photo whose dimensions weren't multiples of 4, and to exactly 0%
  once they were — still an unconditional dependency on that precondition.
  Final fix: slice each source's already-*full-resolution* focus map per
  tile instead of a low-res one, which is exact for any image size — no
  precondition needed. See ROADMAP.md's Step 2 entry and
  `compute-interface.md` §3.4.
