# Helper HTTP API

Interface version: **1** · Status: specified in Step 0, implemented in Step 6
(operations) and Step 6a (detection/pairing) · Types:
[compute-interface.ts](compute-interface.ts)

The helper is a standalone Python program (double-click to start) that offers
the compute interface over HTTP to the Stacking tab, which the Pi serves. It
fetches photos from the Pi itself and writes results below its own output
root.

## 1. Transport

- Listens on `127.0.0.1:8742` only (never on LAN interfaces by default). Port
  configurable in the helper; the page's default probe URL is
  `http://127.0.0.1:8742`.
- JSON bodies (`application/json; charset=utf-8`), field names as in
  [compute-interface.ts](compute-interface.ts). `Blob` sources don't exist on
  the wire: image sources are always `{ "kind": "url", "url": … }`, and the
  storage target is always `{ "kind": "helper-directory" }`.
- All routes are prefixed with `/v1`. A breaking change means `/v2` plus
  `COMPUTE_INTERFACE_VERSION` 2.

## 2. Origin allowlist and pairing

Any website the user visits can send requests to `127.0.0.1`. The helper
therefore trusts only origins the user approved:

1. Every response to an unapproved `Origin` (including CORS preflights) is
   `403`, except `GET /v1/health` and the `/v1/pair` routes.
2. `POST /v1/pair` from a new origin shows a prompt *in the helper's own
   window* ("Allow http://openscan.local to use this helper?"). The page polls
   `GET /v1/pair` until `approved` or `denied`. Approved origins are stored in
   the helper's config and can be revoked there.
3. The helper fetches image URLs only if their host equals the host of the
   approved origin that submitted the job (no proxying to arbitrary hosts).
4. CORS: responses echo the approved origin in `Access-Control-Allow-Origin`
   (never `*`), plus `Vary: Origin`. If a preflight carries
   `Access-Control-Request-Private-Network: true`, the helper answers with
   `Access-Control-Allow-Private-Network: true` (Private Network Access). The
   page side follows Chrome's Local Network Access requirements current at
   Step 6a (permission prompt; possibly only available from HTTPS pages).
   If the Pi page is served over HTTPS, requests to `http://127.0.0.1` aren't
   mixed content (loopback counts as potentially trustworthy).

## 3. Endpoints

### Detection and pairing

| Method, path | Response |
|---|---|
| `GET /v1/health` | `{ "service": "os3-focus-stacking-helper", "interfaceVersion": 1, "helperVersion": "x.y.z", "paired": bool }`. When the calling origin is approved, it additionally includes `"outputRoot"` and `"capabilities"` (`BackendCapabilities`). Answered for any origin with minimal fields, so the page can offer pairing. |
| `POST /v1/pair` | `202 { "status": "pending" }`, or `200` with `approved`/`denied` if already decided |
| `GET /v1/pair` | `{ "status": "pending" \| "approved" \| "denied" }` |

### Configuration (approved origins)

| Method, path | Body / response |
|---|---|
| `GET /v1/config` | `{ "outputRoot": "D:\\Scans\\stacked" }` |
| `PUT /v1/config` | `{ "outputRoot": "…" }`. The helper checks that the folder exists and is writable, else `400`. |

### Operations (approved origins)

Long operations run as jobs so no HTTP request stays open for minutes.

| Method, path | Body / response |
|---|---|
| `POST /v1/jobs/calibrate` | `CalibrateRequest` → `202 { "jobId": "…" }` |
| `POST /v1/jobs/stack` | `StackJob` → `202 { "jobId": "…" }` |
| `GET /v1/jobs/{jobId}` | `{ "state": "queued" \| "running" \| "done" \| "failed" \| "cancelled", "progress": Progress \| null, "result": CalibrateResult \| StackResult \| null, "error": ComputeErrorInfo \| null }` |
| `DELETE /v1/jobs/{jobId}` | Cancel → `202`. The page's `AbortSignal` maps to this call. |
| `POST /v1/prefetch` | `{ "urls": [ … ] }` → `202`. A hint, may be ignored. |

`StackResult.delivery` from the helper is `verified` (the helper re-reads the
file it wrote and compares it byte for byte) or the job fails with
`write-failed` / `verify-failed`.

### Runs (Step 6 sketch, final shape decided in Step 6)

The roadmap asks for a minimal control API (start/pause/stop) so a long scan
can continue in the helper even after the browser tab is closed. The helper then
runs the orchestrator logic itself (batch discovery via the OS3 API/WebSocket,
calibration policy, verification, optional deletion) using the same rules as
[compute-interface.md](compute-interface.md) §4–5:

| Method, path | Purpose |
|---|---|
| `POST /v1/runs` | Start: `{ "osApiBaseUrl", "project", "scanIndex", "live", "calibrationPolicy", "tilePlan", "numberFormat", "encoding", "deleteOriginals" }` |
| `GET /v1/runs/{runId}` | Status per position |
| `POST /v1/runs/{runId}/pause`, `/resume`, `/cancel` | Control |

## 4. Errors

Non-2xx responses carry `{ "error": ComputeErrorInfo }`. `400` for
`invalid-job`/`unsupported`, `403` for unapproved origins or disallowed image
hosts, `404` for unknown job/run ids, `409` for conflicting runs on the same
scan, `500` for `internal`.
