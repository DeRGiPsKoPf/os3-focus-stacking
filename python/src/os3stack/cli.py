"""Reference CLI: stack a whole OS3 scan folder (Step 1 deliverable).

    os3stack stack <scan-dir> [--output-dir DIR] [--calibration-batches N]

Uses the `spread` calibration policy (compute-interface.md §4.2), matching
OS3's own completed-scan behaviour. Live-scan policies belong to the
orchestrator built in Step 3a, not this reference tool.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from os3stack.batches import find_image_batches, infer_project_and_scan
from os3stack.calibrate import calibrate, spread_batches, to_calibration_record
from os3stack.imageio import DEFAULT_JPEG_QUALITY
from os3stack.stack import stack_batch


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="os3stack", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    stack_cmd = subparsers.add_parser("stack", help="Stack every batch in a scan folder")
    stack_cmd.add_argument("scan_dir", type=Path, help="OS3 scan folder, e.g. .../MyProject/scan00")
    stack_cmd.add_argument(
        "--output-dir", type=Path, default=None,
        help="Where to write results (default: <scan-dir>/stacked)",
    )
    stack_cmd.add_argument(
        "--calibration-batches", type=int, default=3,
        help="Number of batches to calibrate from, spread over the scan (default: 3)",
    )
    stack_cmd.add_argument(
        "--jpeg-quality", type=int, default=DEFAULT_JPEG_QUALITY,
        help=f"Output JPEG quality, 1-100 (default: {DEFAULT_JPEG_QUALITY})",
    )
    stack_cmd.add_argument("--project", type=str, default=None, help="Override the inferred project name")
    stack_cmd.add_argument("--scan-index", type=int, default=None, help="Override the inferred scan index")

    return parser


def _run_stack(args: argparse.Namespace) -> int:
    scan_dir: Path = args.scan_dir
    if not scan_dir.is_dir():
        print(f"error: not a directory: {scan_dir}", file=sys.stderr)
        return 1

    output_dir: Path = args.output_dir or (scan_dir / "stacked")
    project_name, scan_index = infer_project_and_scan(scan_dir)
    if args.project is not None:
        project_name = args.project
    if args.scan_index is not None:
        scan_index = args.scan_index

    print(f"Scanning {scan_dir} ...")
    batches = find_image_batches(scan_dir, project_name=project_name, scan_index=scan_index)
    if not batches:
        print(f"error: no complete focus-stack batches found in {scan_dir}", file=sys.stderr)
        return 1

    stack_size = next(iter(batches.values())).stack_size
    print(f"Found {len(batches)} complete batch(es), stack size {stack_size}.")

    calibration_batches = spread_batches(batches, args.calibration_batches)
    print(
        f"Calibrating from {len(calibration_batches)} batch(es) at positions "
        f"{[b.position for b in calibration_batches]} ..."
    )
    t0 = time.monotonic()
    result = calibrate(calibration_batches)
    print(f"Calibration done in {time.monotonic() - t0:.1f}s.")
    if result.failures:
        print(f"warning: {len(result.failures)} alignment failure(s) fell back to identity:")
        for failure in result.failures:
            print(f"  position {failure.position}, focus step {failure.focus_step}: {failure.message}")

    output_dir.mkdir(parents=True, exist_ok=True)
    record = to_calibration_record(
        result,
        project_name=project_name,
        scan_index=scan_index,
        source_positions=[b.position for b in calibration_batches],
        policy={"kind": "spread", "batchCount": args.calibration_batches},
    )
    calibration_path = output_dir / f"calibration_scan{scan_index:02d}.json"
    calibration_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"Wrote {calibration_path}")

    t0 = time.monotonic()
    for position in sorted(batches):
        batch = batches[position]
        output_path = output_dir / f"stacked_scan{scan_index:02d}_{position:03d}.jpg"
        stack_batch(batch, result.transforms, str(output_path), jpeg_quality=args.jpeg_quality)
        print(f"  stacked position {position:03d} -> {output_path.name}")
    elapsed = time.monotonic() - t0
    print(f"Stacked {len(batches)} position(s) in {elapsed:.1f}s ({elapsed / len(batches):.2f}s/position).")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "stack":
        return _run_stack(args)
    parser.error(f"unknown command: {args.command}")
    return 2  # unreachable, parser.error() exits


if __name__ == "__main__":
    sys.exit(main())
