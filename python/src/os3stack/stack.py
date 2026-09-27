"""Merging: warp -> Laplacian^2 sharpness -> per-pixel maximum selection.

Ported from OS3's ``FocusStacker.stack`` (v0.13.0). See
compute-interface.md §3.3 for the normative description, and §3.4 for
tiling (Step 2): the same computation as the untiled path, just restricted
to each tile's processing rect (core + overlap), with only the core written
back to the result. Passing no `tile_plan` (or ``tiling.UNTILED``) processes
the whole image as one tile, producing identical output to the pre-tiling
version of this function.

Crucially, each source's *low-res* focus energy (`compute_focus_energy_lowres`)
is computed once for the whole image and then sliced+upsized per tile —
never recomputed from a tile's own cropped pixels. See that function's
docstring for why: independently downscaling a crop disagrees with the
untiled result almost everywhere in the tile, not just near its edges,
which defeated the purpose of tiling until this was caught on a real photo
(a checkerboard-based synthetic test didn't expose it — see ROADMAP.md's
Step 2 entry).

Not memory-optimized: unlike OS3's own single-pass loop (one warped image
in memory at a time) this pre-warps every non-reference image up front, so
every tile can reuse them without re-warping. That's a deliberate trade-off
for a correctness benchmark, not the production memory profile — see
ROADMAP.md's measured-values table for what OS3's approach costs.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import cv2
import numpy as np

from os3stack.batches import Batch
from os3stack.core import DOWNSCALE, apply_transform, compute_focus_energy_lowres
from os3stack.imageio import DEFAULT_JPEG_QUALITY, load_image, save_image
from os3stack.tiling import UNTILED, Rect, TilePlan, compute_tiles


def _focus_map_for_rect(energy_lowres: np.ndarray, rect: Rect, downscale: float) -> np.ndarray:
    """Slice the region of a whole-image low-res energy map corresponding to
    `rect` (a full-resolution rect whose bounds are multiples of 1/downscale,
    guaranteed by tiling.grid_plan's validation) and upsize it to `rect`'s
    own full-resolution size — the tiled equivalent of what
    `compute_focus_map` does for a whole image in one step."""
    lr_x0 = round(rect.x0 * downscale)
    lr_y0 = round(rect.y0 * downscale)
    lr_x1 = round(rect.x1 * downscale)
    lr_y1 = round(rect.y1 * downscale)
    sub = energy_lowres[lr_y0:lr_y1, lr_x0:lr_x1]
    return cv2.resize(sub, (rect.width, rect.height))


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
            the whole image at once. Defaults to untiled.
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

    if tile_plan is not None and tile_plan.kind == "grid" and (w % 4 != 0 or h % 4 != 0):
        warnings.warn(
            f"Image size {w}x{h} isn't a multiple of 4 in both dimensions; the global "
            f"downscale ratio for the focus map (int(size*{downscale}) / size) then isn't "
            f"exactly {downscale}, so tiled output can disagree with the untiled result "
            f"well beyond the usual overlap margin, not just near tile edges (compute-"
            f"interface.md §3.4). Common camera sensor resolutions are unaffected "
            f"(e.g. 4656x3496).",
            stacklevel=2,
        )

    result = ref_img.copy()
    tiles = compute_tiles(w, h, tile_plan or UNTILED)

    # Low-res focus energy, computed once per image (cheap: 1/16 the
    # pixels), then sliced+upsized per tile below — never recomputed from a
    # tile's own cropped pixels (see this module's docstring and
    # _focus_map_for_rect).
    ref_energy_lowres = compute_focus_energy_lowres(ref_img, downscale)
    aligned_energy_lowres = {
        step: compute_focus_energy_lowres(aligned_by_step[step], downscale)
        for step in aligned_by_step
    }

    for tile in tiles:
        px0, py0, px1, py1 = tile.proc.x0, tile.proc.y0, tile.proc.x1, tile.proc.y1
        cx0, cy0, cx1, cy1 = tile.core.x0, tile.core.y0, tile.core.x1, tile.core.y1

        ref_sub = ref_img[py0:py1, px0:px1]
        best_focus_sub = _focus_map_for_rect(ref_energy_lowres, tile.proc, downscale)
        result_sub = ref_sub.copy()

        for step in range(n):
            if step == reference_step:
                continue

            aligned_sub = aligned_by_step[step][py0:py1, px0:px1]
            focus_sub = _focus_map_for_rect(aligned_energy_lowres[step], tile.proc, downscale)

            better = focus_sub > best_focus_sub  # strict: ties keep the earlier value
            result_sub = np.where(better[..., np.newaxis], aligned_sub, result_sub)
            best_focus_sub = np.where(better, focus_sub, best_focus_sub)

        # Write only the core back, at its offset within the processing rect.
        # Any disagreement with the untiled result — ordinary interpolation
        # boundary effects from upsizing a cropped low-res slice — is
        # confined to a margin near the *processing rect's* edges, which
        # `overlap` pushes outside the core before this line ever runs.
        oy0, ox0 = cy0 - py0, cx0 - px0
        oy1, ox1 = oy0 + (cy1 - cy0), ox0 + (cx1 - cx0)
        result[cy0:cy1, cx0:cx1] = result_sub[oy0:oy1, ox0:ox1]

    save_image(output_path, result, jpeg_quality)
    return StackResult(position=batch.position, width=w, height=h, output_path=output_path)
