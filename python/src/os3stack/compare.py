"""Pixel-diff comparison between two images (Step 2 deliverable, pulled
forward to also compare our output against OS3's own on a real scan).

compute-interface.md §3.4/§8 states the tolerance targets (share of
differing pixels < 0.5%, mean absolute deviation < 0.01 of 255) but doesn't
fix what counts as a single pixel "differing" — JPEG re-encoding alone
introduces a few levels of noise even for genuinely identical content. This
module makes that threshold explicit and adjustable instead of guessing at
whatever the original Step 2 measurements (already in ROADMAP.md) used;
those numbers may need re-measuring against this exact definition (noted
there already).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from os3stack.imageio import load_image

#: A pixel counts as "differing" when its worst channel's absolute deviation
#: exceeds this many levels (0..255). 1 tolerates the +-1 rounding noise two
#: independent JPEG encodes of the same content typically produce, without
#: hiding a real difference.
DEFAULT_THRESHOLD = 1

#: compute-interface.md §8 / ROADMAP.md Step 2 targets.
DEFAULT_MAX_DIFFERING_FRACTION = 0.005
DEFAULT_MAX_MEAN_DEVIATION = 0.01 * 255


@dataclass(frozen=True)
class ComparisonResult:
    width: int
    height: int
    total_pixels: int
    max_abs_deviation: int  # 0..255, worst single channel value over the whole image
    mean_abs_deviation: float  # 0..255, averaged over all channels and pixels
    differing_pixel_count: int
    differing_pixel_fraction: float  # 0.0..1.0
    threshold: int

    def within_tolerance(
        self,
        max_differing_fraction: float = DEFAULT_MAX_DIFFERING_FRACTION,
        max_mean_deviation: float = DEFAULT_MAX_MEAN_DEVIATION,
    ) -> bool:
        return (
            self.differing_pixel_fraction < max_differing_fraction
            and self.mean_abs_deviation < max_mean_deviation
        )


def compare_arrays(a: np.ndarray, b: np.ndarray, threshold: int = DEFAULT_THRESHOLD) -> ComparisonResult:
    """Compare two BGR uint8 arrays of the same shape."""
    if a.shape != b.shape:
        raise ValueError(f"Shape mismatch: {a.shape} vs {b.shape}")

    diff = np.abs(a.astype(np.int16) - b.astype(np.int16))
    per_pixel_max = diff.max(axis=2) if diff.ndim == 3 else diff

    differing_mask = per_pixel_max > threshold
    total = int(per_pixel_max.size)
    differing = int(differing_mask.sum())

    return ComparisonResult(
        width=a.shape[1],
        height=a.shape[0],
        total_pixels=total,
        max_abs_deviation=int(diff.max()),
        mean_abs_deviation=float(diff.mean()),
        differing_pixel_count=differing,
        differing_pixel_fraction=differing / total,
        threshold=threshold,
    )


def compare_images(path_a: str, path_b: str, threshold: int = DEFAULT_THRESHOLD) -> ComparisonResult:
    """Load two JPEGs (compute-interface.md §3.1 decode rules apply) and compare."""
    a = load_image(path_a)
    b = load_image(path_b)
    return compare_arrays(a, b, threshold)


def format_report(result: ComparisonResult) -> str:
    return (
        f"{result.width}x{result.height} ({result.total_pixels} pixels)\n"
        f"  max abs deviation:  {result.max_abs_deviation} / 255\n"
        f"  mean abs deviation: {result.mean_abs_deviation:.4f} / 255\n"
        f"  differing pixels:   {result.differing_pixel_count} "
        f"({result.differing_pixel_fraction * 100:.3f}%), threshold={result.threshold}"
    )
