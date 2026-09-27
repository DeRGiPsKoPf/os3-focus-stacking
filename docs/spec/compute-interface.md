# Compute interface specification

Interface version: **1** · Status: Step 0 deliverable (2026-09-27) · Types:
[compute-interface.ts](compute-interface.ts) · Helper wire protocol:
[helper-http-api.md](helper-http-api.md)

This document defines the contract every compute path (mock, Pyodide, WebGPU,
helper) must satisfy, plus the rules around it that the "Stacking" tab
(the *orchestrator*) relies on: batch discovery, calibration policy, storage
targets, verification before deletion, and helper detection. The key words
MUST/SHOULD/MAY are used in their usual sense.

Checked against upstream: OpenScan3 v0.13.0 (`bd99449`, identical watched
files on `develop` at `28a3893`) and OpenScan3-Client `main` at `56dfe2b`.
See [../../tools/upstream-baseline.json](../../tools/upstream-baseline.json).

## 1. Terms

| Term | Meaning |
|---|---|
| scan | One OS3 scan: `projects/<project>/scanXX/` on the Pi |
| position | One turntable/rotor position of a scan. Its number `NNN` in file names is OS3's *original path index*, not the capture order (OS3 reorders the path) |
| focus step | Index `fsNN` (0-based) within a position's focus sweep |
| stack size | `scan.settings.focus_stacks`; number of focus steps per position |
| batch | All photos of one position (exactly *stack size* images) |
| reference step | `floor(stackSize / 2)`; its image defines the output frame |
| backend | An implementation of `ComputeBackend` |
| orchestrator | The Stacking tab's control logic: finds batches, calls the backend, writes/verifies, deletes |
| storage target | Where results go: a chosen folder, downloads, or the helper's output root |

## 2. Architecture

```
Stacking tab (Vue)
  └─ orchestrator ── OS3 REST + WebSocket (batch discovery, photo URLs, delete)
        └─ ComputeBackend  (exactly one active)
             ├─ mock     — Step 3, returns the reference image unchanged
             ├─ pyodide  — Step 4, OS3's Python code in a Web Worker
             ├─ webgpu   — Step 5, merge on the GPU; calibration delegated to the CPU (Pyodide) worker
             └─ helper   — Step 6, same operations over HTTP on 127.0.0.1
```

- Alignment (calibration) always runs on the CPU and produces one 2×3
  matrix per focus step. Merging is where backends differ.
- Every backend implements both operations; a backend MAY delegate one of them
  internally (the WebGPU backend delegates `calibrate` to the Pyodide worker).
- Backends run off the main thread (Web Worker or separate process).
- Runtime selection (Step 6a): a paired, compatible helper wins; otherwise
  WebGPU if available; otherwise Pyodide. `mock` only in development/tests.

## 3. Operations

The roadmap's `calibrate(batches) → matrices` and
`stackBatch(images, matrices, tilePlan, numberFormat) → resultImage` map to:

```ts
init(): Promise<BackendCapabilities>
calibrate(request: CalibrateRequest, control?): Promise<CalibrateResult>
stackBatch(job: StackJob, control?): Promise<StackResult>
prefetch?(images): void          // optional hint, may be a no-op
dispose(): Promise<void>
```

`StackJob` bundles images (`batch`), matrices (`transforms`), `tilePlan`,
`numberFormat` and the output specification (file name, encoding, storage
target) into one object, so the same shape travels unchanged as a JSON body
to the helper. `control` carries an `AbortSignal` and a progress callback.

### 3.1 Common input rules

- A batch MUST satisfy `images.length === stackSize` and
  `images[i].focusStep === i`. A backend MUST reject anything else with
  `invalid-job`.
- All images of a job MUST decode to the same width and height, else
  `size-mismatch`.
- Encoding: JPEG only in interface version 1 (OS3's stacking also only handles
  `.jpg`).
- Decoding MUST apply the EXIF Orientation tag, as `cv2.imread(IMREAD_COLOR)`
  does (OS3 writes the tag from the camera's orientation setting). All
  coordinates (matrices, tiles, output) refer to the oriented image. Browser
  decoders MUST NOT apply colour management (`colorSpaceConversion: 'none'`).
  *Resolved in Step 0:* neither `opencv-python` nor `pyturbojpeg` is a
  declared dependency of `openscan-firmware` (checked against `pyproject.toml`
  at the v0.13.0/`develop` baseline) — `cv2` comes from a system package on
  the Pi image, and TurboJPEG's `TURBO_AVAILABLE` is `False` unless someone
  installed it manually. `load_image` therefore falls through to
  `cv2.imread(path, cv2.IMREAD_COLOR)` in the default install, which does
  apply EXIF orientation. Re-check with `python tools/check_upstream.py` if
  this ever changes.
- `numberFormat.bitsPerChannel` MUST be honoured or rejected with
  `unsupported`; interface-1 backends accept only 8. Internal math is floating
  point (0.0–1.0) independent of bit depth.
- Image sources: `url` (backend fetches) or `blob` (already fetched by the
  orchestrator). The helper accepts `url` only.

### 3.2 `calibrate` — semantics (OS3 v0.13.0, `FocusStacker.calibrate` / `calibrate_multi`)

For each batch:

1. Reference = image at `referenceStep`; downscale by 0.25
   (`cv2.resize`, INTER_LINEAR, size `int(w*0.25) × int(h*0.25)`), convert to
   grey (8-bit, then /255 to float32), 5×5 box filter.
2. For every other step: same preprocessing, then
   `cv2.findTransformECC(ref, img, I, MOTION_AFFINE,
   (EPS|COUNT, 20, 1e-6), inputMask=None, gaussFiltSize=3)`; divide the
   translation column by 0.25 to get full-resolution units.
3. The reference step gets the identity.

Across batches, the per-step matrices are averaged element-wise (float32),
exactly like `calibrate_multi`. **ECC failures:** OS3 swallows `cv2.error` and
keeps whatever matrix is left, which is then included in the average.
*Resolved in Step 0:* `compute_alignment_transform` only ever reassigns its
local `warp` variable on the *successful* return of `findTransformECC`
(`_, warp = cv2.findTransformECC(...)`); a raised `cv2.error` happens before
that assignment, so `warp` is always still the identity set at the top of the
function — never a partially-updated matrix. Backends MUST reproduce this
(failure ⇒ identity for that step) and additionally report each failure in
`failures`.

The matrix convention is fixed by [compute-interface.ts](compute-interface.ts)
(`AffineMatrix`): OpenCV 2×3 layout, maps output → source coordinates, applied
with `WARP_INVERSE_MAP`. Earlier roadmap wording "3×2 matrix" means the same six
numbers (WGSL `mat3x2`).

### 3.3 `stackBatch` — semantics (OS3 v0.13.0, `FocusStacker.stack`)

1. If `stackSize == 1`: the single image is re-encoded unchanged.
2. `result` := reference image; `best` := focus map of the reference image.
3. For each step `i` in ascending order, skipping the reference:
   - `aligned` := `warpAffine(img_i, transforms[i], (w, h), INTER_LINEAR |
     WARP_INVERSE_MAP, BORDER_CONSTANT, 0)`;
   - `focus` := focus map of `aligned`;
   - where `focus > best` (strict): take the pixel from `aligned` and update
     `best`. Ties keep the earlier value, so the processing order is part of
     the result.
4. Encode as JPEG with `output.encoding.quality` (OS3: 90), no metadata.

Focus map: downscale by 0.25 (INTER_LINEAR) → 8-bit grey → float32 /255 →
`Laplacian(ksize=3)` → square → resize back to full size (INTER_LINEAR). The
exact rounding points (8-bit after resize and after grey conversion) matter for
bit-exactness; the OS3 source is normative, GPU backends approximate it within
the tolerances in §8.

### 3.4 Tiling (`TilePlan`)

- `untiled`: the whole image is processed at once (reference CLI, small images).
- `grid`: the output image is split into *cores* of `tileWidth × tileHeight`
  starting at (0, 0); the last row/column is clipped. Each tile is processed as
  its core expanded by `overlap` on all sides (clipped to the image); only the
  core is written. Every output pixel therefore comes from exactly one tile.
- `tileWidth`, `tileHeight`, `overlap` MUST be multiples of 4 (the focus map
  works at 1/4 scale, so tile edges stay on the global 1/4 grid) and
  `overlap ≥ 16`. Exact tile/no-tile equivalence also needs image width and
  height divisible by 4 (true for the common sensors: 4656×3496, 9152×6944).
- The warp of a tile samples the *source* image at `M · p`; a backend MUST make
  the source region `bbox(M · processed rect)` plus 1 px available. That region
  can exceed the tile, and GPU backends size their textures accordingly.
- **The focus-energy map (§3.3's Laplacian² step) MUST be computed once per
  whole source image, never independently from a tile's own cropped pixels.**
  A tile then only *slices* the region of that shared map its processing rect
  covers — it MUST NOT recompute any part of it. Computing a tile's map from
  that tile's own cropped pixels resamples on a grid anchored to the tile's
  own size, which disagrees with the whole-image resampling grid almost
  everywhere in the tile, not only near its edges, defeating `overlap`
  entirely. Confirmed in Step 2 (`python/src/os3stack/stack.py`): on a
  checkerboard synthetic image this bug stayed within tolerance
  (checkerboards have few near-tied sharpness pixels to flip), but on a real
  photo it produced 70-97% differing pixels. Any tiled backend — this CPU
  reference, WebGPU (Step 5), the helper (Step 6) — MUST follow this
  once-per-image ordering, not just meet the pixel-diff tolerance on whatever
  test image happens to be at hand.
- Two ways to satisfy that rule, depending on what a backend can afford to
  hold per source image:
  - **Full resolution** (what this CPU reference does): compute the whole
    map at full size (§3.3's Laplacian² step *including* its resize back up),
    then slice per tile. Exact for any image size and any tile size/overlap —
    slicing an already-computed array can't disagree with itself. Costs one
    full-resolution array per source image alongside its aligned pixels.
  - **Low resolution** (for a memory- or texture-size-constrained backend
    that can't afford a full-resolution map per source, e.g. WebGPU's ~8192 px
    texture limit): compute the map at its native 1/4-scale size only, slice
    the region a tile's processing rect covers, and upsize just that slice.
    This is only *exact* when the whole image's width and height are
    themselves multiples of 4 — otherwise the image's own global downscale
    ratio (`⌊size × 0.25⌋ / size`) isn't exactly 0.25 either, and no per-tile
    slice can reproduce it without its own rounding (confirmed in Step 2: on a
    1037×1555 photo this brought a backend from 70-97% differing pixels to
    47-54%, much better but still nowhere near the target). `tileWidth`,
    `tileHeight`, `overlap` being multiples of 4 (above) is necessary for this
    approach's exactness but not sufficient by itself — 4 = 1/downscale, so
    tile boundaries land on integer low-res pixels only if the image's own
    boundary (its width/height) does too. Common sensors satisfy this
    (4656×3496, 9152×6944); arbitrary input might not. A backend using this
    approach SHOULD pad the image to the next multiple of 4 (edge replication)
    before processing and crop back to the original size afterward — the
    standard technique for block-based image transforms — rather than merely
    warning and accepting a worse match.
- A backend announces its `preferredTilePlan`; the orchestrator uses it unless
  overridden.

### 3.5 Results and errors

`StackResult` returns size, byte length, SHA-256 where available (`null` if the
backend can't compute it, e.g. no `crypto.subtle` outside a secure context),
per-phase timings, and the `Delivery` state (§5). Errors reject with
`ComputeErrorInfo` fields (`code`, `message`, `retryable`). `aborted` is used
when the `AbortSignal` fires. A backend MUST leave no partial file under the
final name: write to a temporary name and rename, or delete on failure.

## 4. Batch discovery and calibration policy (orchestrator)

### 4.1 Batches

- Photo names: `scan{XX:02}_{NNN:03}_fs{SS:02}.jpg` (OS3 `projects.py`). The
  stack size comes from `scan.settings.focus_stacks`, never from counting files.
- A batch is *complete* when all `stackSize` photos of a position are listed in
  `scan.photos`. OS3 awaits each photo's save before it reports the position's
  progress (`scan_task.py`), so a progress event over `/ws/tasks` means that
  position's files are on disk.
- Image URLs come from the OS3 photo endpoint
  `GET /projects/{project}/{scan}/photo?filename=…&file_only=true` under the
  API base URL the client already uses. In live mode the orchestrator SHOULD
  fetch each photo as soon as it's listed and pass `blob` sources, spreading
  the download (≈11 MB per photo) over the capture time.

### 4.2 Calibration policy

OS3 calibrates from 3 batches evenly spaced over the *whole* scan. That can't
work live, so the policy is explicit and recorded in the calibration file:

| Mode | When | Batches | Effect |
|---|---|---|---|
| `spread` (N = 3) | completed scans | `linspace(0, count-1, N)` over batches sorted by position | Equivalent to OS3 (OS3 uses file-system order, we use position order) |
| `leading` (N = 3), **live default** | live | The first N positions to complete, in capture order | Merging starts after position N; the backlog of N positions catches up within a few seconds |
| `calibration-scan` (N = 3), **live toggle** | live | A separate short scan (N points) before the main scan, same camera/focus settings | Merging starts at the main scan's first position; the calibration views are spread over the object like OS3's |

About `calibration-scan`: the calibration positions don't have to be positions
of the main scan. The matrices describe how the lens image shifts and scales
across the focus sweep, which is the same at every turntable position. The
spread is only there so that ECC sees different views (more robust). How the
pre-scan gets its settings and is started (the main scan can wait on it via
OS3's `depends_on`) is decided in Step 3a.

Before using a calibration, the orchestrator MUST check that `stackSize`,
`imageWidth` and `imageHeight` match the scan, and MUST warn when `failures`
is non-empty.

## 5. Storage targets and verification

### 5.1 Layout

Inside the storage target root:

```
<project>/scanXX/calibration_scanXX.json      # CalibrationRecord (superset of OS3's file)
<project>/scanXX/stacked_scanXX_NNN.jpg       # one per position, OS3's naming
<project>/scanXX/stacking_run_scanXX.json     # run state for resume (Step 3a)
```

Project names are sanitised for Windows/macOS file systems (characters
`<>:"/\|?*` and control characters → `_`). The download fallback can't create
folders and uses flat names: `<project>_stacked_scanXX_NNN.jpg`,
`<project>_calibration_scanXX.json`.

### 5.2 Kinds

| Kind | Used by | How it's chosen | Verifiable |
|---|---|---|---|
| `directory-handle` | browser backends | One folder dialog per scan start (`showDirectoryPicker`); the handle can be passed to a Web Worker and kept in IndexedDB for resume | yes |
| `download` | browser fallback (Firefox, Safari, or no secure context) | automatic | **no** |
| `helper-directory` | helper | Output root configured in the helper; the Stacking tab shows it and may change it via `PUT /v1/config` (paired origins only) | yes |
| `memory` | mock, tests | — | n/a |

Jobs only carry `relativePath`. No absolute path ever travels from the page to
a backend.

**Secure context:** `showDirectoryPicker`, `crypto.subtle` and WebGPU exist only
in secure contexts (HTTPS, or `localhost`). If the Pi serves the UI over plain
HTTP, only the `download` target and the Pyodide backend are available in the
browser. See the roadmap's HTTPS section and open decisions.

### 5.3 Two-stage deletion (toggle, default off)

1. **Stage 1: verified.** The result was written under its final name, then
   re-opened *through the storage target* (fresh read, not a cached buffer)
   and compared with the encoded buffer: same length and identical bytes. Only
   then `delivery.kind === 'verified'`.
2. **Stage 2: delete.** `DELETE /projects/{project}/{scan}/photos` with exactly
   that batch's `photoPath`s, only if **all** of these hold:
   - the batch's result is `verified`;
   - the calibration record for the scan is written and verified the same way;
   - no OS3-side focus stacking task for this scan is pending, running or
     paused (`scan.stacking_task_status`). The client's "auto-start focus
     stacking" option schedules one via `depends_on`, and deleting originals
     under it would break it. The UI MUST warn about this case.
- The delete toggle is unavailable for `download` targets (never verifiable).
- Photos of a calibration pre-scan MAY be deleted once the calibration record
  is verified.
- Never delete because a task or job "succeeded" without stage 1.

### 5.4 Resume

On (re)start the orchestrator reads `stacking_run_scanXX.json` and skips
positions whose output file exists and matches the recorded length and hash.
This mirrors OS3's own resume logic.

## 6. Helper detection (Step 6a)

- The page probes `GET http://127.0.0.1:8742/v1/health` on load of the Stacking
  tab and on user request (timeout 1 s). No address typing; an advanced setting
  MAY override the URL.
- Outcomes (`HelperProbeResult`): `absent`, `incompatible` (interface version
  differs), `unpaired` (helper found, this page's origin not yet approved →
  start pairing), `paired` (use it).
- Pairing: the helper only serves origins the user approved once in the
  helper's own window. It fetches images only from the host of the paired
  origin. Details and CORS/Local Network Access handling:
  [helper-http-api.md](helper-http-api.md).
- Browser caveat, to verify in Step 6a: Chrome's Local Network Access rules
  gate requests from a LAN-served page to `127.0.0.1` behind a permission
  prompt and may block them from non-HTTPS pages.

## 7. Client integration (Step 3+)

All client code lives in the OpenScan3-Client clone under `app/src/stacking/`
(types, backends, orchestrator, storage), `app/src/pages/StackingPage.vue` and
`app/src/components/stacking/`. Python code for Pyodide is shipped as a static
asset (Step 4 decides the sync mechanism from `python/`). Touch points in
existing client code, kept minimal for the upstream PR:
`app/src/router/routes.ts` (one route), `app/src/layouts/MainLayout.vue` (one
navigation entry), `app/src/i18n/en-US/index.ts` (strings). The client already
talks to OS3 through generated SDKs (`src/generated/api`) and
`services/apiClient.ts`; the orchestrator uses those.

## 8. Conformance testing

- Merge comparisons feed *identical matrices* (from the reference CLI's
  calibration) into both sides, so merge differences and calibration
  differences are measured separately.
- Merge tolerance: Step 2's targets (differing pixels < 0.5 %, mean absolute
  deviation < 0.01 of 255) against the reference, or against Step 4 for Step 5.
- Calibration comparison: element-wise matrix deltas; tolerances are set in
  Step 4.
- JPEG decoder differences (libjpeg-turbo in OpenCV vs. browser decoders vs.
  Pyodide's OpenCV build) count against the same tolerance budget. The reference
  decodes with OpenCV.

## 9. Versioning

`COMPUTE_INTERFACE_VERSION` increments on any breaking change to the types or
semantics above. The helper reports its version in `/v1/health`; the page
refuses a helper with a different interface version (`incompatible`).
