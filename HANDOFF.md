# Handoff – current state of work

**Updated:** 2026-10-14 · last commit `d4ea2e1` (2026-10-14, roadmap: helper scope) · branch `main`, in sync with
`origin/main` (public)

## Current goal

**Step 3a – live stacking hookup** (see `ROADMAP.md`): the Stacking tab listens to OS3's WebSocket progress, picks a real
project/scan (replacing the mock batches), merges positions while the scan runs, two-stage deletion, `beforeunload`
warning, resume from the run file. Not started yet as far as the repo shows.

## Last state

- `d4ea2e1`, `e328783` `ROADMAP.md`: helper scope fixed as a small same-origin companion (`localhost:8742`);
  Android helper and server version dropped. `CHANGELOG.md` updated.
- `0875e8f`, `5d832e1` `README.md`: intro rewritten, status refreshed, local path removed.
- `82a9800` **Step 3**: Stacking tab against a mock compute backend – built in the local client clone
  (`client/`, branch `feature/stacking-tab`); in this repo only `docs/spec/compute-interface.ts` became a pointer and
  docs were updated.
- `88e0cb2`, `a8b4df8` **Step 2**: tiled merging, exact for any image size (`python/src/os3stack/stack.py`, `tiling.py`).
- 2026-10-14: `CLAUDE.md` and `HANDOFF.md` added. Tests were not run in this session.

## Open work (in order)

1. **Secure the Step 3 client work.** It exists only in a local `client/` clone that was never pushed (no fork yet).
   It is **not** in `%USERPROFILE%\Projects\os3-focus-stacking`. Where it lives now: unknown, needs clarifying.
   Until it's pushed (e.g. to a private fork of OpenScan3-Client), it can't be continued on another PC.
2. Run `python tools/check_upstream.py` and review upstream changes before starting 3a.
3. Step 3a as described in `ROADMAP.md`, including the manual folder-dialog test in Chrome/Edge left over from Step 3.
4. Confirm Step 1 on a real OS3 scan (file naming, 3-spread-batch calibration across positions, stack size ≠ 4).

## Known problems

- Step 3 code is not on GitHub (see above) – single point of failure.
- `docs/spec/helper-http-api.md` and spec §2/§6 still describe the superseded cross-origin pairing model; to be
  rewritten at the start of Step 6.
- Step 1/2 were verified on a 4-level bracket of a non-OS3 photo, never on a real OS3 scan (no OS3 device was available).

## Decisions pending

| Question | Options | Status |
|---|---|---|
| Where to push the client work | private fork of OpenScan3-Client · public fork · keep local until the PR | open |
| How the calibration pre-scan is started | own form in the Stacking tab · touch point in the Scan page (chained via `depends_on`) | decide in Step 3a |
| Upstream PR target branch | `develop` · `main` | confirm with maintainers before the PR |
| Port-aware API URL PR (`app/src/stores/apiConfig.ts`) | separate upstream PR · developer mode only | open, prerequisite for Step 6 |
| Overlap `AGENTS.md` / `ROADMAP.md` / `CLAUDE.md` / `HANDOFF.md` | keep all four (roles as in `CLAUDE.md`) · merge `AGENTS.md` into `CLAUDE.md` | open |
