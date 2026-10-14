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
  **Critical implementation rule (learned the hard way in Step 2, two bugs
  deep):** the focus-sharpness map MUST be computed once per whole source
  image and sliced per tile — never recomputed from a tile's own cropped
  pixels, which resamples on the wrong grid and disagrees with the untiled
  result almost everywhere in the tile, not just near its edges. Prefer
  slicing the *full-resolution* map (exact for any image size — what
  `python/`'s CPU reference does) over slicing a low-res map and upsizing
  per tile (only exact when image width/height are multiples of 4 — needed
  for memory/texture-limited backends like WebGPU that can't hold a
  full-resolution map per source; pad to the next multiple of 4 and crop
  back if the input doesn't already conform).
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
- Compute path priority: browser first, then the helper — Windows, macOS
  and Linux as equal targets.
- Helper scope: a small, optional companion, never a second control UI. It
  reverse-proxies the Pi's own OpenScan3-Client at `localhost:8742` (same
  origin as its API under `/helper/v1/`), adds compute, storage and runs
  that outlive the tab, never moves hardware or starts scans. The Stacking
  tab turns helper features on per capability flag from
  `/helper/v1/health`; no other OS3 page knows about the helper.
- No server version of the helper: server-side processing is covered by
  OpenScan Cloud.

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
os3-stacking-client/           sibling folder: OpenScan3-Client clone with the Stacking tab (own repo; Step 3+)
```

- `os3-stacking-client` is a plain clone of the upstream `OpenScan3-Client`,
  checked out next to this repo (not inside it, not a submodule). Our work
  lives on branch `feature/stacking-tab`, rebased regularly onto upstream.
  Remotes: `origin` = the private `DeRGiPsKoPf/os3-stacking-client` (a plain
  clone sets this up), `upstream` = `OpenScan-org/OpenScan3-Client` (add it
  once, push URL disabled). A public fork is created only for the upstream PR.
- Client code goes to `app/src/stacking/`, `app/src/pages/StackingPage.vue`,
  `app/src/components/stacking/`. Touch points in existing client code stay
  minimal: one route in `app/src/router/routes.ts`, one nav entry in
  `app/src/layouts/MainLayout.vue`. (No i18n strings: the client uses plain
  English strings in every page, vue-i18n is only boilerplate.) Browser
  globals missing from the client's hand-maintained ESLint allowlist are
  declared per file with `/* global ... */`, not by editing `eslint.config.mjs`.
- The compute interface's TypeScript types live in the client at
  `app/src/stacking/compute/types.ts`; `docs/spec/compute-interface.ts` is
  only a pointer to them now.
- Test scans are never stored in the repo; scripts take their location as an
  argument.
- Keep the working copies — and especially `os3-stacking-client/app/node_modules` and
  `python/.venv` — out of cloud-synced folders (e.g. Google Drive): a sync
  client can lock files in `node_modules` mid-write and make `npm install`
  fail reproducibly (`EPERM`/`EBADF`). Moved off Google Drive to a local
  folder on 2026-09-28 for this reason.

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
| 6 | Helper on Windows/macOS/Linux: reverse proxy for the Pi's UI + compute + runs | full scan from the helper-hosted UI on all three OSes, abort/resume |
| 6a | Same-origin helper detection, features per capability flag | — |

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
- Client development needs Node 22 (`package.json` requires `^22 || ^20`, so
  not the current LTS 24): `cd ../os3-stacking-client/app`, `npm install`, then `npm run dev`
  (localhost) or `npm run build`. The build runs ESLint as a gate; the client
  does not type-check `.vue` files, and upstream already has `tsc` errors of
  its own — check only that none come from `src/stacking` or our pages.
- Known upstream bug: `FocusStacker.calibrate()` doesn't set
  `self.transforms` — pass matrices explicitly to `stack()`.
