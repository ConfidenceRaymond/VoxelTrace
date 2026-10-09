"""QC render of ONE supplied lesion segment for human review (deterministic; display only).

On the PET grid, cropped around the segment's bounding box: PET axial, CT axial and fused
PET/CT at the slice with most segment voxels, neighbouring axial slices, coronal and sagittal
planes through the centroid. The segment contour is magenta; SUVmax is a yellow crosshair and
the SUVpeak sphere centre a green circle. CT (if any) is resampled onto the PET grid for
display only. The banner states the source type and that the mask is NOT reviewed evidence
until a human accepts it.
"""

from __future__ import annotations

import numpy as np

from voxeltrace.visualization.overlays import (
    GREEN,
    MAGENTA,
    YELLOW,
    circle,
    contour,
    crosshair,
    paint,
)
from voxeltrace.visualization.render import add_footer, colorize, compose_grid, png_bytes

MARGIN = 8


def _up(a: np.ndarray, up: int) -> np.ndarray:
    return (
        np.kron(a, np.ones((up, up, 1), dtype=np.uint8))
        if a.ndim == 3
        else np.kron(a, np.ones((up, up), dtype=a.dtype))
    )


def _tile(img2d, mask2d, lo, hi, cmap, up, ct2d=None, marks=()):
    if ct2d is not None:
        base = colorize(ct2d, -150.0, 350.0, "gray").astype(np.float64)
        hot = colorize(img2d, lo, hi, "hot").astype(np.float64)
        a = (np.clip((img2d - lo) / max(hi - lo, 1e-9), 0, 1) * 0.65)[..., None]
        rgb = np.round(base * (1 - a) + hot * a).astype(np.uint8)
    else:
        rgb = colorize(img2d, lo, hi, cmap)
    big = _up(rgb, up)
    m = _up(mask2d.astype(np.uint8), up) > 0
    edge = contour(m)
    edge[1:, :] |= edge[:-1, :]
    big = paint(big, edge, MAGENTA)
    for kind, (r, c) in marks:
        x, y = int(c * up + up // 2), int(r * up + up // 2)
        if kind == "max":
            big = paint(big, crosshair(big.shape[:2], x, y, arm=2 * up), YELLOW)
        else:
            big = paint(big, circle(big.shape[:2], x, y, r=1.5 * up), GREEN)
    return big


def render_lesion_qc(
    pet: np.ndarray,
    mask: np.ndarray,
    *,
    title: str,
    unit: str = "SUV",
    ct_on_pet: np.ndarray | None = None,
    suvmax_kji: tuple[int, int, int] | None = None,
    suvpeak_kji: tuple[int, int, int] | None = None,
    footer: str = "",
) -> bytes:
    m = mask.astype(bool)
    if not m.any():
        raise ValueError("empty segment: nothing to render")
    idx = np.argwhere(m)
    (k0, j0, i0), (k1, j1, i1) = idx.min(0), idx.max(0)
    ks = np.bincount(idx[:, 0])
    k = int(np.argmax(ks))
    if suvmax_kji is not None and m[suvmax_kji[0]].any():
        k = int(suvmax_kji[0])  # centre the review on the hottest voxel's slice
    jc, ic = (int(round(v)) for v in idx[:, 1:].mean(0))
    J0, J1 = max(0, j0 - MARGIN), min(pet.shape[1], j1 + MARGIN + 1)
    I0, I1 = max(0, i0 - MARGIN), min(pet.shape[2], i1 + MARGIN + 1)
    K0, K1 = max(0, k0 - MARGIN), min(pet.shape[0], k1 + MARGIN + 1)
    lo, hi = 0.0, float(np.percentile(pet[K0:K1, J0:J1, I0:I1], 99.5)) or 1.0
    up = max(2, 240 // max(J1 - J0, I1 - I0, K1 - K0))

    def ax(vol, kk):
        return vol[kk, J0:J1, I0:I1]

    def marks_ax(kk):
        out = []
        if suvmax_kji and suvmax_kji[0] == kk:
            out.append(("max", (suvmax_kji[1] - J0, suvmax_kji[2] - I0)))
        if suvpeak_kji and suvpeak_kji[0] == kk:
            out.append(("peak", (suvpeak_kji[1] - J0, suvpeak_kji[2] - I0)))
        return out

    main = [
        (
            f"PET axial k={k} ({unit} 0-{hi:.2g})",
            _tile(ax(pet, k), ax(m, k), lo, hi, "gray_inverted", up, marks=marks_ax(k)),
        )
    ]
    if ct_on_pet is not None:
        main.append(
            ("CT axial (HU -150..350)", _tile(ax(ct_on_pet, k), ax(m, k), -150, 350, "gray", up))
        )
        main.append(
            (
                "Fused PET/CT axial",
                _tile(
                    ax(pet, k),
                    ax(m, k),
                    lo,
                    hi,
                    "hot",
                    up,
                    ct2d=ax(ct_on_pet, k),
                    marks=marks_ax(k),
                ),
            )
        )
    neigh = []
    for kk in (k - 2, k - 1, k + 1, k + 2):
        if 0 <= kk < pet.shape[0]:
            ct2 = ax(ct_on_pet, kk) if ct_on_pet is not None else None
            neigh.append((f"axial k={kk}" + ("" if ax(m, kk).any() else " (no mask)"),
                          _tile(ax(pet, kk), ax(m, kk), lo, hi, "gray_inverted" if ct2 is None else "hot", up, ct2d=ct2, marks=marks_ax(kk))))  # fmt: skip
    cor = (pet[K0:K1, jc, I0:I1][::-1], m[K0:K1, jc, I0:I1][::-1])
    sag = (pet[K0:K1, J0:J1, ic][::-1], m[K0:K1, J0:J1, ic][::-1])
    context = [
        (f"PET coronal j={jc}", _tile(cor[0], cor[1], lo, hi, "gray_inverted", up)),
        (f"PET sagittal i={ic}", _tile(sag[0], sag[1], lo, hi, "gray_inverted", up)),
    ]
    rgb = compose_grid([main, neigh, context] if neigh else [main, context], title=title)
    lines = [footer] if footer else []
    lines.append("magenta = supplied mask; yellow + = SUVmax; green o = SUVpeak centre")
    lines.append("NOT reviewed evidence until a human ACCEPTs this exact mask")
    return png_bytes(add_footer(rgb, lines, mm_per_px=1.0))
