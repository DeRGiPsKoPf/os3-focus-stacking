# AGENTS.md

## Project

Focus Stacking outside the Pi — a web interface that processes focus stacks
from [OpenScan3](https://github.com/OpenScan-org/OpenScan3), runs live during
the scan, and embeds the existing OS3 web UI. It's built as an additive
extension of `OpenScan3-Client` (Vue.js SPA), not a fork or an iframe, with
the goal of an upstream PR. The `OpenScan3` firmware itself is not modified.

Full plan, rationale, and open questions: [ROADMAP.md](ROADMAP.md). Read it
first in any new session; update it as steps complete.

## Language

The project is programmed entirely in English (code, comments, commit
messages, docs) so the repo is publicly readable. Prompts from the
maintainer may be in German or English — that doesn't change the output
language of the project.

## Fixed decisions (short form — see ROADMAP.md for full rationale)

- Stacking algorithm matches OpenScan3's own
  (`openscan_firmware/utils/photos/stacking.py`, v0.13.0): ECC affine
  alignment once per scan, then per position warp → Laplacian² sharpness →
  per-pixel maximum selection.
- Alignment (CPU, produces a 3×2 matrix per focus step) and merging (moves to
  GPU/browser) stay separate. Transforms are always passed as a 3×2 matrix,
  never backend-specific.
- Tiling from the start; tile size/overlap are multiples of 4 px, overlap
  ≥ 16 px.
- 8 bits per channel for the browser/helper base version, permanently — not
  a stepping stone to 16-bit. The interface still always carries the number
  format as an explicit parameter.
- Live stacking merges each position as soon as it's captured, in parallel
  with the next shot.
- Two-stage deletion on the Pi (finish + confirm on disk, then delete
  originals), toggleable, never based on "task succeeded" alone.
- New tab/route in `OpenScan3-Client`, shipped as a regular part of that
  project, not a separate deployment.
- `beforeunload` tab-close warning while a stacking run is active (browser
  compute path has no persistence otherwise).
- Storage target chosen once per scan via the File System Access API
  (Chromium); Firefox/Safari fall back to per-image downloads. Helper path
  uses a fixed configured directory.
- Compute path priority: browser first, then a Windows/Mac helper, Android
  only if at all (no background-process option there).

## Steps and test expectations

See [ROADMAP.md](ROADMAP.md) for full detail per step. Summary of what
"done" means for each:

| Step | Deliverable | Test |
|---|---|---|
| 0 | Folder structure + interface (`calibrate`, `stackBatch`) defined | none, pure spec |
| 1 | Python reference CLI stacking script | run on a real scan, inspect result |
| 2 | Tiling logic + pixel-diff comparison tool | tiled vs. untiled: <0.5% differing pixels, <0.01/255 mean deviation |
| 3 | "Stacking" tab in `OpenScan3-Client`, no real compute | works against a mocked compute path |
| 3a | Live hookup via OS3 WebSocket, two-stage delete, beforeunload | full live scan keeps up, only final stack waits |
| 4 | Pyodide (Python-in-browser) compute | matches Step 1 output |
| 5 | WebGPU compute, tiled | matches Step 4 within Step 2's tolerance |
| 6 | Windows/Mac helper (HTTP, same interface) | full scan from the Pi, abort/resume |
| 6a | Auto helper-detection, Android (lowest priority) | — |
| 7 | Server-hosted helper + login | — |

## Notes for implementers

- `OpenScan3` (firmware) and `OpenScan3-Client` (web UI) are separate repos;
  this project only touches the latter.
- OS3 CORS is fully open (`allow_origins=["*"]"`); a browser UI can read
  directly from the Pi.
- `DELETE /projects/{name}/{scan_index}/photos` already exists for deleting
  originals; no firmware change needed.
- There is no endpoint to write results back to the Pi; results stay on the
  chosen storage target.
- Known upstream bug: `FocusStacker.calibrate()` doesn't set
  `self.transforms` — pass matrices explicitly to `stack()`.
