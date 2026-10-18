# Handoff – current state of work

**Updated:** 2026-10-18 · branch `main`, in sync with `origin/main` (public) · session on the laptop

## Current goal

**Step 3a – live stacking hookup** (see `ROADMAP.md`): done except the calibration pre-scan; two-stage deletion is
built but not yet tried on the scanner.
After that: Step 4 (Pyodide, real compute in the browser), then Step 4a (HTTPS on the Pi).

## Where the work lives

| What | Where | State |
|---|---|---|
| This repo | GitHub `DeRGiPsKoPf/os3-focus-stacking`, `main` | up to date |
| Client work | own repo `DeRGiPsKoPf/os3-stacking-client` (private), branch `feature/stacking-tab`, checked out next to this repo as `%USERPROFILE%\Projects\os3-stacking-client` | in sync with GitHub; its own `HANDOFF.md` tracks the client state |
| Base of the client branch | upstream `develop` at `d4da05e` (release 0.8.0) | unchanged upstream (checked 2026-10-15) |
| Test scanner | `http://openscan.local` (HTTP only, API v0.9) | projects `testscan1`, `testscan2` (10 pos.), `testscan3` (100 pos.), all 4 focus steps |

Desktop: `python/.venv` exists, Node 22.23.2 installed via winget, `npm install` done in the client; dev server entry
`client-dev` in `%USERPROFILE%\Projects\.claude\launch.json`.
**Laptop** (prepared 2026-10-17): both repos pulled, no `client\` left inside this repo, client remotes renamed to
`origin` (private) / `upstream` (push disabled); `python/.venv` created (`pytest` 54 passed); Node 22.23.2 (winget),
`npm install` + `npm run build` OK; `client-dev` entry in `%USERPROFILE%\Projects\.claude\launch.json` – start Claude
sessions in `%USERPROFILE%\Projects` so it is found. Not run on the laptop: dev server against the scanner.

## Last state

- 2026-10-18 (laptop): **two-stage deletion** in the client (`56a00d8`, details in its `HANDOFF.md`); here `ad1e16e`:
  spec §5.4 run-file entries get optional `originalsDeletedAt`, a missing result whose originals are gone is reported
  as lost instead of re-stacked; `CHANGELOG.md`. `tools/check_upstream.py`: watched files unchanged (OS3 now at
  `v0.13.2`, 12 commits past the baseline; client unchanged). Firmware read for the delete endpoint: OS3 removes file,
  metadata and the `scan.photos` entry; its scan task resumes by `current_step`, so deleting doesn't trigger a recapture.
- `efe64d9` `ROADMAP.md`/`CHANGELOG.md`: Step 3a status and the local Source.
- `967d971` spec §5.4: run file format and resume rules (calibration reused, new calibration → new run file, entries
  checked by length + SHA-256, rewritten after every position).
- `93d317d` `ROADMAP.md`: **HTTPS on the Pi becomes Step 4a** (the scanner serves HTTP only; nginx site belongs to the
  APT package `openscan3-system-config`, source not public). Plan: per-device self-signed certificate, nginx on 443
  next to an unchanged port 80, "Open the secure version" button in the Stacking tab; PR walkthrough in the roadmap.
- Client (details in its `HANDOFF.md`): live stacking of real scans (100-position test: each position picked up
  ≤ 0.3 s after OS3's event, run done 1 s after the scan), run file + resume, one-click continue after a closed tab,
  per-scan "last run" notice, **local folder as Source** (photos downloaded from the scanner, nothing on the Pi
  touched), UI wording "Source"/"Target", delete toggle behind a red confirmation dialog. Compute is still the mock
  backend (placeholder images).
- 2026-10-15: `pytest` 54 passed in the new `python/.venv`; `tools/check_upstream.py`: watched files unchanged.

## Open work (in order)

1. Step 3a: decide and build how the calibration pre-scan is started (see decisions pending).
2. Step 3a: try two-stage deletion on the scanner (not reachable from the laptop on 2026-10-18): flip
   `REAL_COMPUTE_AVAILABLE` locally (don't commit), use a throwaway scan only, live and finished; also check that
   deleting while OS3 is still capturing doesn't lose photo entries (scan task and delete both write `scan.json`).
3. Step 4 (Pyodide): real compute in the browser; the first real check of the whole client against the Python reference.
4. Step 4a: ask the maintainers where `openscan3-system-config` lives and whether they want HTTPS by default.
5. Confirm Step 1 on a real OS3 scan: download a `testscan*` folder and run `os3stack stack` on it.

## Known problems

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
| How the calibration pre-scan is started | own form in the Stacking tab · touch point in the Scan page (chained via `depends_on`) | decide in Step 3a |
| HTTPS-by-default on the Pi | as planned in Step 4a · maintainers prefer to do it themselves (then an issue) | ask maintainers before Step 4a |
| Upstream PR target branch | `develop` (our base) · `main` | confirm with maintainers before the PR |
| Port-aware API URL PR (`app/src/stores/apiConfig.ts`) | separate upstream PR · developer mode only | open, prerequisite for Step 6 |
| Overlap `AGENTS.md` / `ROADMAP.md` / `CLAUDE.md` / `HANDOFF.md` | keep all four · merge `AGENTS.md` into `CLAUDE.md` | open |
