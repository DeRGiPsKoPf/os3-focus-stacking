# Handoff – current state of work

**Updated:** 2026-10-19 (end of session) · branch `main`, in sync with `origin/main` (public) · session on the laptop,
no scanner at hand

## Current goal

**Step 4 – Pyodide, real stacking in the browser** (see `ROADMAP.md`): built and tested on real photos from a local
folder; everything left needs the scanner. Step 3a is done except trying two-stage deletion on the scanner; the
calibration pre-scan is deferred. Then Step 4a (HTTPS on the Pi).

## Where the work lives

| What | Where | State |
|---|---|---|
| This repo | GitHub `DeRGiPsKoPf/os3-focus-stacking`, `main` | up to date |
| Client work | own repo `DeRGiPsKoPf/os3-stacking-client` (private), branch `feature/stacking-tab`, checked out next to this repo as `%USERPROFILE%\Projects\os3-stacking-client` | in sync with GitHub; its own `HANDOFF.md` tracks the client state |
| Base of the client branch | upstream `develop` at `d4da05e` (release 0.8.0) | unchanged upstream (checked 2026-10-18) |
| Test scanner | `http://openscan.local` (HTTP only, API v0.9) | projects `testscan1`, `testscan2` (10 pos.), `testscan3` (100 pos.), all 4 focus steps |
| Test photos (not in git) | `stack example/` (ignored), see its `SOURCES.txt` | 3 real brackets as one-position OS3 scans in `stack example/os3/<project>/scan01`, reference results in `stacked/` |

Desktop: `python/.venv` exists (still OpenCV 5.0 there – run `pip install -e ".[dev]"` once to get the 4.11 pin), Node
22.23.2, `npm install` done in the client (run it again: it now also fetches Pyodide); dev server entry `client-dev` in
`%USERPROFILE%\Projects\.claude\launch.json`.
**Laptop:** both repos current; `python/.venv` with OpenCV 4.11.0.86 (`pytest` 55 passed); client `npm install` done,
`public/pyodide/` fetched. Start Claude sessions in `%USERPROFILE%\Projects` so `client-dev` is found (sessions in this
repo need a temporary `.claude/launch.json` with `--prefix ../os3-stacking-client/app`).

## Last state

- 2026-10-19 **Step 4** – here `9fc7c5f`, client `4891dd8` (details in its `HANDOFF.md`):
  - Pyodide 314.0.7 (OpenCV 4.11, numpy) runs everything `os3stack` needs, `findTransformECC` included.
  - **Reference pinned to `opencv-python-headless==4.11.0.86`** (`python/pyproject.toml`): OpenCV 5.0 merged 11–13 %
    of pixels differently from 4.11 on identical input; native 4.11 vs. Pyodide ≤ 0.012 %.
  - **JPEG in the browser:** Pyodide's OpenCV decodes 4.8 % of pixels differently (other JPEG library); Chromium's
    decoder and encoder match OpenCV's libjpeg-turbo pixel for pixel, EXIF orientation 3/6/8 included. So the worker
    decodes/encodes, Python only computes.
  - `os3stack`: injectable image loader (`calibrate(..., load=)`, `merge_batch`, `combine_batch_calibrations`),
    results byte-identical to before; `tools/sync_client_python.py` copies the modules into the client (`--check`).
  - Pyodide + numpy + OpenCV **bundled with the client** (~26 MB, offline-capable), decided by the maintainer.
  - Results (3 real brackets, 4–10 photos, 1–3 MP): merge with reference matrices 0.008–0.38 % differing pixels, mean
    ≤ 0.005/255; own calibration ≤ 0.0125 px from the reference; 9–14 s per run incl. Python start.
  - Spec §3.1/§7/§8 (sync, bundling, browser JPEG, calibration tolerance 0.05 px, end-to-end mean only), `ROADMAP.md`
    Step 4 status, `CHANGELOG.md`, `CLAUDE.md` (stack, architecture, decisions).
- 2026-10-19 `7ec805b`: **calibration pre-scan deferred**; full reasoning in `ROADMAP.md` "Open decisions".
- 2026-10-18: **two-stage deletion** (client `56a00d8`, spec §5.4 `originalsDeletedAt` here `ad1e16e`); firmware
  read: OS3's delete removes file, metadata and `scan.photos` entry; scan resume goes by `current_step`.
- Earlier: Step 3a live stacking, run file + resume, local Source (see `ROADMAP.md`).

## Open work (in order)

All of this **needs the scanner**:

1. Step 4 on the Pi: deploy the client build (or `npm run build` + copy) and check that nginx serves
   `/pyodide/v314.0.7/pyodide.mjs` as JavaScript and `.wasm` as `application/wasm` (`curl -I`); then a live run.
2. Memory at the real size: 16 MP × 12 steps (the reference pre-warps every step, ~1.3 GB in WebAssembly; limit 4 GB).
3. Compare with OS3's own output: let OS3 stack a test scan, download it, `os3stack compare` (with
   `os3stack stack --calibration <OS3's calibration_scanXX.json>` to separate merge from calibration). Read the Pi's
   OpenCV version: `python3 -c "import cv2; print(cv2.__version__)"`.
4. Download `testscan3` (100 positions): confirm Step 1, measure `leading` vs. `spread` (decides the pre-scan;
   `os3stack` needs a small option to calibrate from the first 3 positions).
5. Two-stage deletion on a throwaway scan: set `DELETION_ENABLED = true` in the client's `store.ts` locally (don't commit
   until tested); live and finished; deleting while OS3 still captures must not lose `scan.photos` entries.
6. Step 4a: ask the maintainers where `openscan3-system-config` lives and whether they want HTTPS by default.

## Known problems

- Not verified against OS3's own stacked output yet (item 3); "same quality" is expected, not proven.
- OS3 v0.9 sends tasks over `/ws/tasks` without `run_args`; the client matches the scan task by `scan.task_id` instead.
  Upstream's own `taskUtils` (`getScanIdentifier`) has the same blind spot – possibly worth an upstream issue.
- Folder dialog (`showDirectoryPicker`) needs Chrome/Edge or Brave with `brave://flags/#file-system-access-api`, and a
  secure context (`localhost` or HTTPS) – not the dev server's network URL, not the Pi's HTTP page.
- GitHub may keep the pre-rewrite commits (2026-10-14) reachable by old hash for a while; only GitHub Support can purge them.
- `tools/check_upstream.py` fails with "not a git repository" if its default `%TEMP%` cache survives without `.git`;
  pass `--cache <empty dir>`.
- `docs/spec/helper-http-api.md` and spec §2/§6 still describe the superseded cross-origin pairing; rewrite at Step 6.

## Decisions pending

| Question | Options | Status |
|---|---|---|
| Calibration pre-scan, if the measurement shows `leading` isn't good enough | Scan-page touch point as a separate upstream PR/issue (preferred) · own form in the Stacking tab | deferred 2026-10-19; decide after the measurement |
| If the Pi's nginx serves `.mjs` wrongly | load Pyodide's classic `pyodide.js` instead · ask for an nginx MIME entry (`openscan3-system-config`) | decide after the Pi check |
| HTTPS-by-default on the Pi | as planned in Step 4a · maintainers prefer to do it themselves (then an issue) | ask maintainers before Step 4a |
| Upstream PR target branch | `develop` (our base) · `main` | confirm with maintainers before the PR |
| Port-aware API URL PR (`app/src/stores/apiConfig.ts`) | separate upstream PR · developer mode only | open, prerequisite for Step 6 |
| Overlap `AGENTS.md` / `ROADMAP.md` / `CLAUDE.md` / `HANDOFF.md` | keep all four · merge `AGENTS.md` into `CLAUDE.md` | open |
