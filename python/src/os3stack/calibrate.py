"""Calibration: ECC affine alignment, per batch and averaged across batches.

Ported from OS3's ``FocusStacker.calibrate`` / ``calibrate_multi``
(v0.13.0). See compute-interface.md §3.2 for the normative description and
§4.2 for how batches are chosen (this module only computes transforms from
whatever batches it's given).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

import cv2
import numpy as np

from os3stack.batches import Batch
from os3stack.core import DOWNSCALE, compute_alignment_transform, resize_to_gray
from os3stack.imageio import load_image

#: OS3 version the algorithm in this module is ported from.
OS3_ALGORITHM_VERSION = "0.13.0"


@dataclass(frozen=True)
class CalibrationFailure:
    """compute-interface.ts: `CalibrationFailure`."""

    position: int
    focus_step: int
    message: str


@dataclass(frozen=True)
class CalibrationResult:
    """compute-interface.ts: `CalibrateResult`."""

    transforms: list[np.ndarray]  # index = focus step; transforms[reference_step] is identity
    reference_step: int
    stack_size: int
    image_width: int
    image_height: int
    per_batch_transforms: list[list[np.ndarray]]  # same order as the input batches
    failures: list[CalibrationFailure]


def calibrate_batch(batch: Batch, downscale: float = DOWNSCALE) -> tuple[list[np.ndarray], list[CalibrationFailure]]:
    """Align every image of one batch onto its reference image.

    Returns (transforms, failures); transforms[i] is the identity for
    i == reference_step, and for any step where ECC failed to converge.
    """
    n = batch.stack_size
    reference_step = n // 2

    ref_img = load_image(str(batch.images[reference_step].path))
    ref_gray_small = resize_to_gray(ref_img, downscale)
    ref_gray = cv2.boxFilter(ref_gray_small, -1, (5, 5))

    transforms: list[np.ndarray] = [np.eye(2, 3, dtype=np.float32) for _ in range(n)]
    failures: list[CalibrationFailure] = []

    for step in range(n):
        if step == reference_step:
            continue
        img = load_image(str(batch.images[step].path))
        matrix, ok = compute_alignment_transform(img, ref_gray, downscale)
        transforms[step] = matrix
        if not ok:
            failures.append(CalibrationFailure(
                position=batch.position,
                focus_step=step,
                message="cv2.findTransformECC did not converge; using identity",
            ))

    return transforms, failures


def calibrate(batches: list[Batch], downscale: float = DOWNSCALE) -> CalibrationResult:
    """Calibrate from one or more batches, averaging transforms element-wise
    across batches (OS3's `calibrate_multi` when len(batches) > 1)."""
    if not batches:
        raise ValueError("calibrate() requires at least one batch")

    stack_size = batches[0].stack_size
    for batch in batches:
        if batch.stack_size != stack_size:
            raise ValueError(
                f"All batches must share the same stack size; "
                f"position {batches[0].position} has {stack_size}, "
                f"position {batch.position} has {batch.stack_size}"
            )

    reference_step = stack_size // 2
    sample_img = load_image(str(batches[0].images[0].path))
    height, width = sample_img.shape[:2]

    per_batch_transforms: list[list[np.ndarray]] = []
    all_failures: list[CalibrationFailure] = []
    for batch in batches:
        transforms, failures = calibrate_batch(batch, downscale)
        per_batch_transforms.append(transforms)
        all_failures.extend(failures)

    averaged: list[np.ndarray] = []
    for step in range(stack_size):
        stacked = np.stack([t[step] for t in per_batch_transforms], axis=0)
        averaged.append(np.mean(stacked, axis=0).astype(np.float32))

    return CalibrationResult(
        transforms=averaged,
        reference_step=reference_step,
        stack_size=stack_size,
        image_width=width,
        image_height=height,
        per_batch_transforms=per_batch_transforms,
        failures=all_failures,
    )


def spread_batches(all_batches: dict[int, Batch], batch_count: int) -> list[Batch]:
    """`spread` calibration policy (compute-interface.md §4.2): `batch_count`
    batches evenly spaced over the scan, ordered by position (OS3 uses
    file-system enumeration order; ordering by position is equivalent for a
    completed scan and deterministic)."""
    positions = sorted(all_batches.keys())
    if not positions:
        raise ValueError("No batches to select from")
    batch_count = min(batch_count, len(positions))
    indices = np.linspace(0, len(positions) - 1, batch_count, dtype=int)
    return [all_batches[positions[i]] for i in indices]


def to_calibration_record(
    result: CalibrationResult,
    *,
    project_name: str,
    scan_index: int,
    source_positions: list[int],
    policy: dict,
) -> dict:
    """Build a JSON-serialisable `CalibrationRecord` (compute-interface.ts)."""
    return {
        "project": project_name,
        "scan_index": scan_index,
        "transforms": [t.tolist() for t in result.transforms],
        "formatVersion": 1,
        "referenceStep": result.reference_step,
        "stackSize": result.stack_size,
        "imageWidth": result.image_width,
        "imageHeight": result.image_height,
        "policy": policy,
        "sourcePositions": source_positions,
        "failures": [
            {"position": f.position, "focusStep": f.focus_step, "message": f.message}
            for f in result.failures
        ],
        "algorithm": {
            "name": "os3-ecc-affine",
            "os3Version": OS3_ALGORITHM_VERSION,
            "downscale": DOWNSCALE,
        },
        "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
