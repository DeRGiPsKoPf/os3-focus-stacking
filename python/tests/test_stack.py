import numpy as np
import pytest

from _synthetic import SHARPEST_STEP
from os3stack.batches import Batch, find_image_batches
from os3stack.calibrate import calibrate
from os3stack.compare import compare_arrays
from os3stack.imageio import load_image
from os3stack.stack import stack_batch
from os3stack.tiling import grid_plan


def _identity_transforms(n: int) -> list[np.ndarray]:
    return [np.eye(2, 3, dtype=np.float32) for _ in range(n)]


def test_stack_batch_result_is_close_to_the_sharpest_step(scan_dir, tmp_path):
    batches = find_image_batches(scan_dir)
    batch = batches[0]
    output_path = tmp_path / "stacked_scan00_000.jpg"

    result = stack_batch(batch, _identity_transforms(batch.stack_size), str(output_path))

    assert result.position == 0
    assert result.width == 256
    assert result.height == 256
    assert output_path.exists()

    stacked = load_image(str(output_path))
    reference = load_image(str(batch.images[SHARPEST_STEP].path))
    # No misalignment in this fixture (only blur differs between steps) and
    # the reference step is already the sharpest, so the merge should barely
    # deviate from it.
    mean_abs_diff = np.mean(np.abs(stacked.astype(np.int16) - reference.astype(np.int16)))
    assert mean_abs_diff < 5.0


def test_stack_batch_single_image_reencodes_unchanged(scan_dir, tmp_path):
    batches = find_image_batches(scan_dir)
    only_image = batches[0].images[0]
    single_batch = Batch(
        project_name="MyProject", scan_index=0, position=0, images=(only_image,)
    )
    output_path = tmp_path / "stacked_scan00_000.jpg"

    result = stack_batch(single_batch, _identity_transforms(1), str(output_path))

    assert result.width == 256 and result.height == 256
    original = load_image(str(only_image.path))
    reencoded = load_image(str(output_path))
    assert np.mean(np.abs(original.astype(int) - reencoded.astype(int))) < 2.0


def test_stack_batch_rejects_wrong_transform_count(scan_dir, tmp_path):
    batches = find_image_batches(scan_dir)
    batch = batches[0]

    try:
        stack_batch(batch, _identity_transforms(2), str(tmp_path / "out.jpg"))
        assert False, "expected ValueError"
    except ValueError:
        pass


@pytest.mark.parametrize(
    "tile_width, tile_height, overlap",
    [
        (64, 64, 16),   # 4x4 grid, evenly divides 256 -- no clipped tiles
        (100, 100, 16),  # 3x3 grid, clipped last row/column
    ],
)
def test_tiled_stack_batch_matches_untiled_within_tolerance(scan_dir, tmp_path, tile_width, tile_height, overlap):
    """compute-interface.md §3.4/§8: tiled vs. untiled merging of the same
    batch and transforms should agree within Step 2's tolerance. Real ECC
    transforms (not identity) so the tiles actually sample non-trivial
    source regions, matching a real scan more closely than the identity
    case the other tests here use."""
    batches = find_image_batches(scan_dir)
    batch = batches[0]
    calibration = calibrate([batch])

    untiled_path = tmp_path / "untiled.jpg"
    tiled_path = tmp_path / "tiled.jpg"
    stack_batch(batch, calibration.transforms, str(untiled_path))
    stack_batch(
        batch, calibration.transforms, str(tiled_path),
        tile_plan=grid_plan(tile_width, tile_height, overlap),
    )

    result = compare_arrays(load_image(str(untiled_path)), load_image(str(tiled_path)))
    assert result.within_tolerance(), (
        f"tile {tile_width}x{tile_height} overlap {overlap}: "
        f"{result.differing_pixel_fraction * 100:.3f}% differing, "
        f"mean deviation {result.mean_abs_deviation:.4f}"
    )


def test_tile_plan_none_is_identical_to_explicit_untiled(scan_dir, tmp_path):
    from os3stack.tiling import UNTILED

    batches = find_image_batches(scan_dir)
    batch = batches[0]
    transforms = _identity_transforms(batch.stack_size)

    default_path = tmp_path / "default.jpg"
    explicit_path = tmp_path / "explicit.jpg"
    stack_batch(batch, transforms, str(default_path))
    stack_batch(batch, transforms, str(explicit_path), tile_plan=UNTILED)

    assert np.array_equal(load_image(str(default_path)), load_image(str(explicit_path)))


def test_tiled_stack_batch_exactly_matches_untiled_when_size_is_multiple_of_4(scan_dir, tmp_path):
    """The real-photo test that caught the original tiling bug (ROADMAP.md's
    Step 2 entry): with dimensions divisible by 4, tiled and untiled should
    be bit-for-bit identical, not just within Step 2's tolerance."""
    batches = find_image_batches(scan_dir)  # fixture image size is 256x256
    batch = batches[0]
    calibration = calibrate([batch])

    untiled_path = tmp_path / "untiled.jpg"
    tiled_path = tmp_path / "tiled.jpg"
    stack_batch(batch, calibration.transforms, str(untiled_path))
    stack_batch(batch, calibration.transforms, str(tiled_path), tile_plan=grid_plan(64, 64, 16))

    assert np.array_equal(load_image(str(untiled_path)), load_image(str(tiled_path)))


def test_tiled_stack_batch_is_exact_even_when_image_size_is_not_a_multiple_of_4(tmp_path):
    """The full-resolution-slicing design (see os3stack/stack.py's module
    docstring) doesn't depend on the image size dividing evenly by 4 the way
    a low-res-slice-then-upsize design would — tile/untiled must still match
    exactly for an awkward size like 258x258 (unlike the 256x256 fixture,
    which wouldn't have caught a regression back to that other design)."""
    from _synthetic import blur, make_checkerboard
    from os3stack.batches import Batch, StackImage
    from os3stack.imageio import save_image

    size = 258  # not a multiple of 4
    base = make_checkerboard(size, size, square=32, seed=0)
    images = []
    for step, ksize in enumerate((9, 1, 9)):
        path = tmp_path / f"scan00_000_fs{step:02d}.jpg"
        save_image(str(path), blur(base, ksize), quality=95)
        images.append(StackImage(focus_step=step, path=path))
    batch = Batch(project_name="P", scan_index=0, position=0, images=tuple(images))
    calibration = calibrate([batch])

    untiled_path = tmp_path / "untiled.jpg"
    tiled_path = tmp_path / "tiled.jpg"
    stack_batch(batch, calibration.transforms, str(untiled_path))
    stack_batch(batch, calibration.transforms, str(tiled_path), tile_plan=grid_plan(64, 64, 16))

    assert np.array_equal(load_image(str(untiled_path)), load_image(str(tiled_path)))
