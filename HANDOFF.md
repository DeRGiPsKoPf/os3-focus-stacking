# Handoff – current state of work

**Updated:** 2026-10-15 · branch `main`, in sync with `origin/main` (public) · last worked on the maintainer's desktop

## Current goal

**Step 3a – live stacking hookup** (see `ROADMAP.md`), about half done: real scan selection and live stacking work
against the maintainer's scanner; still missing are the run file/resume (spec §5.4) and two-stage deletion (§5.3).

## Where the work lives

| What | Where | State |
|---|---|---|
| This repo | GitHub `DeRGiPsKoPf/os3-focus-stacking`, `main` | up to date |
| Client work | own repo `DeRGiPsKoPf/os3-stacking-client` (private), branch `feature/stacking-tab`, checked out next to this repo as `%USERPROFILE%\Projects\os3-stacking-client` | in sync with GitHub; its own `HANDOFF.md` tracks the client state |
| Base of the client branch | upstream `develop` at `d4da05e` (release 0.8.0) | unchanged upstream (checked 2026-10-15) |
| Test scanner | `http://openscan.local` (HTTP only, API v0.9) | projects `testscan1`, `testscan2` (10 pos.), `testscan3` (100 pos.), all 4 focus steps |

Desktop: `python/.venv` exists, Node 22.23.2 installed via winget, `npm install` done in the client.
**Laptop:** still has the old `os3-focus-stacking\client\` – delete it once `%USERPROFILE%\Projects\os3-stacking-client`
exists (check first that the old copy has nothing unpushed); `python/.venv` and Node there unknown.

## Last state

- 2026-10-15 `93d317d` `ROADMAP.md`/`CHANGELOG.md`: **HTTPS on the Pi becomes Step 4a.** The scanner serves HTTP only
  (port 443 closed); stock images have no HTTPS and the nginx site belongs to the APT package `openscan3-system-config`
  (source not public). Plan: per-device self-signed certificate created on the Pi, nginx on 443 next to an unchanged
  port 80, "Open the secure version" button in the Stacking tab; PR walkthrough in the roadmap.
- 2026-10-15 client `a437214`, `c2e6750`: Stacking tab stacks **real scans, live while they capture** (details in the
  client's `HANDOFF.md`). Live test on `testscan3` (100 positions, 4 focus steps, ~6.3 s per position): all 100
  positions stacked, each picked up ≤ 0.3 s after OS3's progress event, run finished 1 s after the scan. Compute is
  still the mock backend (placeholder images).
- 2026-10-15: `pytest` 54 passed in the new `python/.venv`; `tools/check_upstream.py`: watched files unchanged
  (OpenScan3 `develop` at `ee44b2b`, 7 commits past the baseline).

## Open work (in order)

1. Step 3a: run file + resume (spec §5.4).
2. Step 3a: two-stage deletion (spec §5.3) – implement, but keep it disabled while only the mock backend exists.
3. Manual folder-dialog test in Chrome/Edge at **`http://localhost:9000/stacking`** (not the dev server's network
   URL – that isn't a secure context). Settings are stored per origin: set host `openscan.local` there once.
4. Step 3a: decide and build the calibration pre-scan start (see decisions pending).
5. Step 4 (Pyodide), then Step 4a (HTTPS PR; first ask the maintainers where `openscan3-system-config` lives).
6. Confirm Step 1 on a real OS3 scan: copy a `testscan*` folder off the Pi and run `os3stack stack` on it.

## Known problems

- OS3 v0.9 sends tasks over `/ws/tasks` without `run_args`; the client matches the scan task by `scan.task_id` now.
  Upstream's own `taskUtils` (`getScanIdentifier`) has the same blind spot – possibly worth an upstream issue.
- GitHub may keep the pre-rewrite commits (2026-10-14) reachable by old hash for a while; only GitHub Support can purge them.
- `tools/check_upstream.py` fails with "not a git repository" if its default `%TEMP%` cache survives without `.git`;
  pass `--cache <empty dir>`.
- `docs/spec/helper-http-api.md` and spec §2/§6 still describe the superseded cross-origin pairing; rewrite at Step 6.
- Steps 1/2 were never run on a real OS3 scan yet (now possible: test scans exist on the Pi).

## Decisions pending

| Question | Options | Status |
|---|---|---|
| How the calibration pre-scan is started | own form in the Stacking tab · touch point in the Scan page (chained via `depends_on`) | decide in Step 3a |
| HTTPS-by-default on the Pi | as planned in Step 4a · maintainers prefer to do it themselves (then an issue) | ask maintainers before Step 4a |
| Upstream PR target branch | `develop` (our base) · `main` | confirm with maintainers before the PR |
| Port-aware API URL PR (`app/src/stores/apiConfig.ts`) | separate upstream PR · developer mode only | open, prerequisite for Step 6 |
| Overlap `AGENTS.md` / `ROADMAP.md` / `CLAUDE.md` / `HANDOFF.md` | keep all four · merge `AGENTS.md` into `CLAUDE.md` | open |
