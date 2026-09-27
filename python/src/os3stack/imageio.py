"""Image loading and saving.

Ported from OpenScan3's ``openscan_firmware/utils/photos/stacking.py``
(v0.13.0). OS3 declares neither ``opencv-python`` nor ``pyturbojpeg`` as a
dependency of the firmware package (checked against ``pyproject.toml`` at the
v0.13.0/``develop`` baseline, see ../../../tools/upstream-baseline.json): on
the Pi, ``cv2`` comes from a system package and TurboJPEG is unavailable
unless installed manually. The default code path is therefore
``cv2.imread``/``cv2.imwrite``, which is what this module always uses — no
TurboJPEG fallback, since reproducing an install nobody ships by default
would only add a silent divergence from the common case. This also means
EXIF Orientation IS applied on decode (OpenCV's default JPEG behaviour since
3.2), which is the assumption the rest of this package and the spec build on
(compute-interface.md §3.1).
"""

from __future__ import annotations

import os

import cv2
import numpy as np

#: OS3's default JPEG output quality (openscan_firmware/utils/photos/stacking.py).
DEFAULT_JPEG_QUALITY = 90


def load_image(path: str) -> np.ndarray:
    """Load a JPEG as a BGR uint8 array, applying EXIF orientation.

    Raises:
        FileNotFoundError: if `path` doesn't exist.
        ValueError: if the file exists but couldn't be decoded as an image.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Could not decode image: {path}")
    return img


def save_image(path: str, img: np.ndarray, quality: int = DEFAULT_JPEG_QUALITY) -> None:
    """Encode `img` (BGR uint8) as JPEG and write it to `path`.

    Creates parent directories as needed. Writes to a temporary name first
    and renames into place, so a crash or interrupted write never leaves a
    partial file under the final name (compute-interface.md §3.5).
    """
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)

    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError(f"Could not encode image for: {path}")

    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "wb") as f:
            f.write(buf.tobytes())
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
