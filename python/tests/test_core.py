import numpy as np

from os3stack.core import (
    apply_transform,
    compute_alignment_transform,
    compute_focus_map,
    resize_to_gray,
)

from _synthetic import blur, make_checkerboard


def test_resize_to_gray_shape_and_range():
    img = make_checkerboard(64, 48, seed=1)
    gray = resize_to_gray(img, 0.25)

    assert gray.shape == (12, 16)  # (height, width) at 0.25 scale
    assert gray.dtype == np.float32
    assert gray.min() >= 0.0
    assert gray.max() <= 1.0


def test_compute_focus_map_is_higher_for_sharper_image():
    sharp = make_checkerboard(64, 64, seed=2)
    blurred = blur(sharp, 9)

    sharp_energy = compute_focus_map(sharp).mean()
    blurred_energy = compute_focus_map(blurred).mean()

    assert sharp_energy > blurred_energy


def test_apply_transform_identity_is_a_no_op():
    img = make_checkerboard(64, 64, seed=3)
    identity = np.eye(2, 3, dtype=np.float32)

    warped = apply_transform(img, identity)

    assert warped.shape == img.shape
    # Bilinear sampling at exact integer coordinates reproduces the source
    # exactly; only floating-point identity is assumed here.
    assert np.array_equal(warped, img)


def test_compute_alignment_transform_identical_image_is_near_identity():
    # Large enough that the 0.25 downscale still leaves ECC enough texture
    # to converge reliably (see tests/_synthetic.py's IMAGE_SIZE comment).
    img = make_checkerboard(256, 256, square=32, seed=4)
    ref_gray_small = resize_to_gray(img, 0.25)
    import cv2

    ref_gray = cv2.boxFilter(ref_gray_small, -1, (5, 5))

    matrix, ok = compute_alignment_transform(img, ref_gray, scale=0.25)

    assert ok
    identity = np.eye(2, 3, dtype=np.float32)
    assert np.allclose(matrix, identity, atol=0.5)
