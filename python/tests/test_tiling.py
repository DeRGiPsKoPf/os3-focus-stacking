import pytest

from os3stack.tiling import UNTILED, Rect, compute_tiles, grid_plan


def test_untiled_plan_is_one_tile_covering_the_whole_image():
    tiles = compute_tiles(100, 60, UNTILED)

    assert len(tiles) == 1
    assert tiles[0].core == Rect(0, 0, 100, 60)
    assert tiles[0].proc == Rect(0, 0, 100, 60)


def test_grid_plan_rejects_non_multiples_of_4():
    with pytest.raises(ValueError, match="tile_width"):
        grid_plan(tile_width=99, tile_height=64, overlap=16)
    with pytest.raises(ValueError, match="tile_height"):
        grid_plan(tile_width=64, tile_height=63, overlap=16)
    with pytest.raises(ValueError, match="overlap"):
        grid_plan(tile_width=64, tile_height=64, overlap=17)


def test_grid_plan_rejects_overlap_below_16():
    with pytest.raises(ValueError, match="overlap"):
        grid_plan(tile_width=64, tile_height=64, overlap=12)


def test_grid_plan_rejects_non_positive_tile_size():
    with pytest.raises(ValueError):
        grid_plan(tile_width=0, tile_height=64, overlap=16)


def test_grid_tiling_evenly_divisible_image():
    # 256x256 in 64x64 cores -> a clean 4x4 grid, no clipped tiles.
    plan = grid_plan(tile_width=64, tile_height=64, overlap=16)
    tiles = compute_tiles(256, 256, plan)

    assert len(tiles) == 16
    cores = {(t.core.x0, t.core.y0, t.core.x1, t.core.y1) for t in tiles}
    assert cores == {
        (x, y, x + 64, y + 64) for x in (0, 64, 128, 192) for y in (0, 64, 128, 192)
    }
    # Every pixel is covered by exactly one tile's core.
    total_core_area = sum(t.core.width * t.core.height for t in tiles)
    assert total_core_area == 256 * 256


def test_grid_tiling_clips_the_last_row_and_column():
    # 100x100 in 64x64 cores -> tiles at x/y in {0, 64}, with the second
    # column/row clipped to width/height 36 instead of 64.
    plan = grid_plan(tile_width=64, tile_height=64, overlap=16)
    tiles = compute_tiles(100, 100, plan)

    assert len(tiles) == 4
    cores = {(t.core.x0, t.core.y0, t.core.x1, t.core.y1) for t in tiles}
    assert cores == {
        (0, 0, 64, 64),
        (64, 0, 100, 64),
        (0, 64, 64, 100),
        (64, 64, 100, 100),
    }
    total_core_area = sum(t.core.width * t.core.height for t in tiles)
    assert total_core_area == 100 * 100


def test_processing_rect_expands_by_overlap_and_clips_to_image():
    plan = grid_plan(tile_width=64, tile_height=64, overlap=16)
    tiles = compute_tiles(100, 100, plan)
    by_core_origin = {(t.core.x0, t.core.y0): t for t in tiles}

    # Interior side of the top-left tile clips against nothing (touches 0),
    # but its bottom/right side (not at an image edge) gets the full overlap.
    top_left = by_core_origin[(0, 0)]
    assert top_left.proc == Rect(0, 0, 64 + 16, 64 + 16)

    # The bottom-right tile's core touches the image edge on two sides
    # (clipped to 100), so its processing rect can't extend past 100 there,
    # but does extend by the full overlap on its other two sides.
    bottom_right = by_core_origin[(64, 64)]
    assert bottom_right.proc == Rect(64 - 16, 64 - 16, 100, 100)
