"""Synthetic image helpers shared by conftest.py and test modules.

Kept separate from conftest.py so test modules can import these plain
functions directly, without relying on pytest's conftest-as-package import
mechanics.
"""

from __future__ import annotations

import cv2
import numpy as np


def make_checkerboard(width: int, height: int, square: int = 8, seed: int = 0) -> np.ndarray:
    """A textured BGR image (checkerboard + noise) so ECC has gradients to
    align on and the Laplacian sharpness measure is meaningful."""
    rng = np.random.default_rng(seed)
    grid = np.indices((height, width)).sum(axis=0)
    base = ((grid // square) % 2).astype(np.uint8) * 255
    img = np.stack([base, base, base], axis=-1)
    noise = rng.integers(0, 30, size=img.shape, dtype=np.uint8)
    return cv2.add(img, noise)


def blur(img: np.ndarray, ksize: int) -> np.ndarray:
    if ksize <= 1:
        return img.copy()
    return cv2.GaussianBlur(img, (ksize, ksize), 0)


#: focus_step -> Gaussian blur kernel size. Step 1 (the reference/middle
#: step for a 3-image stack) is sharpest; 0 and 2 are visibly blurred.
BLUR_BY_STEP = {0: 9, 1: 1, 2: 9}
SHARPEST_STEP = 1
#: Large enough that the 0.25 ECC/focus-map downscale (compute-interface.md
#: §3.2) still leaves a workable amount of texture (64x64 at that scale is
#: only 16x16 px, too little for reliable ECC convergence).
IMAGE_SIZE = 256
CHECKER_SQUARE = 32


def write_scan(scan_path, positions: tuple[int, ...] = (0, 1), jpeg_quality: int = 95) -> None:
    scan_path.mkdir(parents=True, exist_ok=True)
    scan_index = 0
    for position in positions:
        base = make_checkerboard(IMAGE_SIZE, IMAGE_SIZE, square=CHECKER_SQUARE, seed=position)
        for step, ksize in BLUR_BY_STEP.items():
            img = blur(base, ksize)
            path = scan_path / f"scan{scan_index:02d}_{position:03d}_fs{step:02d}.jpg"
            cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
