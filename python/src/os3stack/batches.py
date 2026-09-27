"""Discover focus-stack batches in an OS3 scan directory.

Ported from OS3's ``find_image_batches`` (``openscan_firmware/utils/photos/
stacking.py``, v0.13.0), extended with the project/scan metadata and stack
size validation described in compute-interface.md §4.1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: scan{XX}_{NNN}_fs{SS}.jpg — XX = scan index, NNN = position (OS3's
#: original path index, not capture order), SS = 0-based focus step.
_FILENAME_PATTERN = re.compile(r"scan(\d+)_(\d+)_fs(\d+)\.jpg$")


@dataclass(frozen=True)
class StackImage:
    focus_step: int
    path: Path


@dataclass(frozen=True)
class Batch:
    """All photos of one scan position. compute-interface.ts: `Batch`."""

    project_name: str
    scan_index: int
    position: int
    images: tuple[StackImage, ...]  # sorted by focus_step, 0..stack_size-1

    @property
    def stack_size(self) -> int:
        return len(self.images)

    @property
    def image_paths(self) -> list[str]:
        """Paths in ascending focus-step order, as OS3's `stack()` expects."""
        return [str(img.path) for img in self.images]


def infer_project_and_scan(scan_dir: Path) -> tuple[str, int]:
    """Infer (project_name, scan_index) from a path like `.../MyProject/scan00`.

    Falls back to scan_index 0 and the directory's own name as the project
    name if `scan_dir` isn't named `scanNN` (e.g. when pointed at an
    arbitrary folder of images for testing).
    """
    scan_dir = Path(scan_dir)
    match = re.fullmatch(r"scan(\d+)", scan_dir.name)
    if match:
        return scan_dir.parent.name or scan_dir.name, int(match.group(1))
    return scan_dir.name, 0


def find_image_batches(
    scan_dir: str | Path,
    stack_size: int | None = None,
    project_name: str | None = None,
    scan_index: int | None = None,
) -> dict[int, Batch]:
    """Find and group images into complete focus-stack batches.

    Args:
        scan_dir: Directory containing scan images (non-recursive, like OS3).
        stack_size: Expected images per batch. If None, auto-detected from
            the first position that has any matching files (OS3's behaviour).
        project_name, scan_index: Override the values inferred from `scan_dir`.

    Returns:
        Dict mapping position -> Batch, for positions with exactly
        `stack_size` images. Incomplete positions are silently dropped, as in
        OS3 — a scan still capturing a position simply doesn't yield it yet.
    """
    scan_dir = Path(scan_dir)
    inferred_project, inferred_scan_index = infer_project_and_scan(scan_dir)
    project_name = project_name if project_name is not None else inferred_project
    scan_index = scan_index if scan_index is not None else inferred_scan_index

    by_position: dict[int, list[tuple[int, Path]]] = {}
    for path in sorted(scan_dir.glob("*.jpg")):
        match = _FILENAME_PATTERN.match(path.name)
        if not match:
            continue
        position = int(match.group(2))
        focus_step = int(match.group(3))
        by_position.setdefault(position, []).append((focus_step, path))

    if stack_size is None and by_position:
        first = next(iter(by_position.values()))
        stack_size = len(first)

    result: dict[int, Batch] = {}
    for position, entries in by_position.items():
        entries.sort(key=lambda e: e[0])
        if stack_size is not None and len(entries) != stack_size:
            continue
        focus_steps = [fs for fs, _ in entries]
        if focus_steps != list(range(len(entries))):
            # Gap or duplicate fsNN (e.g. a retried capture) — not a clean
            # batch spec §3.1 requires images[i].focusStep == i.
            continue
        images = tuple(StackImage(focus_step=fs, path=p) for fs, p in entries)
        result[position] = Batch(
            project_name=project_name,
            scan_index=scan_index,
            position=position,
            images=images,
        )

    return result
