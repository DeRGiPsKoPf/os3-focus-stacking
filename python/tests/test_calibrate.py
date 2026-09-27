import numpy as np

from os3stack.batches import find_image_batches
from os3stack.calibrate import calibrate, spread_batches, to_calibration_record


def test_calibrate_single_batch(scan_dir):
    batches = find_image_batches(scan_dir)
    result = calibrate([batches[0]])

    assert result.stack_size == 3
    assert result.reference_step == 1
    assert len(result.transforms) == 3
    assert result.image_width == 256
    assert result.image_height == 256
    assert len(result.per_batch_transforms) == 1

    identity = np.eye(2, 3, dtype=np.float32)
    assert np.array_equal(result.transforms[result.reference_step], identity)
    # Same underlying content at every step (only blur differs, no shift):
    # alignment should converge close to identity for the outer steps too.
    for step in (0, 2):
        assert np.allclose(result.transforms[step], identity, atol=1.0)


def test_calibrate_multi_batch_averages_transforms(scan_dir):
    batches = find_image_batches(scan_dir)
    result = calibrate([batches[0], batches[1]])

    assert len(result.per_batch_transforms) == 2
    for step in range(result.stack_size):
        expected = np.mean(
            [result.per_batch_transforms[0][step], result.per_batch_transforms[1][step]],
            axis=0,
        ).astype(np.float32)
        assert np.array_equal(result.transforms[step], expected)


def test_calibrate_rejects_mismatched_stack_sizes(scan_dir):
    from os3stack.batches import Batch, StackImage

    batches = find_image_batches(scan_dir)
    short_batch = Batch(
        project_name="MyProject",
        scan_index=0,
        position=99,
        images=batches[0].images[:2],
    )

    try:
        calibrate([batches[0], short_batch])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_spread_batches_selects_evenly(scan_dir):
    from os3stack.batches import Batch

    all_batches = {
        i: Batch(project_name="P", scan_index=0, position=i, images=())
        for i in range(10)
    }

    selected = spread_batches(all_batches, 3)

    assert [b.position for b in selected] == [0, 4, 9]


def test_spread_batches_caps_at_available_count(scan_dir):
    batches = find_image_batches(scan_dir)  # only 2 batches available
    selected = spread_batches(batches, 3)
    assert len(selected) == 2


def test_to_calibration_record_shape(scan_dir):
    batches = find_image_batches(scan_dir)
    result = calibrate([batches[0]])

    record = to_calibration_record(
        result,
        project_name="MyProject",
        scan_index=0,
        source_positions=[0],
        policy={"kind": "spread", "batchCount": 1},
    )

    assert record["project"] == "MyProject"
    assert record["scan_index"] == 0
    assert record["formatVersion"] == 1
    assert record["referenceStep"] == 1
    assert record["stackSize"] == 3
    assert record["imageWidth"] == 256
    assert record["imageHeight"] == 256
    assert record["sourcePositions"] == [0]
    assert record["policy"] == {"kind": "spread", "batchCount": 1}
    assert record["algorithm"]["name"] == "os3-ecc-affine"
    assert len(record["transforms"]) == 3
    assert record["transforms"][1] == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert isinstance(record["createdAt"], str)
