"""Merging: warp -> Laplacian^2 sharpness -> per-pixel maximum selection.

Ported from OS3's ``FocusStacker.stack`` (v0.13.0). See
compute-interface.md §3.3 for the normative description. This module is
untiled (Step 2 adds tiling on top of the same per-tile call).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from os3stack.batches import Batch
from os3stack.core import DOWNSCALE, apply_transform, compute_focus_map
from os3stack.imageio import DEFAULT_JPEG_QUALITY, load_image, save_image


@dataclass(frozen=True)
class StackResult:
    """Subset of compute-interface.ts's `StackResult` relevant to this
    untiled, synchronous reference implementation."""

    position: int
    width: int
    height: int
    output_path: str


def stack_batch(
    batch: Batch,
    transforms: list[np.ndarray],
    output_path: str,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    downscale: float = DOWNSCALE,
) -> StackResult:
    """Merge one batch into a single all-in-focus image and write it as JPEG.

    Args:
        batch: The images to merge (`batch.images[i]` corresponds to focus
            step i).
        transforms: One 2x3 matrix per focus step (`transforms[i]` maps
            output pixels to source pixels for `batch.images[i]`), e.g. from
            `calibrate()`. Length must equal `batch.stack_size`.
        output_path: Where to write the merged JPEG (parent dirs created).
        jpeg_quality: 1..100 (OS3 default: 90).
    """
    n = batch.stack_size
    if len(transforms) != n:
        raise ValueError(
            f"Expected {n} transforms (one per focus step), got {len(transforms)}"
        )

    if n == 1:
        img = load_image(str(batch.images[0].path))
        save_image(output_path, img, jpeg_quality)
        h, w = img.shape[:2]
        return StackResult(position=batch.position, width=w, height=h, output_path=output_path)

    reference_step = n // 2
    ref_img = load_image(str(batch.images[reference_step].path))
    h, w = ref_img.shape[:2]

    # Equivalent to OS3's inlined version: the reference image needs no
    # warp, so its focus map is just compute_focus_map() on the image as-is.
    best_focus = compute_focus_map(ref_img, downscale)

    result = ref_img.copy()

    for step in range(n):
        if step == reference_step:
            continue

        img = load_image(str(batch.images[step].path))
        aligned = apply_transform(img, transforms[step])
        focus = compute_focus_map(aligned, downscale)

        better = focus > best_focus  # strict: ties keep the earlier value
        result = np.where(better[..., np.newaxis], aligned, result)
        best_focus = np.where(better, focus, best_focus)

        del img, aligned, focus

    save_image(output_path, result, jpeg_quality)
    return StackResult(position=batch.position, width=w, height=h, output_path=output_path)
