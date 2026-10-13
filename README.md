# OS3 Focus Stacking

*Still in development — use at your own risk.*

[OpenScan3](https://github.com/OpenScan-org/OpenScan3) scans a turntable
position by taking a bracket of photos at different focus distances, then
needs that bracket stacked into one sharp image before it's usable for 3D
reconstruction. Today that stacking happens as a separate step, after the
*entire* scan — hundreds of positions, a dozen-plus photos each — is already
captured. This project moves that work into the browser tab you're already
watching the scan from: as soon as one position's bracket finishes, it gets
stacked while the camera moves on to the next one, so by the time the scan
ends, only the very last position is still waiting.

## What it is

- **An additive "Stacking" tab inside
  [`OpenScan3-Client`](https://github.com/OpenScan-org/OpenScan3-Client)** —
  not a fork, not an iframe, the same Vue app with one more tab, next to the
  existing "Scan" tab, aimed at an eventual upstream pull request. The
  `OpenScan3` firmware itself isn't touched.
- **Served by the Pi, computed in your browser** — open the tab, nothing to
  install, works from any device already on the scanner's network.
- **The same algorithm OpenScan3 already uses for stacking** (`stacking.py`'s
  ECC alignment + Laplacian-sharpness pixel selection), ported faithfully and
  checked pixel-for-pixel against OS3's own output — results don't change,
  just where and when they get computed.
- **Tiled from the start**, so it scales to a full-resolution camera sensor,
  not just small previews.
- A **local helper program** (planned) will pick up the same job over HTTP
  for scans too large to stack in the browser alone.

See [ROADMAP.md](ROADMAP.md) for the full plan and the reasoning behind
every decision — bit depth, calibration batches, safe deletion, HTTPS,
compute-path priority, and more.

## Status

Steps 0–2 done: the compute interface is specified in
[docs/spec/](docs/spec/compute-interface.md), and a Python reference
implementation (`python/`, package `os3stack`) ports OS3's own calibration
and merging, including tiled merging, with a CLI and tests, verified
against a real photo. Step 3 (a "Stacking" tab in `OpenScan3-Client`,
against a mock compute backend) is built and working, but lives in a local
clone for now and isn't pushed yet — no real computation runs in the
browser/helper yet. See [ROADMAP.md](ROADMAP.md) for the full plan,
architecture decisions, and current step, and [CHANGELOG.md](CHANGELOG.md)
for what's landed. [AGENTS.md](AGENTS.md) has a short reference for anyone
(human or agent) implementing a step, including the repository layout and
the upstream change check (`python tools/check_upstream.py`).

## License

GPL-3.0, consistent with `OpenScan3` and `OpenScan3-Client`. See
[LICENSE](LICENSE).
