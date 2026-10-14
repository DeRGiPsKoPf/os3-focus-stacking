# Handoff – current state of work

**Updated:** 2026-10-14 · branch `main`, in sync with `origin/main` (public) · last checked on the maintainer's desktop

## Current goal

**Step 3a – live stacking hookup** (see `ROADMAP.md`): the Stacking tab listens to OS3's WebSocket progress, picks a real
project/scan (replacing the mock batches), merges positions while the scan runs, two-stage deletion, `beforeunload`
warning, resume from the run file. Not started yet.

## Where the work lives

| What | Where | State |
|---|---|---|
| This repo | GitHub `DeRGiPsKoPf/os3-focus-stacking`, `main` | up to date |
| Step 3 client work | own repo `DeRGiPsKoPf/os3-stacking-client` (private), branch `feature/stacking-tab`, commit `e81ec19`, checked out next to this repo as `%USERPROFILE%\Projects\os3-stacking-client` | in sync with GitHub; remotes `origin` = upstream, `backup` = private repo. A public fork is created only for the upstream PR. Its own `HANDOFF.md` tracks the client state. |
| Base of the client branch | upstream `develop` at `d4da05e` (release 0.8.0) | upstream `develop` hasn't moved since (checked 2026-10-14) – no rebase needed |

Working copies: `%USERPROFILE%\Projects\os3-focus-stacking` and `%USERPROFILE%\Projects\os3-stacking-client` side by
side. Until 2026-10-14 the client lived inside this repo as `client/` (still gitignored). **On the laptop it is still
there:** move it out to `%USERPROFILE%\Projects\os3-stacking-client` (or delete it and clone the backup repo there),
then `git pull` in both. Gitignored, laptop only: `stack example/` (the 4-photo test bracket from Steps 1/2) and
`roadmap-focus-stacking.md`. `python/.venv` exists on neither machine yet; recreate it before running tests.

## Last state

- 2026-10-14: **history rewritten and force-pushed** so every commit shows only the noreply identity (no content
  changes except two scrubbed doc lines in `688b8eb`). All hashes from before that date changed; other clones must be
  re-cloned. Hashes below are the new ones.
- `14585b7`, `688b8eb` `CLAUDE.md` and `HANDOFF.md` added, then corrected to the actual state on the laptop.
- `f99138f`, `2b0a781` `ROADMAP.md`: helper scope fixed as a small same-origin companion (`localhost:8742`);
  Android helper and server version dropped; Windows/macOS/Linux equal targets. `CHANGELOG.md` updated.
- `b87f83c`, `6b095d4` `README.md`: intro rewritten, status refreshed, local path removed.
- 2026-10-14: client commit re-authored to the noreply identity (`4d40a6a` → `e81ec19`, same content) and pushed to
  the private backup repo; both repos now use `DeRGiPsKoPf <…@users.noreply.github.com>` as local git identity.
- `e2fb045` **Step 3**: Stacking tab against a mock compute backend (client commit now `e81ec19`, 8 files, +1008 lines:
  `app/src/stacking/`, `StackingPage.vue`, `components/stacking/StackingResultCard.vue`, one route, one nav entry).
- `853630f`, `3d64931` **Step 2**: tiled merging, exact for any image size (`python/src/os3stack/stack.py`, `tiling.py`).
- 2026-10-14: `python tools/check_upstream.py` run – watched files unchanged in both upstream repos (OpenScan3
  `develop` has 7 new commits since the baseline, none touching watched files; OpenScan3-Client `main` unchanged).
  Python tests were not run.

## Open work (in order)

1. Recreate `python/.venv` (see `CLAUDE.md` key commands; upgrade pip first, see `python/README.md`) and run `pytest`.
2. Step 3a as described in `ROADMAP.md`, including the manual folder-dialog test in Chrome/Edge left over from Step 3.
3. Confirm Step 1 on a real OS3 scan (file naming, 3-spread-batch calibration across positions, stack size ≠ 4).

## Known problems

- GitHub may keep the pre-rewrite commits reachable by their old hash for a while (unreferenced, not in any branch).
  Only GitHub Support can purge them early.
- `npm run dev`/`build` hasn't been re-run since the client moved (git state verified identical); on the desktop
  `npm install` hasn't been run yet.
- `tools/check_upstream.py` fails with "not a git repository" if its default cache folder in `%TEMP%` survives without
  its `.git` (seen 2026-10-14). Workaround: delete that folder or pass `--cache <empty dir>`.
- `docs/spec/helper-http-api.md` and spec §2/§6 still describe the superseded cross-origin pairing model; to be
  rewritten at the start of Step 6.
- Step 1/2 were verified on a 4-level bracket of a non-OS3 photo, never on a real OS3 scan (no OS3 device was available).

## Decisions pending

| Question | Options | Status |
|---|---|---|
| How the calibration pre-scan is started | own form in the Stacking tab · touch point in the Scan page (chained via `depends_on`) | decide in Step 3a |
| Upstream PR target branch | `develop` (the client branch is already based on it) · `main` | confirm with maintainers before the PR |
| Port-aware API URL PR (`app/src/stores/apiConfig.ts`) | separate upstream PR · developer mode only | open, prerequisite for Step 6 |
| Overlap `AGENTS.md` / `ROADMAP.md` / `CLAUDE.md` / `HANDOFF.md` | keep all four (roles as in `CLAUDE.md`) · merge `AGENTS.md` into `CLAUDE.md` | open |
