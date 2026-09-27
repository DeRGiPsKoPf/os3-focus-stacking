"""Synthetic scan fixtures. No real camera images are stored in this repo —
running the CLI on a real scan and inspecting the result is Step 1's actual
(manual) test criterion; these fixtures only exercise the code paths."""

from __future__ import annotations

import pytest

from _synthetic import write_scan


@pytest.fixture
def scan_dir(tmp_path):
    """`<tmp>/MyProject/scan00/` with 2 complete 3-image batches (positions 0, 1)."""
    scan_path = tmp_path / "MyProject" / "scan00"
    write_scan(scan_path)
    return scan_path
