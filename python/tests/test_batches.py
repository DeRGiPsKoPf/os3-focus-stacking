from os3stack.batches import find_image_batches, infer_project_and_scan


def test_infer_project_and_scan_from_scanNN_dir(scan_dir):
    project_name, scan_index = infer_project_and_scan(scan_dir)
    assert project_name == "MyProject"
    assert scan_index == 0


def test_infer_project_and_scan_falls_back_for_arbitrary_dir(tmp_path):
    arbitrary = tmp_path / "some_photos"
    arbitrary.mkdir()
    project_name, scan_index = infer_project_and_scan(arbitrary)
    assert project_name == "some_photos"
    assert scan_index == 0


def test_finds_complete_batches(scan_dir):
    batches = find_image_batches(scan_dir)

    assert set(batches.keys()) == {0, 1}
    for position, batch in batches.items():
        assert batch.project_name == "MyProject"
        assert batch.scan_index == 0
        assert batch.position == position
        assert batch.stack_size == 3
        assert [img.focus_step for img in batch.images] == [0, 1, 2]
        assert batch.image_paths == [str(img.path) for img in batch.images]


def test_incomplete_batch_is_dropped(scan_dir):
    # Position 2 only gets 2 of 3 images.
    (scan_dir / "scan00_002_fs00.jpg").write_bytes(b"not a real jpeg, content doesn't matter here")
    (scan_dir / "scan00_002_fs01.jpg").write_bytes(b"not a real jpeg, content doesn't matter here")

    batches = find_image_batches(scan_dir)

    assert 2 not in batches
    assert set(batches.keys()) == {0, 1}


def test_batch_with_gap_in_focus_steps_is_dropped(scan_dir):
    # Position 3 has fs00 and fs02 but not fs01 -- same count as a real batch
    # (stack_size auto-detected as 3), but the step sequence has a gap.
    (scan_dir / "scan00_003_fs00.jpg").write_bytes(b"x")
    (scan_dir / "scan00_003_fs02.jpg").write_bytes(b"x")
    (scan_dir / "scan00_003_fs03.jpg").write_bytes(b"x")

    batches = find_image_batches(scan_dir)

    assert 3 not in batches


def test_explicit_stack_size_filters_out_other_sizes(scan_dir):
    batches = find_image_batches(scan_dir, stack_size=5)
    assert batches == {}


def test_non_matching_filenames_are_ignored(scan_dir):
    (scan_dir / "thumbnail.jpg").write_bytes(b"x")
    (scan_dir / "notes.txt").write_bytes(b"x")

    batches = find_image_batches(scan_dir)

    assert set(batches.keys()) == {0, 1}


def test_project_and_scan_index_overrides(scan_dir):
    batches = find_image_batches(scan_dir, project_name="Other", scan_index=7)
    batch = batches[0]
    assert batch.project_name == "Other"
    assert batch.scan_index == 7
