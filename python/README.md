# os3stack

Step 1 (reference CLI) and Step 2 (tiling + comparison) of the OS3
Focus-Stacking project. Ports OpenScan3's own stacking algorithm
(`openscan_firmware/utils/photos/stacking.py`, v0.13.0) so it can run on a
scan folder outside the Pi, and serves as the benchmark every later compute
path (Pyodide, WebGPU, helper) is compared against.

See [../docs/spec/compute-interface.md](../docs/spec/compute-interface.md)
for the normative algorithm description and [../ROADMAP.md](../ROADMAP.md)
for the overall plan.

## Install

```
python -m venv .venv
.venv\Scripts\activate   # Windows; use `source .venv/bin/activate` elsewhere
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

**Troubleshooting `SSLEOFError` / "There was a problem confirming the ssl
certificate":** pip before 24.2 only trusts its own bundled CA list, not the
operating system's certificate store. If something on the machine inspects
TLS traffic (for example security software), `curl` and browsers still work
but old pip fails. pip ≥ 24.2 uses the system store. If upgrading pip itself
fails for that reason, do the upgrade once without certificate verification,
then continue normally with full verification:

```
python -m pip install --upgrade pip --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

## Usage

### `stack` — stack a whole scan folder

```
os3stack stack <scan-dir> [--output-dir DIR] [--calibration-batches N] [--calibration FILE] [--jpeg-quality Q]
```

`<scan-dir>` is an OS3 scan folder (e.g. `.../MyProject/scan00`) containing
`scan{XX}_{NNN}_fs{SS}.jpg` files. Output defaults to `<scan-dir>/stacked`:
one `stacked_scan{XX}_{NNN}.jpg` per position plus `calibration_scan{XX}.json`
(format: `CalibrationRecord` in the spec) — unless `--calibration FILE` is
given, which uses that file's transforms instead of calibrating (accepts
both our own file and OS3's own `calibration_scanXX.json`) and writes no new
calibration file. Useful to compare just the merge step against OS3's own
stacked output, e.g. when OS3's own focus-stacking task ran on the same
scan: point `--calibration` at the Pi's `stacked/calibration_scanXX.json`.

Calibration (when not overridden) uses the `spread` policy (batches evenly
spaced over the scan), matching completed-scan behaviour; live-scan policies
(`leading`, `calibration-scan`) are orchestrator concerns from Step 3a on,
not part of this reference CLI.

### `compare` — pixel-diff two images

```
os3stack compare <image-a> <image-b> [--threshold N] [--max-differing-fraction F] [--max-mean-deviation F]
```

Reports max/mean absolute deviation and the share of "differing" pixels (a
pixel's worst channel deviating by more than `--threshold`, default 1 of
255 — see `os3stack/compare.py` for why that's not fixed by the spec).
Exits 0 if both the differing-pixel share and the mean deviation are below
their limits (defaults: compute-interface.md §8's targets, 0.5% / 0.01·255),
1 otherwise. Use it to compare tiled against untiled output (Step 2) or our
output against OS3's own.

## Tests

```
pytest
```

Tests use synthetic images (no real scan data is stored in this repo).
Running the CLI on a real scan and inspecting the result by eye is Step 1's
actual test criterion — supply your own scan folder for that.
