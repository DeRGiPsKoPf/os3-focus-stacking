# OS3 Focus Stacking – project context

Quick reference: how does this project work? Current state of work: `HANDOFF.md`. Full plan, every step and
the reasoning behind each decision: `ROADMAP.md`. Implementer notes and repo layout: `AGENTS.md`.
Compute interface (normative): `docs/spec/compute-interface.md`.

## Project overview

Moves OpenScan3's focus stacking off the Raspberry Pi and into the browser tab that watches the scan: each turntable
position's focus bracket is stacked as soon as it is captured, so only the last position is left when the scan ends.
Delivered as an additive "Stacking" tab in `OpenScan3-Client` (Vue SPA), aimed at an upstream PR; the `OpenScan3`
firmware stays untouched. Audience: OpenScan3 users; maintainer is DeRGiPsKoPf.

## Tech stack

- **Python ≥ 3.11** reference implementation `os3stack` (`python/`): numpy, opencv-python-headless; pytest.
- **Client work** (Step 3+): Vue 3 + Quasar + Pinia + TypeScript in a local clone of `OpenScan3-Client` at `client/`
  (gitignored, its own repo). Needs **Node 22**. Not part of this repository.
- Planned compute paths: Pyodide (Step 4), WebGPU (Step 5), a local Python helper (Step 6).
- License GPL-3.0 (matches OpenScan3 and OpenScan3-Client).

## Architecture

```
docs/spec/        compute interface (calibrate, stackBatch, StackJob, tiling, storage targets), helper HTTP API
python/src/os3stack/
  core.py         OS3 v0.13.0 stacking primitives (ECC alignment, Laplacian² focus energy, max selection)
  calibrate.py    calibration batches → one 2×3 affine matrix per focus step
  stack.py        stack_batch(): warp → focus map → per-pixel selection, optional tile plan
  tiling.py       tile/processing-rect geometry (core + overlap)
  batches.py      batch discovery from OS3 file names scanXX_NNN_fsSS.jpg
  calibration_io.py  load an existing calibration record (ours or OS3's calibration_scanXX.json)
  imageio.py      decode/encode (cv2.imread semantics, EXIF orientation applied)
  compare.py      pixel-diff tool (max/mean deviation, share of differing pixels)
  cli.py          `os3stack stack` and `os3stack compare`
python/tests/     unit tests on synthetic images (_synthetic.py)
tools/check_upstream.py + upstream-baseline.json   reports upstream changes to files the spec depends on
client/           (gitignored) OpenScan3-Client clone, branch feature/stacking-tab
```

Alignment (CPU, once per scan) and merging (moves to GPU/browser later) are separate stages; every compute path takes
the same `StackJob` and must produce the same result as the Python reference.

## Conventions

- **Everything in English** (code, comments, commits, docs), even when prompts are in German.
- PEP 8, type hints, docstrings that explain *why* (see `stack.py`'s module docstring as the model).
- **Tests:** synthetic images only; real scans never go into the repo – scripts take their location as an argument.
  Every compute path is verified against the Python reference with `os3stack compare`
  (target: < 0.5 % differing pixels, mean deviation < 0.01·255). Test on a real photo too – both Step 2 bugs only
  showed up there.
- **Commits:** subject `Step N: …`, `Docs: …`, `Roadmap: …` (≤ ~70 chars), blank line, body explaining why.
  Notable changes also go into `CHANGELOG.md` (Keep a Changelog). Commits made by Claude end with `Co-Authored-By`.
- Client code only in `app/src/stacking/`, `app/src/pages/StackingPage.vue`, `app/src/components/stacking/`;
  touch points in existing client code: one route, one nav entry. Missing ESLint globals per file via `/* global */`.
- At the end of every session update only `HANDOFF.md` (and step status in `ROADMAP.md` when a step completes);
  change this file only when architecture, conventions or stack change.

## Key commands

```bash
python tools/check_upstream.py            # at the start of every step; --diff shows the full diff
cd python
python -m venv .venv && .venv\Scripts\activate     # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
pytest
os3stack stack <scan-dir> [--tile-width W --tile-height H --tile-overlap O] [--calibration FILE]
os3stack compare <image-a> <image-b>
# client (Step 3+, needs the local clone and Node 22)
cd client/app && npm install && npm run dev     # or: npm run build (runs ESLint as a gate)
```

No linter configured for `python/`. If `pip` fails with `SSLEOFError`, see `python/README.md`.

## Known pitfalls and decisions

| Decision | Why | Rejected |
|---|---|---|
| Same algorithm as OS3 `stacking.py` v0.13.0 | results must not change, only where/when they're computed | own/faster algorithm |
| Additive tab in OpenScan3-Client | mergeable upstream | fork, iframe, standalone app |
| Transforms always 2×3 affine, OpenCV layout | one format for every backend | backend-specific matrices ("3×2" in old text = same numbers) |
| 8 bit per channel, permanently for browser/helper base | keeps live scans feasible (~50–70 GB vs 100–350 GB) | 16-bit (deferred to a helper expansion) |
| Helper = small same-origin companion proxying the Pi's UI at `localhost:8742` | no second control UI, no CORS/pairing | desktop control app; cross-origin pairing (Step 0 design) |
| Two-stage deletion (byte-exact re-read, then delete) | never lose originals on a crash/disconnect | delete on "task succeeded" |

- **Tiling rule:** compute the focus map once per whole source image and slice it per tile – never recompute it from a
  tile's cropped pixels (Step 2, two bugs deep). WebGPU will need the low-res variant with width/height padded to multiples of 4.
- **Upstream bug:** `FocusStacker.calibrate()` doesn't set `self.transforms` – pass matrices explicitly.
- Photo names `scanXX_NNN_fsSS.jpg`: `NNN` is OS3's path index, not capture order; `SS` is 0-based.
- Keep the working copy (`client/app/node_modules`, `python/.venv`) out of cloud-synced folders (`EPERM`/`EBADF` on npm install).

## Do not touch / handle with care

- **`OpenScan3` firmware:** no changes planned; anything that seems to need one is a separate, explicit decision.
- **Existing OpenScan3-Client code** beyond the one route and one nav entry; don't edit `eslint.config.mjs`.
- **`docs/spec/compute-interface.md`** is normative – change it deliberately and keep `CHANGELOG.md` in sync.
- **`tools/upstream-baseline.json`:** move it forward only after reviewing the reported upstream changes.
- Never delete originals on the Pi while an OS3-side focus stacking task for the same scan is pending or running.
