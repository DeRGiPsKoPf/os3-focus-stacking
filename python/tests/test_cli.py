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
