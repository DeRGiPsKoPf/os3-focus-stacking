"""Loading an existing calibration record (ours or OS3's own) from disk.

Lets `os3stack stack` use transforms someone else already computed instead
of calibrating itself — in particular OS3's own `calibration_scanXX.json`
(written by `focus_stacking_task.py`), so a comparison against OS3's own
stacked output isolates the merge algorithm from calibration differences
(compute-interface.md §4.2 notes OS3 and this project can pick different
calibration batches). OS3's file only has `project`, `scan_index` and
`transforms`; every other field here is optional.
"""

from __future__ import annotations

import json

import numpy as np


def load_calibration_transforms(path: str) -> list[np.ndarray]:
    """Read a calibration JSON's `transforms` field as a list of 2x3 float32
    matrices, index = focus step (compute-interface.md's `AffineMatrix`).

    Accepts both OS3's own minimal file and our `CalibrationRecord` superset
    — only the `transforms` field is used.
    """
    with open(path, "r", encoding="utf-8") as f:
        record = json.load(f)

    raw_transforms = record.get("transforms")
    if not raw_transforms:
        raise ValueError(f"No 'transforms' field in calibration file: {path}")

    transforms = []
    for i, matrix in enumerate(raw_transforms):
        arr = np.array(matrix, dtype=np.float32)
        if arr.shape != (2, 3):
            raise ValueError(
                f"transforms[{i}] in {path} has shape {arr.shape}, expected (2, 3)"
            )
        transforms.append(arr)

    return transforms
