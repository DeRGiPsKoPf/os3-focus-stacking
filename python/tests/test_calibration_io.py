import json

import numpy as np
import pytest

from os3stack.calibration_io import load_calibration_transforms


def test_loads_os3_minimal_format(tmp_path):
    # OS3's own calibration_scanXX.json only has these three fields.
    path = tmp_path / "calibration_scan00.json"
    path.write_text(json.dumps({
        "project": "MyProject",
        "scan_index": 0,
        "transforms": [
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            [[1.0, 0.02, 1.5], [-0.01, 1.0, -0.5]],
        ],
    }), encoding="utf-8")

    transforms = load_calibration_transforms(str(path))

    assert len(transforms) == 2
    assert transforms[0].shape == (2, 3)
    assert transforms[0].dtype == np.float32
    assert np.array_equal(transforms[0], np.eye(2, 3, dtype=np.float32))
    assert np.allclose(transforms[1], [[1.0, 0.02, 1.5], [-0.01, 1.0, -0.5]])


def test_loads_our_own_superset_format(tmp_path):
    path = tmp_path / "calibration_scan00.json"
    path.write_text(json.dumps({
        "project": "MyProject",
        "scan_index": 0,
        "transforms": [[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]],
        "formatVersion": 1,
        "referenceStep": 0,
        "stackSize": 1,
        "imageWidth": 256,
        "imageHeight": 256,
        "policy": {"kind": "spread", "batchCount": 1},
        "sourcePositions": [0],
        "failures": [],
        "algorithm": {"name": "os3-ecc-affine", "os3Version": "0.13.0", "downscale": 0.25},
        "createdAt": "2026-09-27T00:00:00+00:00",
    }), encoding="utf-8")

    transforms = load_calibration_transforms(str(path))

    assert len(transforms) == 1


def test_missing_transforms_field_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"project": "P", "scan_index": 0}), encoding="utf-8")

    with pytest.raises(ValueError, match="transforms"):
        load_calibration_transforms(str(path))


def test_wrong_matrix_shape_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({
        "project": "P", "scan_index": 0,
        "transforms": [[[1.0, 0.0], [0.0, 1.0]]],  # 2x2, not 2x3
    }), encoding="utf-8")

    with pytest.raises(ValueError, match=r"\(2, 3\)"):
        load_calibration_transforms(str(path))
