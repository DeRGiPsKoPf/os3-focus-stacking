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

```
os3stack stack <scan-dir> [--output-dir DIR] [--calibration-batches N] [--jpeg-quality Q]
```

`<scan-dir>` is an OS3 scan folder (e.g. `.../MyProject/scan00`) containing
`scan{XX}_{NNN}_fs{SS}.jpg` files. Output defaults to `<scan-dir>/stacked`:
one `stacked_scan{XX}_{NNN}.jpg` per position plus `calibration_scan{XX}.json`
(format: `CalibrationRecord` in the spec).

Calibration uses the `spread` policy (batches evenly spaced over the scan),
matching completed-scan behaviour; live-scan policies (`leading`,
`calibration-scan`) are orchestrator concerns from Step 3a on, not part of
this reference CLI.

## Tests

```
pytest
```

Tests use synthetic images (no real scan data is stored in this repo).
Running the CLI on a real scan and inspecting the result by eye is Step 1's
actual test criterion — supply your own scan folder for that.
