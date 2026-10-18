# Roadmap: Focus Stacking outside the Pi

Status: 2026-10-15. This file is the starting point for every new session —
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
| **Helper** on the PC (proxies the Pi's own UI at `localhost:8742`) | **Helper** | large scans, runs that must outlive the tab, any browser |

The second row is a **later expansion** (Steps 6/6a). The helper never
reimplements OS3's UI: it serves the Pi's own OpenScan3-Client unchanged
through a local reverse proxy, so the page and the helper share one origin.
The Stacking tab detects the helper with a same-origin request and turns on
helper features per capability — no manual switching, no typing addresses.
Opened from the Pi directly, the tab computes in the browser as before.
Until the helper runs on all target platforms, "browser computes" remains
the only path.

**Priority order of compute paths:** (1) Browser, (2) Helper on Windows,
macOS and Linux — all three equal targets, see Step 6.

All compute paths receive the same job and return the same result (see the
interface in Step 0).

## Fixed decisions

- **Algorithm:** the one from OpenScan3
  (`openscan_firmware/utils/photos/stacking.py`, v0.13.0). Alignment once per
  scan via ECC affine transform, then per position: warp → Laplacian² as
  sharpness measure → pick the sharpest image per pixel.
- **Alignment and merging stay separate.** Alignment always runs on the CPU
  and produces one 2×3 affine matrix per focus step. Only the merging step
  moves to GPU/browser.
- **Calibration batches** (added in Step 0): OS3 calibrates from 3 batches
  spread evenly over the whole scan, which is impossible while the scan is
  still running. Completed scans keep OS3's spread; live scans use the first 3
  completed positions by default, or — as a toggle — a separate short
  calibration pre-scan (3 positions, same camera and focus settings) before
  the main scan. The matrices describe the lens's focus breathing, which is the
  same at every turntable position, so the pre-scan positions don't need to be
  positions of the main scan. Details: `docs/spec/compute-interface.md` §4.2.
  The pre-scan toggle is **deferred** (2026-10-19, see Open decisions): live
  scans calibrate from the first 3 positions until a measurement shows that
  isn't good enough.
- **Tiling from the start.** Any image size up to the native camera
  resolution. Tile size and overlap are multiples of 4 px (= 1 / the
  downscale factor of the sharpness map). Overlap at least 16 px.
- **Transforms are always passed as a 2×3 affine matrix** in OpenCV layout
  (`[[a, b, c], [d, e, f]]`, maps output → source pixels), never
  backend-specific. This file said "3×2" before Step 0; it's the same six
  numbers (WGSL calls it `mat3x2`).
- **8 bits per color channel to start, and permanently for the
  browser/helper base version.** 16-bit is **not** a near-term expansion
  step anymore — it's clearly assigned to a future helper expansion (see the
  dedicated section below). 8-bit keeps the live
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
  connection drop/crash mid-save. Also never delete while OS3's own focus
  stacking task for the same scan is pending or running: since client 0.8.0 the
  Scan page can auto-start stacking on the Pi after the scan (`depends_on`),
  and that task needs the originals. The Stacking tab warns about this case.
- **Additive extension of `OpenScan3-Client`**, not a fork/iframe. A new
  tab/route next to the existing scan UI, built and shipped as part of the
  same Vue project. Goal: mergeable upstream as a PR without touching
  existing code beyond one route, one navigation entry and i18n strings.
- **Helper scope: small companion, not a control app.** The helper never
  reimplements scanner control, live view or scan setup — those stay in
  OpenScan3-Client, served by the Pi. It adds only what a browser can't do
  well, hosts the Pi's own UI through a local reverse proxy, never moves
  hardware or starts scans, and is optional by design. Details and
  rationale: the dedicated section below.
- **Development against current upstream, no long-lived fork.** The client is
  developed in a plain clone of upstream `OpenScan3-Client`, its own
  repository checked out next to this one (`../os3-stacking-client`; until
  2026-10-14 it lived inside this repo as `client/`), on a feature branch that is rebased onto
  upstream regularly. A GitHub fork is only created when pushing is needed
  (backup, PR). `tools/check_upstream.py` reports upstream changes to every
  firmware and client file the spec depends on; run it at the start of each
  step.
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
  folder, not the chosen one). Downloads can't be re-read, so the two-stage
  deletion is unavailable in that mode. The API also needs a secure context
  (see the HTTPS section). Helper compute path: a fixed path as a text
  field in settings, since the helper is a standalone program with
  unrestricted file access anyway (jobs only carry relative file names; the
  root is set in the helper, the tab can change it through the helper's
  same-origin API).

### On the helper's scope (small companion, not a control app)

The helper could in principle take over OS3's whole control interface —
scanner control, live view, scan setup — as a desktop app that replaces the
scanner's web interface. It deliberately doesn't:

- **No second OS3 client to maintain.** The OS3 API is still moving fast
  (the firmware mounts `/v0.8`, `/v0.9`, `/latest` and `/next` side by side;
  the client carries generated SDKs for all four). A second control UI would
  have to follow every firmware change and would soon cost more than the
  stacking itself.
- **Contributes to upstream instead of competing with it.** The goal is a PR
  that adds one route and one nav entry; a parallel control app can't be
  merged into anything.
- **Installation stays optional.** Anyone can still open the Pi's address
  from any device on the network and stack in the browser.
- **One UI, one master.** No second program that also drives the motors and
  the camera, so no locking or state sync between two UIs.
- **Small attack surface.** A local service that can move hardware and is
  reachable from web pages is a much more attractive target than one that
  computes images.

**How it works.** The helper listens on `127.0.0.1:8742` only and
reverse-proxies the Pi's UI and API there (`/` and `/api/…`, including
WebSockets and the MJPEG camera preview, to exactly one configured Pi). Its
own API lives under `/helper/v1/…` on the same origin. That avoids CORS,
origin pairing and Chrome's still-changing Local Network Access rules for
cross-origin requests to `127.0.0.1`; `localhost` is always a secure
context; and the UI always matches the Pi's firmware because it comes from
the Pi itself. The Stacking tab probes `GET /helper/v1/health` and shows
each helper feature only if the helper reports the matching capability.
Only the Stacking tab knows about the helper — every other OS3 page behaves
exactly as upstream ships it. The helper never moves hardware or starts
scans; its only write to the Pi is the existing two-stage deletion. If it
goes away mid-run, the scan on the Pi carries on unaffected; after a
restart the helper resumes from the run file (spec §5.4).

**What changes when the helper is detected:**

| Area | Browser only | With helper |
|---|---|---|
| Compute | WebGPU/Pyodide inside the tab | Native multi-core OpenCV, same code as the reference |
| Run lifetime | Tab must stay open (`beforeunload` warning) | Run lives in the helper; the tab can close and reconnect later; resumes after a crash |
| Storage | Folder dialog (Chromium only), else downloads | Fixed output folder, in any browser |
| Two-stage deletion | Only with the folder dialog | Always (helper verifies by re-reading) |
| Secure context | Needs HTTPS on the Pi | Always (`localhost`) |
| Large scans | Limited by tab memory and GPU texture size | Limited by disk and RAM |
| Later, each behind its own flag (not scheduled) | — | 16-bit/TIFF/RAW (see the 16-bit section), "open output folder", background masks, photogrammetry project export (Metashape/RealityCapture/Meshroom folder layout) |

Basic stacking never requires a helper-only feature.

**Known costs**, handled in Step 6:

- Outside developer mode, the client builds its API URL from
  `window.location.hostname` without the port (`app/src/stores/apiConfig.ts`),
  so a page at `localhost:8742` would call port 80. Fix: a small, separate
  upstream PR that keeps the page's port. Until then: developer mode with
  host `localhost`, port `8742`; the helper also proxies the developer-mode
  paths (`/v0.9/…`, `/latest/…`, `/next/…`) to the Pi's `/api/…`.
- Until the Stacking-tab PR is merged, the Pi's UI has no Stacking tab. For
  that window only, the helper may serve a bundled client build while still
  proxying the API (transitional — it brings back the version-mismatch risk).
- The proxy must stream the MJPEG preview and the WebSockets without
  buffering, and pin the Pi's (usually self-signed) HTTPS certificate on
  first connect.

### On the 16-bit question (clearly deferred: helper expansion, not near-term)

- Belongs thematically to the helper (Step 6), not the browser core.
- The interface must still always carry the number format as a parameter,
  never assume it — costs nothing now, prevents silent 8-bit assumptions in
  the code, and keeps the path open for the later expansion.
- Internal computation runs in floating point (0.0–1.0) either way, that
  doesn't change with bit depth — only reading/writing gets swapped out for
  the expansion.
- At 16-bit, the browser can't read TIFF/RAW itself (needs a WASM decoder,
  e.g. libtiff/libraw), the data volume doubles, the helper becomes
  practically mandatory for large scans — which fits, since in the helper
  memory and compute power aren't the browser's problem anymore anyway.

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
- **Timing:** originally assumed to affect only Step 5 (WebGPU with parallel
  web workers). **Correction from Step 0:** several APIs are available only in
  secure contexts (HTTPS, or `localhost`): the File System Access API
  (`showDirectoryPicker`, the storage-target folder dialog, Step 3), WebGPU
  (Step 5) and `crypto.subtle`. If the Pi serves the UI over plain HTTP, the
  Pi-served Stacking tab can offer only the download fallback, and therefore
  no two-stage deletion, from Step 3 on. Development isn't blocked: the client
  dev server runs on `localhost`, which is a secure context. How to proceed is
  listed under open decisions.
  Original recommendation, still sensible for the PR itself: file it only once
  the rest already works and has proven itself — a small, well-justified
  addition to a working feature is easier to get accepted than an upfront
  requirement.
- **Bar to clear:** must be integrated as solidly as the rest of the
  foundation, not bolted on as a quick hack.
- **Current state (checked 2026-10-15):** stock OS3 images serve **HTTP
  only**. The maintainer's scanner (`openscan.local`) has port 80 (nginx) and
  8000 (uvicorn) open, 443 closed. The nginx site
  `/etc/nginx/sites-available/openscan3.conf` belongs to the APT package
  `openscan3-system-config` (OpenScan3 `docs/DEBIAN_PACKAGING.md`, pi-gen
  `DOCUMENTATION.md`), so a hand-made HTTPS setup on the Pi is likely
  overwritten by the next package update — probably why the scanner that used
  HTTPS on 2026-09-27 doesn't anymore (not verified). The 2026-09-27
  "resolved" note under open decisions is therefore withdrawn: HTTPS is
  needed after all, as its own upstream contribution (Step 4a).

**Plan (Step 4a): HTTPS as a package-owned default, aimed at the simplest
experience for a normal user.** No certificate files to copy, no settings,
no command line:

1. **Certificate per device, created on the Pi.** A small oneshot systemd unit
   (in `openscan3-system-config`) runs before nginx: if
   `/etc/openscan3/tls/` has no certificate, or its names no longer match the
   current hostname, it creates a self-signed one with `openssl` (key stays
   on the device, never shipped in the package; subject alternative names
   `<hostname>.local`, `<hostname>`, the current IPs; long validity). No
   shared private key across devices.
2. **nginx listens on 443 as well**, with the same site (SPA, `/api`
   proxying incl. WebSocket upgrade headers and unbuffered MJPEG). **Port 80
   stays as it is** — no forced redirect, so nothing that talks to the Pi
   over HTTP today breaks (scripts, the API at `:8000`, older clients).
3. **The client needs no change for this:** `apiConfig.ts` already takes the
   scheme from `window.location.protocol`, so a page opened over `https://`
   calls the API and WebSockets over `https://`/`wss://` on the same host.
4. **User-facing part, inside the Stacking tab (our PR, not a separate
   one):** if `window.isSecureContext` is false, the tab explains in one
   sentence what's missing (folder saving, deleting originals, fast GPU
   stacking) and offers a button "Open the secure version" →
   `https://<same host>/stacking`. The browser shows its certificate warning
   **once** per PC/browser ("Advanced → Continue"); the tab says beforehand
   that this is expected for a home-network device. Without HTTPS on the Pi
   the button is hidden and the tab falls back to downloads as today.

To verify in Step 4a before proposing it: after clicking through the
certificate warning, Chrome/Edge must report `isSecureContext === true` and
allow `showDirectoryPicker` and WebGPU (expected; service workers are known
not to work on such pages, but the client doesn't use one). Firefox/Safari
keep the download fallback regardless.

Rejected for normal users: a local CA the user installs on every PC (too many
steps), public certificates (impossible for `.local` names), Chrome's
"treat insecure origin as secure" flag (a developer workaround). The helper
(Step 6) remains the route that needs no certificate at all, since
`localhost` is always secure.

**How the PR works** (first upstream PR, so step by step): the source of
`openscan3-system-config` is not in a public GitHub repo we could find
(OpenScan3 and OpenScan3-pi-gen only install it from the APT repository).
So: (a) ask the maintainers in a GitHub Discussion/issue on `OpenScan3`
where the package lives and whether they'd accept HTTPS-by-default as
described — short, with the reason (secure-context APIs) and the "port 80
unchanged" promise; (b) fork that repository, branch, implement 1–2, build
the `.deb`, install it on our own scanner and test (fresh install, upgrade,
hostname change, HTTP still working); (c) push the branch to the fork and
open the PR on GitHub with what changed, why, and how it was tested; (d)
answer review comments by pushing more commits to the same branch. If they'd
rather own it themselves, the same description becomes an issue instead.
Timing as recommended above: after the Stacking tab works with real compute
(Step 4), before WebGPU (Step 5) needs it.

## Open decisions

- Input format for a future 16-bit expansion (helper): 16-bit TIFF or
  RAW/DNG directly (smaller, but needs demosaicing)? Only relevant once
  Step 6 comes up.
- Upstream PR for a port-aware API URL in OpenScan3-Client's
  `app/src/stores/apiConfig.ts` (prerequisite for the helper-hosted UI
  without developer mode). Separate from the Stacking-tab PR.
- Pi address in the helper: typed once (pre-filled with OS3's default host)
  vs. mDNS discovery. Decide in Step 6.
- Write results back to the Pi? OS3 has no endpoint for that. Not a
  priority — results stay on the PC/chosen storage target. An additive PR
  against OS3 would be possible, but is its own, separate undertaking.
- ~~HTTPS earlier than Step 5?~~ ~~Resolved 2026-09-27: the maintainer's Pi
  already serves the UI over `https://`.~~ **Reopened and decided
  2026-10-15:** the scanner serves HTTP only (stock images have no HTTPS), so
  HTTPS becomes its own upstream contribution, Step 4a — plan in the HTTPS
  section above. Development is unaffected (dev server on `localhost`).
- Where the source of `openscan3-system-config` (owner of the nginx site)
  lives, and whether the maintainers want HTTPS-by-default. Ask them before
  Step 4a.
- ~~How the calibration pre-scan gets its scan settings and is started.~~
  **Decided 2026-10-19: deferred.** The Stacking-tab PR ships live stacking
  with the `leading` calibration only; the pre-scan is proposed to the
  maintainers later as its own small PR or issue, and only if measurements
  show it's needed. Why:
  - *Own form in the Stacking tab* can't see the main scan's settings: the
    Scan page keeps focus steps/range as local component state
    (`ScanSettingsSection.vue`) until the scan starts. The tab would need its
    own focus fields (entered twice, mismatches only caught afterwards), two
    manual starts, and an extra scan in the project. Works without touching
    upstream code, but clumsy.
  - *Touch point in the Scan page* is the clean UX (one toggle, same settings,
    main scan chained via `depends_on`, which OS3's add-scan call already
    accepts — no firmware change), but it edits upstream's busiest page:
    breaks the one-route-one-nav-entry rule, makes the PR a much bigger ask,
    and causes rebase conflicts while we wait.
  - *Reusing an earlier scan's calibration* (no pre-scan at all) is rejected:
    the matrices depend on the physical setup (camera tilt, distance, focus
    range), which can change between scans.
  - The pre-scan's only gain is robustness: `leading` calibrates from 3
    neighbouring views, which can be low on texture. Whether that matters
    is unmeasured. **Measure first** (Step 4): stack a real 100-position scan
    with `leading` and with `spread` calibration and run `os3stack compare`.
    Below the compare target (< 0.5 % differing pixels, mean < 0.01·255) →
    drop the pre-scan. Above → propose the Scan-page touch point upstream.
- Upstream target branch for the PR (`develop` is where upstream merges
  features, `main` is the default/release branch). Confirm with the
  maintainers before opening the PR.

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

### Step 0 — Skeleton and interface ✅ done 2026-09-27
**Model:** Opus (architecture decision)
Define the folder structure, Git repo (fork of `OpenScan3-Client`), and the
interface every compute path must satisfy: `calibrate(batches) → matrices`
and `stackBatch(images, matrices, tilePlan, numberFormat) → resultImage`.
Also: how the page detects whether a helper is reachable locally (for
Step 6a), and how the storage target (folder handle or helper path) is
passed through the interface.
**Test:** none, pure specification.
**Result:**
- Interface: `docs/spec/compute-interface.md` (normative) and
  `docs/spec/compute-interface.ts` (types, moves into the client in Step 3).
  `stackBatch` takes one `StackJob` object (batch, transforms, tile plan,
  number format, output spec) so the same shape travels to the helper as JSON.
- Storage target: a `StorageTarget` union (folder handle / download / helper
  directory / memory) inside the job's output spec; results report `verified`
  only after a byte-exact re-read, which gates deletion.
- Helper detection: `GET http://127.0.0.1:8742/v1/health`, with one-time
  pairing per page origin in the helper's own window, in
  `docs/spec/helper-http-api.md`. **Superseded 2026-10-14** by the
  same-origin model (helper proxies the Pi's UI, see "On the helper's
  scope"); the spec is rewritten at the start of Step 6.
- Folder structure: see `AGENTS.md`. Instead of a fork, a plain upstream clone
  at `client/` from Step 3 on; fork only when pushing.
- Upstream tracking: `tools/check_upstream.py` + `tools/upstream-baseline.json`.

### Step 1 — Reference in Python ✅ done 2026-09-27
**Model:** Sonnet
A small command-line script using OpenScan3's original code that stacks a
folder (8-bit). Serves as the **benchmark**: everything that later gets
dropped in the browser gets compared against this.
Lives in `python/` (package `os3stack`, layout in `AGENTS.md`) and implements
`docs/spec/compute-interface.md` §3.2–3.3 on OS3's code. The scan folder is
passed as an argument; test scans never go into the repo. Check on real data:
whether OS3 on the Pi decodes with TurboJPEG or OpenCV (matters for EXIF
orientation, spec §3.1), and what a failing ECC leaves in the matrix (§3.2).
**Test:** run it on a real scan, look at the result.
**Status:** `python/` package `os3stack` with CLI `os3stack stack <scan-dir>`
and `os3stack compare <a> <b>` (Step 2's tool, pulled forward); 38 unit tests
on synthetic images pass. Both open questions were answered from OS3's
source: `cv2.imread` is the default decode path (EXIF orientation applied),
and a failed ECC always leaves the identity. **Real-scan test passed**
2026-09-27 on a 4-level bracket of a real photo (souvenir model, 1037x1555,
not an OS3 scan but genuine camera JPEGs — no OS3 device was available for
this session): all four transforms converged (no ECC failures), scale
changed smoothly and monotonically across steps (~1.007 → 1.0 (reference) →
0.999, plausible focus breathing), and the merged result is sharp in regions
that are blurred in every single input (near towers, receding right-hand
structure, and the base lettering each sharp only in one or two of the four
inputs, all sharp together in the output). `compare` correctly reports two
different focus levels of that same series as ~96% differing pixels (FAIL,
as expected — they really are different images). Still to confirm once a
real OS3 scan is available: file naming/position handling, calibrate() on
the actual 3-spread-batches policy across positions (this test only had one
position), and a stack size other than 4.

### Step 2 — Tiling logic plus comparison tool ✅ done 2026-09-27
**Model:** Sonnet
Build the tile split with overlap, still in Python. Plus a script that
compares two images pixel by pixel (max deviation, share of differing
pixels).
Tiles follow the definition in `docs/spec/compute-interface.md` §3.4 (core
plus overlap on every side, only the core is written).
**Test:** compare tiled against untiled. Target: share of differing pixels
under 0.5%, mean deviation under 0.01 of 255.

**Status:** comparison tool (`os3stack compare`) was already done in Step 1
(needed there too, against OS3's own output). Tiling: `os3stack.tiling`
(tile/processing-rect geometry) plus `stack_batch(..., tile_plan=...)`, CLI
flags `--tile-width/--tile-height/--tile-overlap`. 54 unit tests pass,
including tiled-vs-untiled equivalence on synthetic images at both
multiple-of-4 and deliberately awkward sizes.

**Two bugs, both caught only by testing on a real photo:**

1. The first implementation recomputed each tile's downscaled focus-sharpness
   map from that tile's own cropped pixels. That resamples on a grid anchored
   to the tile's own size, disagreeing with the whole-image resampling grid
   almost everywhere in the tile, not just near its edges — on the
   checkerboard synthetic test image this stayed within tolerance
   (checkerboards have almost no near-tied sharpness pixels to flip), but on
   the real photo from Step 1 it produced 70-97% differing pixels.
2. The fix (compute each source's low-res focus energy *once* for the whole
   image, then slice+upsize the relevant region per tile) still assumed the
   image's width and height divide evenly by 4 — otherwise the *global*
   downscale ratio `int(size*0.25)/size` isn't exactly 0.25 either, and a
   per-tile slice can't reproduce it without its own rounding. On the real
   photo (1037x1555, not divisible by 4) this brought the mismatch down from
   70-97% to "only" 48-54% — much better, but nowhere near the target, and a
   real reminder that "closer" isn't "fixed".

**The actual fix:** don't slice a *low-res* array and upsize per tile at all
— compute each source's focus map at *full* resolution once (the same array
the untiled path already produces), and have every tile just slice that
finished array. Slicing an already-computed array can't disagree with
itself, so this is exact for *any* image size and *any* tile size/overlap,
not just multiples of 4 — the multiple-of-4 requirement turned out to be an
artifact of trying to stay at low resolution, not a fundamental limit. This
CPU reference implementation can afford it because it already holds full-size
aligned pixels for every source in memory at once; a real memory- or
texture-limited backend (Step 5's WebGPU) still needs the low-res-slice
approach and its multiple-of-4 precondition (or padding to the next multiple
of 4 and cropping back, the standard technique for block-based transforms).
Full reasoning: `python/src/os3stack/stack.py`'s module docstring;
`core.compute_focus_energy_lowres`'s docstring covers the low-res approach
kept for that future use.

**Measured (real photo, 4-level bracket from Step 1, 512 px tiles, `os3stack
compare`'s default threshold of 1/255):**

| Approach | Image size | Overlap | differing pixels | mean deviation |
|---|---|---|---|---|
| per-tile low-res recompute (bug 1) | 1037x1555 | 16 px | 73.0% | 2.22 |
| per-tile low-res recompute (bug 1) | 1037x1555 | 64 px | 70.8% | 2.13 |
| shared low-res, sliced per tile (bug 2) | 1037x1555 | 16 px | 53.7% | 1.56 |
| shared low-res, sliced per tile (bug 2) | 1037x1555 | 64 px | 47.6% | 1.37 |
| shared low-res, sliced per tile (bug 2) | 1036x1552 (cropped to ÷4) | 16/64 px | **0.000%** | **0.0000** |
| **full-resolution, sliced per tile (fix)** | **1037x1555** | **16/64 px** | **0.000%** | **0.0000** |

Common camera sensor resolutions divide evenly by 4 anyway (e.g. 4656x3496),
so bug 2 would rarely have shown up on an actual OS3 scan — but the fix means
this no longer matters at all, for this implementation. The 5-image/0-16-64px
table from earlier planning is superseded by all of the above — it used an
unknown methodology (no fixed differing-pixel threshold was specified) and
most likely hit bug 1.

### Step 3 — UI, as a new tab in OpenScan3-Client ✅ done 2026-09-28 (scan selection moved to 3a)
**Model:** Sonnet
New tab/route "Stacking" in the existing `OpenScan3-Client` Vue project,
next to the unchanged scan part: select images/scan, progress, view and save
result, delete toggle, storage target selection (folder dialog). Built and
shipped as a regular part of the rest of the client. Doesn't compute
anything yet — it only calls the interface from Step 0.
Starts by cloning upstream `OpenScan3-Client` into `client/` (feature branch)
and moving `docs/spec/compute-interface.ts` to
`app/src/stacking/compute/types.ts`, where it gets type-checked for the
first time. Develop with the client's dev server on `localhost` (a secure
context, so the folder dialog works) against the real Pi's API.
**Test:** with a mocked compute path that returns finished images.
**Status:** built in `client/` on branch `feature/stacking-tab` (local only;
no fork yet, so nothing pushed). New code: `app/src/stacking/` (the moved
`compute/types.ts`, a mock `ComputeBackend` in `compute/mock.ts`, fixed mock
batches, a Pinia store driving calibrate → stackBatch per position),
`app/src/pages/StackingPage.vue`, `app/src/components/stacking/`. Touch
points in existing code: one route, one nav entry. Test passed in the browser
against the dev server: full run with progress and per-position status,
result thumbnails with download, abort mid-run. ESLint clean, no `tsc`
errors in our files (upstream has pre-existing `tsc` errors of its own and
doesn't type-check in its build), production build succeeds.
Deviations and open points:
- **Scan selection moved to Step 3a.** The tab runs on fixed mock batches.
  Choosing a real project/scan needs batch discovery from OS3's photo list,
  which is 3a's hookup — and no Pi was reachable to test against.
- **Folder dialog needs one manual test** in Chrome/Edge: the code path
  exists (`showDirectoryPicker`, writes through the handle), but the native
  OS dialog can't be driven by automation.
- No i18n strings: the client doesn't use vue-i18n in any real page (plain
  English strings throughout), so `app/src/i18n/en-US/index.ts` stays
  untouched — one touch point fewer than planned.
- `FileSystemDirectoryHandle`/`DOMException` are missing from the client's
  hand-maintained ESLint globals list; declared per file with `/* global */`
  instead of editing the shared `eslint.config.mjs`.

### Step 3a — Live stacking hookup
**Model:** Sonnet
The "Stacking" tab polls/listens to OS3's WebSocket progress messages,
detects finished positions while the scan is still running, triggers
merging. Two-stage deletion as a toggle. `beforeunload` warning during an
active run. Calibration toggle: first 3 completed positions (default) vs.
calibration pre-scan (see fixed decisions). Resume from the run file in the
storage target (spec §5.4). Also, moved here from Step 3: choosing a real
project/scan (existing projects store + batch discovery from the scan's
photo list, spec §4.1), replacing the mock batches.
**Test:** a full live scan, verify stacking keeps up with capturing and only
the final stack is left as waiting time.
**Status (2026-10-19):** done except a test of two-stage deletion on the
scanner. The calibration pre-scan is **deferred** out of this step (see Open
decisions): the tab calibrates live from the first 3 positions only.
Two-stage deletion (2026-10-18): per position after its result and the
calibration record are verified and no OS3 stacking task needs the photos;
locked while compute is the mock. Real scan selection, live stacking (100-position test: every
position picked up ≤ 0.3 s after OS3's event, run done 1 s after the scan),
`beforeunload`, run file + resume (spec §5.4), one-click continue after a
closed tab, a per-scan "last run" notice. Added on request: a **local
Source** — a folder of photos downloaded from the scanner, read via the
folder dialog (read-only, remembered for resuming) or a plain folder input
as fallback; nothing on the Pi is touched for it. UI wording: "Source" (where
photos come from) and "Target" (where results go). The delete toggle needs a
confirmation with a red button and stays locked while compute is the mock.

### Step 4 — Computing in the browser, simple variant
**Model:** Sonnet, Opus if it gets stuck
Pyodide: the same Python code runs directly in the browser. Slow, but
guaranteed to match the reference result.
**Test:** compare against Step 1, must be practically identical. Also settle
the deferred calibration pre-scan: `leading` vs. `spread` calibration on a
real 100-position scan (see Open decisions).
**Risk:** whether the OpenCV package for Pyodide can do everything needed
must be checked early.

### Step 4a — HTTPS on the Pi (upstream PR to `openscan3-system-config`)
**Model:** Opus (touches someone else's system packaging)
Per-device self-signed certificate created on the Pi, nginx on 443 next to
the unchanged port 80, and the Stacking tab's "Open the secure version"
button. Full plan, rejected alternatives and the PR walkthrough: "On the
HTTPS question" above.
**Test:** on the maintainer's scanner — fresh install and upgrade of the
package, hostname change regenerates the certificate, HTTP keeps working,
Chrome/Edge report a secure context after the one-time warning and the folder
dialog works on `https://openscan.local/stacking`.

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

### Step 6 — Helper: proxy, compute, runs (Windows, macOS, Linux)
**Model:** Opus for the proxy/security design, Sonnet for the rest
A Python program (`os3stack.helper`) with a small window/tray icon, scoped as
described in "On the helper's scope". It (1) reverse-proxies the Pi's UI and
API at `http://localhost:8742/` — HTTP, WebSocket and the MJPEG camera
preview — to exactly one configured Pi (TLS certificate pinned on first
use); (2) serves its own API under `/helper/v1/` (compute jobs, runs with
start/pause/resume/cancel, config); (3) writes results below a fixed output
root and verifies each file by re-reading it. Runs as its own process,
started by double-click; "Open OpenScan" opens the browser at the proxied
UI. **Windows, macOS and Linux are equal targets**: built, packaged and
tested on all three.
Starts by rewriting `docs/spec/helper-http-api.md` and
`docs/spec/compute-interface.md` §2/§6 to the same-origin model (routes under
`/helper/v1/`; the pairing/CORS text moves to an appendix "deferred
cross-origin mode"; security: listen on `127.0.0.1` only, accept only
`Host: localhost`/`127.0.0.1`, no CORS headers on the helper API,
state-changing requests need the helper's own `Origin` plus a custom
header, never an open proxy).
**Prerequisite:** the port-aware API URL (see "Known costs" above and open
decisions); until it's merged, developer mode.
**Test:** on each of Windows, macOS and Linux, a full scan from the
helper-hosted UI: scan control, live preview and WebSocket progress work
through the proxy unchanged; stacking runs in the helper; close the tab
mid-run and reconnect; kill the helper mid-run and resume.

### Step 6a — Helper detection and capability unlocking
**Model:** Sonnet
The Stacking tab calls `GET /helper/v1/health` (relative URL, same origin,
1 s timeout) on load and on request. Absent → browser backends;
incompatible interface version → banner + browser backends; present →
helper backend, with each helper feature shown only if its capability flag
is present (table in "On the helper's scope"). Opened from the Pi directly,
the tab shows a small hint linking to `localhost:8742` instead of probing
cross-origin (a plain link — top-level navigation isn't gated like `fetch`).
The cross-origin probe with pairing (Step 0's original design) is deferred;
build it only if the helper turns out to be needed from the Pi-served page.
Build this only once Step 6 runs on Windows, macOS and Linux.

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
- No server version of the helper: server-side processing is already
  covered by OpenScan Cloud (that same upload endpoint).
- Client API URL: outside developer mode, `app/src/stores/apiConfig.ts`
  builds `${scheme}://${hostname}/api/${version}` (no port); on the
  appliance image, nginx maps `/api/` to the firmware. WebSockets live under
  the same prefix (`…/ws/tasks`, `…/ws/device`). Tracked by
  `tools/check_upstream.py`.
- OS3 stores the alignment matrices as JSON under
  `scanXX/stacked/calibration_scanXX.json`.
- Bug in the original code: `FocusStacker.calibrate()` doesn't set
  `self.transforms`. Calling `stack()` right after throws an exception. Pass
  the matrices explicitly.
- Storage target selection: File System Access API on the browser path
  (Chromium browsers only), fixed path on the helper path. Firefox/Safari
  have no folder access — falls back to individual downloads there.
- Photo names on the Pi: `scanXX_NNN_fsSS.jpg`. `NNN` is OS3's original path
  index (not the capture order, the path gets optimised), `SS` starts at 0.
  OS3 saves every photo of a position before it reports that position's
  progress over `/ws/tasks`.
