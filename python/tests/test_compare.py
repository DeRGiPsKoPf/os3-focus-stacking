import numpy as np

from os3stack.compare import compare_arrays, compare_images


def test_identical_arrays_have_zero_deviation():
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    img[:] = 100

    result = compare_arrays(img, img.copy())

    assert result.max_abs_deviation == 0
    assert result.mean_abs_deviation == 0.0
    assert result.differing_pixel_count == 0
    assert result.differing_pixel_fraction == 0.0
    assert result.within_tolerance()


def test_detects_a_localized_difference():
    a = np.zeros((10, 10, 3), dtype=np.uint8)
    b = a.copy()
    b[0, 0] = [50, 50, 50]  # one pixel, well above the default threshold

    result = compare_arrays(a, b, threshold=1)

    assert result.max_abs_deviation == 50
    assert result.differing_pixel_count == 1
    assert result.differing_pixel_fraction == 1 / 100
    assert result.total_pixels == 100


def test_threshold_absorbs_small_noise():
    a = np.full((4, 4, 3), 100, dtype=np.uint8)
    b = a.copy()
    b[0, 0] = 101  # deviation of 1

    within_default = compare_arrays(a, b, threshold=1)
    within_zero = compare_arrays(a, b, threshold=0)

    assert within_default.differing_pixel_count == 0
    assert within_zero.differing_pixel_count == 1


def test_shape_mismatch_raises():
    a = np.zeros((10, 10, 3), dtype=np.uint8)
    b = np.zeros((5, 5, 3), dtype=np.uint8)
    try:
        compare_arrays(a, b)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_within_tolerance_respects_both_conditions():
    a = np.zeros((100, 100, 3), dtype=np.uint8)
    b = a.copy()
    # 100 of 10000 pixels (1%) differ a lot -- exceeds the default 0.5% target.
    b[:, 0] = 200

    result = compare_arrays(a, b)

    assert result.differing_pixel_fraction == 0.01
    assert not result.within_tolerance()
    assert result.within_tolerance(max_differing_fraction=0.02, max_mean_deviation=1000)


def test_compare_images_loads_and_compares_files(tmp_path):
    from os3stack.imageio import save_image

    img = np.full((16, 16, 3), 128, dtype=np.uint8)
    path_a = tmp_path / "a.jpg"
    path_b = tmp_path / "b.jpg"
    save_image(str(path_a), img, quality=100)
    save_image(str(path_b), img, quality=100)

    result = compare_images(str(path_a), str(path_b))

    assert result.width == 16
    assert result.height == 16
    # High-quality re-encode of an identical flat image should be exact or
    # very nearly so; either way it must be within tolerance.
    assert result.within_tolerance()
