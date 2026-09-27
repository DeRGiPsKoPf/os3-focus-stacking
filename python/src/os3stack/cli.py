"""Reference CLI: stack a whole OS3 scan folder (Step 1), and a pixel-diff
comparison tool (Step 2, pulled forward).

    os3stack stack <scan-dir> [--output-dir DIR] [--calibration-batches N] [--calibration FILE]
    os3stack compare <image-a> <image-b> [--threshold N]

`stack` uses the `spread` calibration policy (compute-interface.md §4.2),
matching OS3's own completed-scan behaviour, unless `--calibration` points
at an existing calibration file (ours or OS3's own) to use instead — useful
to compare just the merge step against OS3's own stacked output, without
also comparing which batches got picked for calibration. Live-scan policies
belong to the orchestrator built in Step 3a, not this reference tool.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from os3stack.batches import find_image_batches, infer_project_and_scan
from os3stack.calibrate import calibrate, spread_batches, to_calibration_record
from os3stack.calibration_io import load_calibration_transforms
from os3stack.compare import (
    DEFAULT_MAX_DIFFERING_FRACTION,
    DEFAULT_MAX_MEAN_DEVIATION,
    DEFAULT_THRESHOLD,
    compare_images,
    format_report,
)
from os3stack.imageio import DEFAULT_JPEG_QUALITY
from os3stack.stack import stack_batch
from os3stack.tiling import TilePlan, grid_plan


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
        help="Number of batches to calibrate from, spread over the scan (default: 3). "
             "Ignored if --calibration is given.",
    )
    stack_cmd.add_argument(
        "--calibration", type=Path, default=None,
        help="Use transforms from an existing calibration JSON (ours or OS3's own "
             "calibration_scanXX.json) instead of calibrating. Skips writing a new "
             "calibration file.",
    )
    stack_cmd.add_argument(
        "--jpeg-quality", type=int, default=DEFAULT_JPEG_QUALITY,
        help=f"Output JPEG quality, 1-100 (default: {DEFAULT_JPEG_QUALITY})",
    )
    stack_cmd.add_argument("--project", type=str, default=None, help="Override the inferred project name")
    stack_cmd.add_argument("--scan-index", type=int, default=None, help="Override the inferred scan index")
    stack_cmd.add_argument(
        "--tile-width", type=int, default=None,
        help="Merge tile-by-tile (compute-interface.md §3.4) instead of the whole image at "
             "once. Requires --tile-height and --tile-overlap too. Multiple of 4.",
    )
    stack_cmd.add_argument("--tile-height", type=int, default=None, help="See --tile-width. Multiple of 4.")
    stack_cmd.add_argument(
        "--tile-overlap", type=int, default=None,
        help="Context added on every side of each tile before merging; only the tile's core "
             "is kept. See --tile-width. Multiple of 4, at least 16.",
    )

    compare_cmd = subparsers.add_parser(
        "compare", help="Pixel-diff two images (compute-interface.md §3.4/§8)"
    )
    compare_cmd.add_argument("image_a", type=Path)
    compare_cmd.add_argument("image_b", type=Path)
    compare_cmd.add_argument(
        "--threshold", type=int, default=DEFAULT_THRESHOLD,
        help=f"Per-pixel worst-channel deviation (0-255) above which a pixel counts "
             f"as differing (default: {DEFAULT_THRESHOLD})",
    )
    compare_cmd.add_argument(
        "--max-differing-fraction", type=float, default=DEFAULT_MAX_DIFFERING_FRACTION,
        help=f"Exit 1 if the differing-pixel share is at or above this (default: "
             f"{DEFAULT_MAX_DIFFERING_FRACTION})",
    )
    compare_cmd.add_argument(
        "--max-mean-deviation", type=float, default=DEFAULT_MAX_MEAN_DEVIATION,
        help=f"Exit 1 if the mean absolute deviation is at or above this, out of 255 "
             f"(default: {DEFAULT_MAX_MEAN_DEVIATION:.3f})",
    )

    return parser


def _resolve_transforms(args: argparse.Namespace, batches, stack_size: int):
    """Return (transforms, calibration_record_or_None) per --calibration or
    the `spread` policy. `calibration_record_or_None` is written to
    <output-dir>/calibration_scanXX.json only when we computed it ourselves."""
    if args.calibration is not None:
        print(f"Loading calibration from {args.calibration} ...")
        transforms = load_calibration_transforms(str(args.calibration))
        if len(transforms) != stack_size:
            raise ValueError(
                f"{args.calibration} has {len(transforms)} transform(s), "
                f"but this scan's stack size is {stack_size}"
            )
        return transforms, None

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

    record = to_calibration_record(
        result,
        project_name=calibration_batches[0].project_name,
        scan_index=calibration_batches[0].scan_index,
        source_positions=[b.position for b in calibration_batches],
        policy={"kind": "spread", "batchCount": args.calibration_batches},
    )
    return result.transforms, record


def _resolve_tile_plan(args: argparse.Namespace) -> TilePlan | None:
    """None (untiled) if none of --tile-width/-height/-overlap were given;
    a validated grid plan if all three were. Raises ValueError otherwise,
    or if the values themselves are invalid (see tiling.grid_plan)."""
    given = {
        "--tile-width": args.tile_width,
        "--tile-height": args.tile_height,
        "--tile-overlap": args.tile_overlap,
    }
    provided = {name: value for name, value in given.items() if value is not None}
    if not provided:
        return None
    if len(provided) != len(given):
        missing = ", ".join(name for name, value in given.items() if value is None)
        raise ValueError(f"--tile-width/--tile-height/--tile-overlap must all be given together; missing {missing}")
    return grid_plan(args.tile_width, args.tile_height, args.tile_overlap)


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

    try:
        tile_plan = _resolve_tile_plan(args)  # validate before the (possibly slow) calibration
        transforms, record = _resolve_transforms(args, batches, stack_size)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if tile_plan is not None:
        print(f"Tiling: {tile_plan.tile_width}x{tile_plan.tile_height}, overlap {tile_plan.overlap}")

    output_dir.mkdir(parents=True, exist_ok=True)
    if record is not None:
        calibration_path = output_dir / f"calibration_scan{scan_index:02d}.json"
        calibration_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(f"Wrote {calibration_path}")

    t0 = time.monotonic()
    for position in sorted(batches):
        batch = batches[position]
        output_path = output_dir / f"stacked_scan{scan_index:02d}_{position:03d}.jpg"
        stack_batch(batch, transforms, str(output_path), jpeg_quality=args.jpeg_quality, tile_plan=tile_plan)
        print(f"  stacked position {position:03d} -> {output_path.name}")
    elapsed = time.monotonic() - t0
    print(f"Stacked {len(batches)} position(s) in {elapsed:.1f}s ({elapsed / len(batches):.2f}s/position).")

    return 0


def _run_compare(args: argparse.Namespace) -> int:
    for path in (args.image_a, args.image_b):
        if not path.is_file():
            print(f"error: not a file: {path}", file=sys.stderr)
            return 1

    try:
        result = compare_images(str(args.image_a), str(args.image_b), threshold=args.threshold)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"{args.image_a.name} vs {args.image_b.name}")
    print(format_report(result))

    ok = result.within_tolerance(args.max_differing_fraction, args.max_mean_deviation)
    print("PASS" if ok else "FAIL", "(tolerance: "
          f"<{args.max_differing_fraction * 100:.2f}% differing, "
          f"<{args.max_mean_deviation:.3f} mean deviation)")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "stack":
        return _run_stack(args)
    if args.command == "compare":
        return _run_compare(args)
    parser.error(f"unknown command: {args.command}")
    return 2  # unreachable, parser.error() exits


if __name__ == "__main__":
    sys.exit(main())
