import json

from os3stack.cli import main


def test_stack_command_end_to_end(scan_dir, tmp_path):
    output_dir = tmp_path / "out"

    exit_code = main([
        "stack", str(scan_dir),
        "--output-dir", str(output_dir),
        "--calibration-batches", "2",
    ])

    assert exit_code == 0
    assert (output_dir / "calibration_scan00.json").exists()
    assert (output_dir / "stacked_scan00_000.jpg").exists()
    assert (output_dir / "stacked_scan00_001.jpg").exists()

    record = json.loads((output_dir / "calibration_scan00.json").read_text(encoding="utf-8"))
    assert record["project"] == "MyProject"
    assert record["scan_index"] == 0
    assert sorted(record["sourcePositions"]) == [0, 1]
    assert record["policy"] == {"kind": "spread", "batchCount": 2}


def test_stack_command_reports_error_on_empty_dir(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    exit_code = main(["stack", str(empty_dir)])

    assert exit_code == 1


def test_stack_command_reports_error_on_missing_dir(tmp_path):
    exit_code = main(["stack", str(tmp_path / "does-not-exist")])
    assert exit_code == 1


def test_stack_command_with_external_calibration_skips_writing_one(scan_dir, tmp_path):
    identity_calibration = tmp_path / "external_calibration.json"
    identity_calibration.write_text(json.dumps({
        "project": "MyProject",
        "scan_index": 0,
        "transforms": [
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        ],
    }), encoding="utf-8")
    output_dir = tmp_path / "out"

    exit_code = main([
        "stack", str(scan_dir),
        "--output-dir", str(output_dir),
        "--calibration", str(identity_calibration),
    ])

    assert exit_code == 0
    assert (output_dir / "stacked_scan00_000.jpg").exists()
    assert (output_dir / "stacked_scan00_001.jpg").exists()
    # No calibration was computed, so none should be written.
    assert not (output_dir / "calibration_scan00.json").exists()


def test_stack_command_rejects_calibration_with_wrong_stack_size(scan_dir, tmp_path):
    wrong_size_calibration = tmp_path / "wrong.json"
    wrong_size_calibration.write_text(json.dumps({
        "project": "MyProject", "scan_index": 0,
        "transforms": [[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]],  # 1, but stack size is 3
    }), encoding="utf-8")

    exit_code = main([
        "stack", str(scan_dir),
        "--output-dir", str(tmp_path / "out"),
        "--calibration", str(wrong_size_calibration),
    ])

    assert exit_code == 1


def test_compare_command_pass_and_fail(scan_dir, tmp_path):
    from os3stack.batches import find_image_batches

    batches = find_image_batches(scan_dir)
    image_a = str(batches[0].images[0].path)  # blurred (fs00)
    image_b = str(batches[0].images[1].path)  # sharp (fs01) -- clearly different

    exit_code_same = main(["compare", image_a, image_a])
    exit_code_different = main(["compare", image_a, image_b])

    assert exit_code_same == 0
    assert exit_code_different == 1


def test_compare_command_reports_error_on_missing_file(tmp_path):
    exit_code = main(["compare", str(tmp_path / "a.jpg"), str(tmp_path / "b.jpg")])
    assert exit_code == 1


def test_stack_command_with_tiling(scan_dir, tmp_path):
    output_dir = tmp_path / "out"

    exit_code = main([
        "stack", str(scan_dir),
        "--output-dir", str(output_dir),
        "--tile-width", "64", "--tile-height", "64", "--tile-overlap", "16",
    ])

    assert exit_code == 0
    assert (output_dir / "stacked_scan00_000.jpg").exists()


def test_stack_command_rejects_partial_tile_args(scan_dir, tmp_path):
    exit_code = main([
        "stack", str(scan_dir),
        "--output-dir", str(tmp_path / "out"),
        "--tile-width", "64", "--tile-height", "64",
        # --tile-overlap missing
    ])

    assert exit_code == 1


def test_stack_command_rejects_invalid_tile_size(scan_dir, tmp_path):
    exit_code = main([
        "stack", str(scan_dir),
        "--output-dir", str(tmp_path / "out"),
        "--tile-width", "63", "--tile-height", "64", "--tile-overlap", "16",
    ])

    assert exit_code == 1
