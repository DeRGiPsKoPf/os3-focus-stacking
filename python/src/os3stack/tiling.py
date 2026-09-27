"""Tile geometry for tiled merging (Step 2).

compute-interface.md §3.4: the output image is split into *cores* of
`tile_width` x `tile_height` starting at (0, 0), with the last row/column
clipped to the image. Each tile is processed as its core expanded by
`overlap` on every side (clipped to the image) — that expanded region is the
tile's *processing rect* — and only the core is written to the result.
`tile_width`, `tile_height` and `overlap` must be multiples of 4 (matching
the focus map's 1/4-scale downscale/upscale, `os3stack.core.DOWNSCALE`), and
`overlap` must be at least 16.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    """A rectangle in image pixel coordinates. `x1`/`y1` are exclusive."""

    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0


@dataclass(frozen=True)
class Tile:
    core: Rect
    proc: Rect  # core expanded by `overlap` on every side, clipped to the image


@dataclass(frozen=True)
class TilePlan:
    """compute-interface.ts's `TilePlan`. Construct via `UNTILED` or `grid_plan()`."""

    kind: str  # 'untiled' | 'grid'
    tile_width: int = 0
    tile_height: int = 0
    overlap: int = 0


#: The whole image is processed as a single tile.
UNTILED = TilePlan(kind="untiled")


def grid_plan(tile_width: int, tile_height: int, overlap: int) -> TilePlan:
    """A `grid` tile plan, validated per compute-interface.md §3.4.

    Raises ValueError if `tile_width`, `tile_height` or `overlap` isn't a
    multiple of 4, or `overlap` is below 16.
    """
    for name, value in (
        ("tile_width", tile_width), ("tile_height", tile_height), ("overlap", overlap),
    ):
        if value % 4 != 0:
            raise ValueError(f"{name} must be a multiple of 4, got {value}")
    if tile_width <= 0 or tile_height <= 0:
        raise ValueError("tile_width and tile_height must be positive")
    if overlap < 16:
        raise ValueError(f"overlap must be at least 16, got {overlap}")

    return TilePlan(kind="grid", tile_width=tile_width, tile_height=tile_height, overlap=overlap)


def compute_tiles(width: int, height: int, plan: TilePlan) -> list[Tile]:
    """Split a `width` x `height` image into tiles per `plan`.

    For `plan.kind == "untiled"` this is a single tile covering the whole
    image, with `core == proc` — the same shape a grid tile has, so callers
    (`os3stack.stack.stack_batch`) don't need a separate untiled code path.
    """
    if plan.kind == "untiled":
        full = Rect(0, 0, width, height)
        return [Tile(core=full, proc=full)]

    if plan.kind != "grid":
        raise ValueError(f"Unknown tile plan kind: {plan.kind!r}")

    tiles: list[Tile] = []
    y = 0
    while y < height:
        core_y1 = min(y + plan.tile_height, height)
        x = 0
        while x < width:
            core_x1 = min(x + plan.tile_width, width)
            core = Rect(x, y, core_x1, core_y1)
            proc = Rect(
                max(0, core.x0 - plan.overlap),
                max(0, core.y0 - plan.overlap),
                min(width, core.x1 + plan.overlap),
                min(height, core.y1 + plan.overlap),
            )
            tiles.append(Tile(core=core, proc=proc))
            x += plan.tile_width
        y += plan.tile_height

    return tiles
