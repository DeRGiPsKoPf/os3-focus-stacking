# AGENTS.md

## Project

Focus Stacking outside the Pi — a web interface that processes focus stacks
from [OpenScan3](https://github.com/OpenScan-org/OpenScan3), runs live during
the scan, and embeds the existing OS3 web UI. It's built as an additive
extension of `OpenScan3-Client` (Vue.js SPA), not a fork or an iframe, with
the goal of an upstream PR. The `OpenScan3` firmware itself is not modified.

Full plan, rationale, and open questions: [ROADMAP.md](ROADMAP.md). Read it
first in any new session; update it as steps complete. The compute interface
every step builds on is specified in [docs/spec/](docs/spec/).

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
- Alignment (CPU, produces a 2×3 affine matrix per focus step) and merging
  (moves to GPU/browser) stay separate. Transforms are always passed as a 2×3
  matrix in OpenCV layout (`[[a, b, c], [d, e, f]]`, maps output → source
  pixels), never backend-specific. Older text saying "3×2" means the same
  six numbers.
- Calibration batches: completed scans use 3 batches spread over the scan
  (like OS3); live scans use the first 3 completed positions by default, or —
  toggle — a separate 3-position calibration pre-scan before the main scan.
- Tiling from the start; tile size/overlap are multiples of 4 px, overlap
  ≥ 16 px (definition: [docs/spec/compute-interface.md](docs/spec/compute-interface.md) §3.4).
- 8 bits per channel for the browser/helper base version, permanently — not
  a stepping stone to 16-bit. The interface still always carries the number
  format as an explicit parameter.
- Live stacking merges each position as soon as it's captured, in parallel
  with the next shot.
- Two-stage deletion on the Pi (finish + confirm on disk by byte-exact
  re-read, then delete originals), toggleable, never based on "task
  succeeded" alone, never while an OS3-side focus stacking task for the same
  scan is pending/running (the client's "auto-start focus stacking" option).
- New tab/route in `OpenScan3-Client`, shipped as a regular part of that
  project, not a separate deployment.
- `beforeunload` tab-close warning while a stacking run is active (browser
  compute path has no persistence otherwise).
- Storage target chosen once per scan via the File System Access API
  (Chromium, secure context only); Firefox/Safari fall back to per-image
  downloads (no deletion possible then). Helper path uses a fixed configured
  directory.
- Compute path priority: browser first, then a Windows/Mac helper, Android
  only if at all (no background-process option there).

## Repository layout

```
os3-focus-stacking/            (this repo)
├── ROADMAP.md, AGENTS.md, README.md, CHANGELOG.md, LICENSE
├── docs/spec/                 Step 0: compute interface (normative), TS types, helper HTTP API
├── tools/                     repo maintenance: upstream change check
├── python/                    Steps 1, 2, 6: one Python project (created in Step 1)
│   ├── pyproject.toml
│   ├── src/os3stack/          port of OS3 stacking.py, tiling, compare tool, reference CLI, helper/
│   └── tests/
└── client/                    local clone of OpenScan3-Client (gitignored, own repo; Step 3+)
```

- `client/` is a plain clone of the upstream `OpenScan3-Client`, not a
  submodule. Our work lives on a feature branch there, rebased regularly
  onto upstream. A GitHub fork is added as a second remote only when pushing
  is needed (backup/PR); install the `gh` CLI at that point.
- Client code goes to `app/src/stacking/`, `app/src/pages/StackingPage.vue`,
  `app/src/components/stacking/`. Touch points in existing client code stay
  minimal: one route in `app/src/router/routes.ts`, one nav entry in
  `app/src/layouts/MainLayout.vue`, strings in `app/src/i18n/en-US/index.ts`.
- Test scans are never stored in the repo; scripts take their location as an
  argument.
- The working copy lives in Google Drive by the maintainer's choice; don't
  move it.

## Upstream tracking

OpenScan3 and OpenScan3-Client are under active development. At the start of
every step, run:

```
python tools/check_upstream.py
```

It reports upstream commits that touch the files our spec depends on
(`tools/upstream-baseline.json`), exit code 1 if any changed. Review them
(`--diff` shows the full diff), update spec/code if needed, then move the
baseline forward in `tools/upstream-baseline.json`.

## Steps and test expectations

See [ROADMAP.md](ROADMAP.md) for full detail per step. Summary of what
"done" means for each:

| Step | Deliverable | Test |
|---|---|---|
| 0 | Folder structure + interface (`calibrate`, `stackBatch`) defined — done, see `docs/spec/` | none, pure spec |
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
- OS3 CORS is fully open (`allow_origins=["*"]`); a browser UI can read
  directly from the Pi.
- Photo names: `scanXX_NNN_fsSS.jpg`. `NNN` is OS3's original path index, not
  the capture order; `SS` is 0-based. Stack size comes from
  `scan.settings.focus_stacks`.
- A scan-task progress event means that position's photos are saved (OS3
  awaits each save before reporting progress).
- `DELETE /projects/{name}/{scan_index}/photos` already exists for deleting
  originals; no firmware change needed.
- There is no endpoint to write results back to the Pi; results stay on the
  chosen storage target.
- `showDirectoryPicker`, `crypto.subtle` and WebGPU need a secure context
  (HTTPS or localhost). The client dev server on localhost qualifies.
- Known upstream bug: `FocusStacker.calibrate()` doesn't set
  `self.transforms` — pass matrices explicitly to `stack()`.
