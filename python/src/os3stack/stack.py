"""Merging: warp -> Laplacian^2 sharpness -> per-pixel maximum selection.

Ported from OS3's ``FocusStacker.stack`` (v0.13.0). See
compute-interface.md §3.3 for the normative description, and §3.4 for
tiling (Step 2): the same computation as the untiled path, just restricted
to each tile's processing rect (core + overlap), with only the core written
back to the result. Passing no `tile_plan` (or ``tiling.UNTILED``) processes
the whole image as one tile, producing identical output to the pre-tiling
version of this function.

Each source's focus map (`compute_focus_map`, i.e. already resized back up
to full resolution) is computed once for the whole image; every tile then
just *slices* its processing rect out of that finished array. Slicing an
already-computed array can't disagree with itself, so this is exact for any
image size and any tile size/overlap — not just images whose width and
height happen to be multiples of 4 (an earlier version computed each source's
*low-res* energy once and resized a slice of it per tile instead, which
looked right but wasn't: resizing a crop uses a resampling ratio that only
matches the whole image's own resampling ratio when the image size divides
evenly by 1/downscale, so it was still exact-only-for-multiples-of-4, just a
narrower and sneakier version of the original per-tile-recompute bug below).

This costs one extra full-resolution float32 array per source image, which
this reference implementation can afford: it already holds every source's
full-resolution *aligned pixels* in memory at once (see the note below), so
one more same-sized array per source is a fraction more, not a change of
order of magnitude. A real memory- or texture-size-constrained backend
(Step 5's WebGPU, texture-limited to ~8192 px) can't afford a full-resolution
intermediate for every source and must genuinely tile the low-res-to-full-res
upsize — for that, see compute-interface.md §3.4's normative rule (compute
the low-res energy once, then slice-and-upsize the low-res slice per tile,
which is only exact when image dimensions are multiples of 4; achieving
exactness for arbitrary sizes there means padding to the next multiple of 4
before processing and cropping back afterward, the standard technique for
block-based image transforms).

The original bug this replaced: the very first tiling implementation
recomputed each tile's downscaled focus energy from that tile's own cropped
pixels (rather than from a shared whole-image array at all), which resamples
on a grid anchored to the tile's own size and disagreed with the untiled
result almost everywhere in the tile, not just near its edges. Caught on a
real photo (a checkerboard synthetic test didn't expose it) — see
ROADMAP.md's Step 2 entry for the numbers.

Not memory-optimized: unlike OS3's own single-pass loop (one warped image
in memory at a time) this pre-warps every non-reference image up front, so
every tile can reuse them without re-warping. That's a deliberate trade-off
for a correctness benchmark, not the production memory profile — see
ROADMAP.md's measured-values table for what OS3's approach costs.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from os3stack.batches import Batch
from os3stack.core import DOWNSCALE, apply_transform, compute_focus_map
from os3stack.imageio import DEFAULT_JPEG_QUALITY, load_image, save_image
from os3stack.tiling import UNTILED, TilePlan, compute_tiles


@dataclass(frozen=True)
class StackResult:
    """Subset of compute-interface.ts's `StackResult` relevant to this
    synchronous reference implementation."""

    position: int
    width: int
    height: int
    output_path: str


def stack_batch(
    batch: Batch,
    transforms: list[np.ndarray],
    output_path: str,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    downscale: float = DOWNSCALE,
    tile_plan: TilePlan | None = None,
) -> StackResult:
    """Merge one batch into a single all-in-focus image and write it as JPEG.

    Args:
        batch: The images to merge (`batch.images[i]` corresponds to focus
            step i).
        transforms: One 2x3 matrix per focus step (`transforms[i]` maps
            output pixels to source pixels for `batch.images[i]`), e.g. from
            `calibrate()`. Length must equal `batch.stack_size`.
        output_path: Where to write the merged JPEG (parent dirs created).
        jpeg_quality: 1..100 (OS3 default: 90).
        tile_plan: `tiling.grid_plan(...)` to merge tile-by-tile instead of
            the whole image at once. Defaults to untiled. Output is
            bit-for-bit identical to untiled regardless of image size (see
            this module's docstring).
    """
    n = batch.stack_size
    if len(transforms) != n:
        raise ValueError(
            f"Expected {n} transforms (one per focus step), got {len(transforms)}"
        )

    if n == 1:
        # Nothing to merge or tile: a single-image "stack" is just a
        # re-encode, exactly as in OS3.
        img = load_image(str(batch.images[0].path))
        save_image(output_path, img, jpeg_quality)
        h, w = img.shape[:2]
        return StackResult(position=batch.position, width=w, height=h, output_path=output_path)

    reference_step = n // 2
    ref_img = load_image(str(batch.images[reference_step].path))
    h, w = ref_img.shape[:2]

    # The reference frame needs no warp (its transform is the identity).
    aligned_by_step = {
        step: apply_transform(load_image(str(batch.images[step].path)), transforms[step])
        for step in range(n)
        if step != reference_step
    }

    # Full-resolution focus maps, computed once per image; every tile below
    # only slices these, never recomputes them (see module docstring).
    ref_focus_map = compute_focus_map(ref_img, downscale)
    aligned_focus_maps = {
        step: compute_focus_map(aligned_by_step[step], downscale)
        for step in aligned_by_step
    }

    result = ref_img.copy()
    tiles = compute_tiles(w, h, tile_plan or UNTILED)

    for tile in tiles:
        px0, py0, px1, py1 = tile.proc.x0, tile.proc.y0, tile.proc.x1, tile.proc.y1
        cx0, cy0, cx1, cy1 = tile.core.x0, tile.core.y0, tile.core.x1, tile.core.y1

        ref_sub = ref_img[py0:py1, px0:px1]
        best_focus_sub = ref_focus_map[py0:py1, px0:px1]
        result_sub = ref_sub.copy()

        for step in range(n):
            if step == reference_step:
                continue

            aligned_sub = aligned_by_step[step][py0:py1, px0:px1]
            focus_sub = aligned_focus_maps[step][py0:py1, px0:px1]

            better = focus_sub > best_focus_sub  # strict: ties keep the earlier value
            result_sub = np.where(better[..., np.newaxis], aligned_sub, result_sub)
            best_focus_sub = np.where(better, focus_sub, best_focus_sub)

        # Write only the core back, at its offset within the processing rect.
        oy0, ox0 = cy0 - py0, cx0 - px0
        oy1, ox1 = oy0 + (cy1 - cy0), ox0 + (cx1 - cx0)
        result[cy0:cy1, cx0:cx1] = result_sub[oy0:oy1, ox0:ox1]

    save_image(output_path, result, jpeg_quality)
    return StackResult(position=batch.position, width=w, height=h, output_path=output_path)
