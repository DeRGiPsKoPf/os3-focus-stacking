"""Low-level image operations shared by calibration and merging.

Ported 1:1 from OpenScan3's ``openscan_firmware/utils/photos/stacking.py``
(v0.13.0). Every function here corresponds to a normative step in
compute-interface.md §3.2/§3.3 — keep them in sync, and keep this module free
of anything that isn't part of that exact algorithm (batching, I/O, CLI
concerns belong elsewhere).
"""

from __future__ import annotations

import cv2
import numpy as np

#: Downscale factor for the focus map and for ECC alignment. Also fixes the
#: tiling grid: tile size/overlap must be multiples of 1/DOWNSCALE = 4 px
#: (compute-interface.md §3.4).
DOWNSCALE = 0.25

#: cv2.findTransformECC criteria (OS3: 20 iterations, 1e-6 epsilon).
_ECC_CRITERIA = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 1e-6)


def resize_to_gray(img: np.ndarray, scale: float) -> np.ndarray:
    """Downscale by `scale` and convert to float32 grey in [0, 1]."""
    h, w = img.shape[:2]
    small = cv2.resize(img, (int(w * scale), int(h * scale)))
    return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0


def compute_focus_energy_lowres(img: np.ndarray, downscale: float = DOWNSCALE) -> np.ndarray:
    """Laplacian-squared sharpness energy at `downscale` resolution, without
    resizing back up.

    Split out from `compute_focus_map` for backends that can't afford a
    full-resolution focus map per source image (a real memory- or
    texture-size-constrained tiled backend, e.g. Step 5's WebGPU): compute
    this once per whole source image, then slice+upsize the relevant region
    per tile, instead of downscaling each tile's own cropped pixels
    independently (the two aren't equivalent — independently downscaling a
    crop resamples on a grid anchored to that crop's own dimensions, which
    disagrees with the full image's resampling grid almost everywhere in the
    tile, not just near its edges).

    Note this function is currently unused by `os3stack.stack`: this CPU
    reference implementation can afford full-resolution focus maps (it
    already holds full-resolution aligned pixels for every source at once),
    so it slices those directly instead — exact for any image size. Slicing
    *this* low-res-then-upsized-per-tile array is only exact when the whole
    image's width and height are themselves multiples of 4 (so the global
    downscale ratio `int(size*downscale)/size` is exactly `downscale`, matching
    every tile's own ratio); tile boundaries being multiples of 4 alone isn't
    enough. See os3stack.stack's module docstring for the full reasoning and
    what an exact-for-any-size version of this approach would need (padding).
    """
    gray = resize_to_gray(img, downscale)
    laplacian = cv2.Laplacian(gray, cv2.CV_32F, ksize=3)
    return laplacian * laplacian


def compute_focus_map(img: np.ndarray, downscale: float = DOWNSCALE) -> np.ndarray:
    """Laplacian-squared sharpness energy, computed at `downscale` and
    resized back to `img`'s full resolution."""
    h, w = img.shape[:2]
    energy = compute_focus_energy_lowres(img, downscale)
    return cv2.resize(energy, (w, h))


def compute_alignment_transform(
    img: np.ndarray, ref_gray: np.ndarray, scale: float = DOWNSCALE
) -> tuple[np.ndarray, bool]:
    """ECC affine alignment of `img` onto a preprocessed reference.

    Returns (matrix, ok). On ECC failure, `matrix` is the identity — the
    same outcome OS3 produces, since ``warp`` is only reassigned on a
    successful `findTransformECC` return (compute-interface.md §3.2) — and
    `ok` is False so callers can record it as a `CalibrationFailure`.
    """
    gray = resize_to_gray(img, scale)
    gray = cv2.boxFilter(gray, -1, (5, 5))
    warp = np.eye(2, 3, dtype=np.float32)

    try:
        _, warp = cv2.findTransformECC(
            ref_gray, gray, warp, cv2.MOTION_AFFINE, _ECC_CRITERIA,
            inputMask=None, gaussFiltSize=3,
        )
        warp[:, 2] /= scale
        return warp, True
    except cv2.error:
        return warp, False


def apply_transform(img: np.ndarray, transform: np.ndarray) -> np.ndarray:
    """Warp `img` with a 2x3 affine matrix (output -> source, compute-
    interface.md's `AffineMatrix` convention)."""
    h, w = img.shape[:2]
    return cv2.warpAffine(
        img, transform, (w, h),
        flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_CONSTANT,
    )
