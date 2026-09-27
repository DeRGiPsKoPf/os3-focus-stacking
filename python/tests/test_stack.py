import numpy as np

from _synthetic import SHARPEST_STEP
from os3stack.batches import Batch, find_image_batches
from os3stack.imageio import load_image
from os3stack.stack import stack_batch


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
