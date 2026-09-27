# Roadmap: Focus Stacking outside the Pi

Status: 2026-09-27. This file is the starting point for every new session —
read it first, update it at the end.

## Goal

A web interface that processes focus stacks from OpenScan3, runs live during
the scan, and embeds the existing OS3 web UI alongside it (one tab "Scan" =
OS3 itself, one tab "Stacking" = our part).

**The target location is the client repo, not the firmware.** The OS3 web
interface is its own project, `OpenScan3-Client` (Vue.js SPA), separate from
the Python/FastAPI firmware in the `OpenScan3` repo. Our tab is added as an
additive extension to `OpenScan3-Client` (a new route/tab next to the
existing scan part), not as a fork or an iframe embedding someone else's
page — that way it's a regular, equal-standing part of the same Vue
application and easier to get accepted as a PR. The firmware itself
(`OpenScan3` repo) needs **no changes** — everything required already exists
(delete endpoint, permissive CORS setting, WebSocket progress). The only
foreseeable exception is HTTPS/certificates, see the dedicated section below.

**The page is served by the Pi itself** (row 1 below) — no separate web
server on the PC needed, nothing to install, usable immediately with any
device on the same network.

**Computation** happens, at the user's choice:

| Who serves the page | Who computes | When it makes sense |
|---|---|---|
| **Pi** (default) | **Browser** on the PC | no installation, the default case |
| **Pi** | **Helper**, if reachable locally (`localhost:<port>` responds) | large scans, once the helper is available |
| own Helper | Helper | special case, more relevant for server/Step 7 |

The middle row is a **later expansion** (see Step 6a): on load, the page
automatically checks whether a helper is running locally, and then uses it
transparently instead of browser computation — no manual switching, no
typing addresses. Until the helper runs on all target platforms, "browser
computes" remains the only path.

**Priority order of compute paths:** (1) Browser, (2) Helper on Windows +
Mac, (3) Android only if at all — see Step 6a.

All compute paths receive the same job and return the same result (see the
interface in Step 0).

## Fixed decisions

- **Algorithm:** the one from OpenScan3
  (`openscan_firmware/utils/photos/stacking.py`, v0.13.0). Alignment once per
  scan via ECC affine transform, then per position: warp → Laplacian² as
  sharpness measure → pick the sharpest image per pixel.
- **Alignment and merging stay separate.** Alignment always runs on the CPU
  and produces one 3×2 matrix per focus step. Only the merging step moves to
  GPU/browser.
- **Tiling from the start.** Any image size up to the native camera
  resolution. Tile size and overlap are multiples of 4 px (= 1 / the
  downscale factor of the sharpness map). Overlap at least 16 px.
- **Transforms are always passed as a 3×2 matrix**, never backend-specific.
- **8 bits per color channel to start, and permanently for the
  browser/helper base version.** 16-bit is **not** a near-term expansion
  step anymore — it's clearly assigned to the future helper+server
  collaboration (see the dedicated section below). 8-bit keeps the live
  scenario (400×12×16MP) at ~50–70 GB instead of 100–350 GB — that's what
  keeps the browser path realistically usable for the live case.
- **Live stacking during the scan, anchored in the browser part.** As soon as
  a position is fully photographed, merging that position starts, in
  parallel with the next shot. Capturing one position (12 levels) takes
  ~12–24 s, merging one position (8-bit) ~3 s — the computer spends most of
  the time waiting for new images, not the other way around. Only the final
  stack remains as pure waiting time after the scan ends.
- **Two-stage deletion on the Pi** (toggleable): (1) stack finished AND
  confirmed as a file on the target disk by reopening it, (2) only then call
  `DELETE /projects/{name}/{scan_index}/photos` with the original file
  names. Never delete solely because a "task succeeded" — protects against a
  connection drop/crash mid-save.
- **Additive extension of `OpenScan3-Client`**, not a fork/iframe. A new
  tab/route next to the existing scan UI, built and shipped as part of the
  same Vue project. Goal: mergeable upstream as a PR without touching
  existing code.
- **Tab-close protection:** a `beforeunload` warning with a confirmation
  dialog while a stacking run is active (the browser compute path otherwise
  has no persistence beyond closing the tab — that's the trade-off versus a
  standalone helper process).
- **Storage target selectable once per scan start, not per image:** the
  browser compute path uses the File System Access API (Chrome/Edge) — one
  folder dialog at scan start, after which the page keeps writing to that
  folder without further dialogs, live during the scan too. **Limitation:**
  this API doesn't exist in Firefox/Safari — falls back there to individual
  browser downloads per finished image (land in the default downloads
  folder, not the chosen one). Helper compute path: a fixed path as a text
  field in settings, since the helper is a standalone program with
  unrestricted file access anyway.

### On the 16-bit question (clearly deferred: helper+server expansion, not near-term)

- Belongs thematically to Step 6/7 (helper, server), not the browser core.
- The interface must still always carry the number format as a parameter,
  never assume it — costs nothing now, prevents silent 8-bit assumptions in
  the code, and keeps the path open for the later expansion.
- Internal computation runs in floating point (0.0–1.0) either way, that
  doesn't change with bit depth — only reading/writing gets swapped out for
  the expansion.
- At 16-bit, the browser can't read TIFF/RAW itself (needs a WASM decoder,
  e.g. libtiff/libraw), the data volume doubles, the helper becomes
  practically mandatory for large scans — fits together with server/Step 7,
  where memory and compute power aren't the browser's problem anymore
  anyway.

### On the HTTPS question: the only foreseeable firmware/system intervention

Concerns neither firmware logic nor client code, but the **Pi's system
configuration** (a front-end web server/reverse proxy, certificate, port) —
a single, clearly scoped building block.

- **Why it's needed:** modern browsers only allow certain performance
  features (SharedArrayBuffer, parallel Web Worker processing) over HTTPS,
  except on `localhost`. That's a browser security rule, not an OS3
  weakness — easy to justify, not a security problem that needs fixing.
- **Scope:** a self-signed certificate for a home-network device, an
  established pattern (comparable to router web UIs).
- **Timing:** only affects Step 5 (WebGPU with parallel web workers), not the
  earlier steps. Steps 0–4 run entirely without this discussion.
  Recommendation: file the PR for this only once the rest already works and
  has proven itself — a small, well-justified addition to a working feature
  is easier to get accepted than an upfront requirement.
- **Bar to clear:** must be integrated as solidly as the rest of the
  foundation, not bolted on as a quick hack.

## Open decisions

- Input format for a future 16-bit expansion (helper+server): 16-bit TIFF or
  RAW/DNG directly (smaller, but needs demosaicing)? Only relevant once
  Step 6/7 comes up.
- Write results back to the Pi? OS3 has no endpoint for that. Not a
  priority — results stay on the PC/chosen storage target. An additive PR
  against OS3 would be possible, but is its own, separate undertaking.

## Measured values (basis for all estimates)

Measured on 2 CPU cores, 16 MP images (4656×3496), native OpenCV:

| Operation | 8-bit | 16-bit |
|---|---|---|
| Merge per additional image | 249 ms | 297 ms |
| Peak memory, one stack | 543 MB | 683 MB |
| Reading a file | JPEG 193 ms (11 MB) | TIFF 351 ms (73 MB), PNG 810 ms (66 MB) |

At 16-bit, **reading** is the bottleneck, not computing — at 8-bit (the
current starting point), reading and computing are roughly equally
expensive.

Projection for the live scenario (400 positions × 12 levels × 16 MP, 8-bit,
2 cores as the baseline):

| Path | rough duration (only the final stack, since it's live) |
|---|---|
| Helper on an 8-core desktop | a few minutes |
| Browser with WebGPU | somewhat more, but within the time of one shot per position |
| Browser with Pyodide | critical — may no longer be "live", since it's slower than one shot takes |

## Steps

### Step 0 — Skeleton and interface
**Model:** Opus (architecture decision)
Define the folder structure, Git repo (fork of `OpenScan3-Client`), and the
interface every compute path must satisfy: `calibrate(batches) → matrices`
and `stackBatch(images, matrices, tilePlan, numberFormat) → resultImage`.
Also: how the page detects whether a helper is reachable locally (for
Step 6a), and how the storage target (folder handle or helper path) is
passed through the interface.
**Test:** none, pure specification.

### Step 1 — Reference in Python
**Model:** Sonnet
A small command-line script using OpenScan3's original code that stacks a
folder (8-bit). Serves as the **benchmark**: everything that later gets
dropped in the browser gets compared against this.
**Test:** run it on a real scan, look at the result.

### Step 2 — Tiling logic plus comparison tool
**Model:** Sonnet
Build the tile split with overlap, still in Python. Plus a script that
compares two images pixel by pixel (max deviation, share of differing
pixels).
**Test:** compare tiled against untiled. Target: share of differing pixels
under 0.5%, mean deviation under 0.01 of 255.
**Already measured (5 images, structured test subject, 512 px tiles,
8-bit):**

| Overlap | differing pixels | mean deviation |
|---|---|---|
| 0 px | 3.58% | 1.57 |
| 16 px | 0.13% | 0.0016 |
| 64 px | 0.23% | 0.0027 |

### Step 3 — UI, as a new tab in OpenScan3-Client
**Model:** Sonnet
New tab/route "Stacking" in the existing `OpenScan3-Client` Vue project,
next to the unchanged scan part: select images/scan, progress, view and save
result, delete toggle, storage target selection (folder dialog). Built and
shipped as a regular part of the rest of the client. Doesn't compute
anything yet — it only calls the interface from Step 0.
**Test:** with a mocked compute path that returns finished images.

### Step 3a — Live stacking hookup
**Model:** Sonnet
The "Stacking" tab polls/listens to OS3's WebSocket progress messages,
detects finished positions while the scan is still running, triggers
merging. Two-stage deletion as a toggle. `beforeunload` warning during an
active run.
**Test:** a full live scan, verify stacking keeps up with capturing and only
the final stack is left as waiting time.

### Step 4 — Computing in the browser, simple variant
**Model:** Sonnet, Opus if it gets stuck
Pyodide: the same Python code runs directly in the browser. Slow, but
guaranteed to match the reference result.
**Test:** compare against Step 1, must be practically identical.
**Risk:** whether the OpenCV package for Pyodide can do everything needed
must be checked early.

### Step 5 — Computing in the browser, fast variant
**Model:** Opus for the setup, Sonnet for the rest
WebGPU. Warping = texture sampling, Laplacian = 3×3 filter, selection =
per-pixel maximum. Tiling is mandatory here: the usual texture limit is
8192 px, a 45 MP camera delivers 8256 px width. Reading files must be
spread across multiple web workers, otherwise the GPU doesn't help — settle
the HTTPS question (see above) beforehand and file it as its own PR against
the Pi system configuration.
**Test:** compare against Step 4. Small deviations from different rounding
are acceptable, the benchmark is the table from Step 2.

### Step 6 — Helper for large scans, order: Windows + Mac first
**Model:** Sonnet
A Python program that offers the same interface over HTTP, fetches the
images itself from the Pi, and provides a minimal control API
(start/pause/stop) for the Pi-hosted UI. Runs as its own process, not
started by the browser — a double-click icon to launch it. Fixed storage
path as a setting. Linux comes along for free (same Python code), but
priority is Windows/Mac since that's where actual usage happens.
**Test:** a full scan from the Pi, verify abort and resume.

### Step 6a — Automatic helper detection + Android (lowest priority)
**Model:** Sonnet
The Pi-hosted page checks on load whether `localhost:<port>` (helper)
responds, and then uses it automatically instead of browser computation —
no manual switch. Only build this once Step 6 runs on Windows and Mac.
**Android: lowest priority, only if at all.** No Python background process
like on desktop is possible (Android doesn't allow loose background
services without their own app) — an Android helper would be its own app,
not a port, and a fully separate undertaking. Until then (and that's the
default case anyway, see the priority order above), Android only gets the
browser compute path (Step 4/5).

### Step 7 — Server
**Model:** Sonnet
The same helper on a server, plus login. The UI stays unchanged. This is
also where the 16-bit question becomes relevant again, see above.

## Notes

- The web UI and firmware are separate repos: `OpenScan3` (Python/FastAPI,
  firmware) and `OpenScan3-Client` (Vue.js SPA, web UI). Our project extends
  `OpenScan3-Client`, leaving `OpenScan3` untouched.
- OS3 doesn't start focus stacking automatically, only via
  `POST /projects/{name}/scans/{i}/focus-stacking/start`. So it's fine to
  simply never call it.
- OS3 allows requests from any website (`allow_origins=["*"]`), so a browser
  UI can read directly from the Pi.
- Deleting original images: `DELETE /projects/{name}/{scan_index}/photos`
  with a list of file names — already exists, no firmware change needed.
- No endpoint to write finished images back to the Pi (only cloud upload via
  `POST /projects/{name}/upload`).
- OS3 stores the alignment matrices as JSON under
  `scanXX/stacked/calibration_scanXX.json`.
- Bug in the original code: `FocusStacker.calibrate()` doesn't set
  `self.transforms`. Calling `stack()` right after throws an exception. Pass
  the matrices explicitly.
- Storage target selection: File System Access API on the browser path
  (Chromium browsers only), fixed path on the helper path. Firefox/Safari
  have no folder access — falls back to individual downloads there.
