#!/usr/bin/env python3
"""Copy the os3stack modules the browser backend runs into the client.

The Pyodide backend (Step 4) runs this repo's Python reference code itself,
not a port of it: the client ships a verbatim copy of the modules below,
which the Web Worker writes into Pyodide's file system and imports. This
tool is the only way that copy changes, so client and reference can't drift
apart silently.

    python tools/sync_client_python.py           # copy into the client
    python tools/sync_client_python.py --check   # exit 1 if the copy differs

Line endings are ignored when comparing (git may convert them on checkout).

Exit codes: 0 = in sync (or copied), 1 = out of sync (--check), 2 = error.
"""

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "python" / "src" / "os3stack"
DEFAULT_CLIENT = REPO.parent / "os3-stacking-client"
TARGET_IN_CLIENT = Path("app/src/stacking/compute/pyodide/os3stack")

#: What calibrate() and merge_batch() import, and nothing else: no CLI, no
#: comparison tool, no file-based calibration loading.
MODULES = (
    "__init__.py",
    "batches.py",
    "calibrate.py",
    "core.py",
    "imageio.py",
    "stack.py",
    "tiling.py",
)


def normalized(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="only compare, don't copy")
    parser.add_argument("--client", type=Path, default=DEFAULT_CLIENT, help=f"client checkout (default: {DEFAULT_CLIENT})")
    args = parser.parse_args()

    if not (args.client / "app").is_dir():
        print(f"error: no client checkout at {args.client}", file=sys.stderr)
        return 2
    target = args.client / TARGET_IN_CLIENT

    expected = set(MODULES)
    present = {p.name for p in target.glob("*.py")} if target.is_dir() else set()
    differing = [m for m in MODULES if not (target / m).exists() or normalized(target / m) != normalized(SOURCE / m)]
    extra = sorted(present - expected)

    if args.check:
        for name in differing:
            print(f"differs: {TARGET_IN_CLIENT / name}")
        for name in extra:
            print(f"not a synced module: {TARGET_IN_CLIENT / name}")
        if differing or extra:
            print("out of sync - run: python tools/sync_client_python.py")
            return 1
        print(f"in sync: {len(MODULES)} modules in {TARGET_IN_CLIENT}")
        return 0

    target.mkdir(parents=True, exist_ok=True)
    for name in differing:
        (target / name).write_bytes(normalized(SOURCE / name))
        print(f"copied: {TARGET_IN_CLIENT / name}")
    for name in extra:
        (target / name).unlink()
        print(f"removed: {TARGET_IN_CLIENT / name}")
    if not differing and not extra:
        print("already in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
