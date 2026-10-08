"""QC render of a reference-region PROPOSAL for human review (deterministic).

Axial and coronal CT and PET planes through the proposal centre, on the proposer's working
grid. The outline is the contour of the proposal's own region mask on that grid. The banner
states that the region is an automatic proposal that requires review.
"""

from __future__ import annotations

import numpy as np

from voxeltrace.quant.reference_auto import ReferenceProposal, WorkGrid
from voxeltrace.visualization.overlays import GREEN, MAGENTA, contour, paint
from voxeltrace.visualization.render import add_footer, colorize, compose_grid, png_bytes

UPSCALE = 6
ZOOM_HALF_MM = 60.0


def region_mask_on_work(w: WorkGrid, p) -> np.ndarray:
    """Region mask on the working grid for anything with method / centre_patient_mm /
    diameter_mm / length_mm (a proposal, a spec or a review geometry)."""
    c = p.centre_patient_mm
    assert c is not None and p.diameter_mm is not None
    xg, yg, zg = w.x[None, None, :], w.y[None, :, None], w.z[:, None, None]
    r2 = (p.diameter_mm / 2) ** 2
    if p.method == "SPHERE_AT_SUPPLIED_CENTRE":
        return (xg - c[0]) ** 2 + (yg - c[1]) ** 2 + (zg - c[2]) ** 2 <= r2
    return ((xg - c[0]) ** 2 + (yg - c[1]) ** 2 <= r2) & (
        np.abs(zg - c[2]) <= (p.length_mm or 0) / 2
    )


def _thick(edge: np.ndarray) -> np.ndarray:
    out = edge.copy()
    out[1:, :] |= edge[:-1, :]
    out[:, 1:] |= edge[:, :-1]
    return out


def _tile(
    plane: np.ndarray, mask: np.ndarray, lo: float, hi: float, cmap: str, up: int = UPSCALE
) -> np.ndarray:
    big = np.kron(plane, np.ones((up, up)))
    mbig = np.kron(mask.astype(np.uint8), np.ones((up, up), np.uint8)) > 0
    rgb = colorize(big, lo, hi, cmap)
    return paint(rgb, _thick(contour(mbig)), GREEN if cmap == "gray" else MAGENTA)


def _crop(a: np.ndarray, r0: int, c0: int, half: int) -> np.ndarray:
    return a[max(r0 - half, 0) : r0 + half + 1, max(c0 - half, 0) : c0 + half + 1]


def render_proposal_qc(w: WorkGrid, p: ReferenceProposal, *, title: str) -> bytes:
    if p.status != "PROPOSED" or p.centre_patient_mm is None:
        raise ValueError("only PROPOSED regions can be rendered")
    m = region_mask_on_work(w, p)
    k, j, i = w.index_of(p.centre_patient_mm)
    h = int(round(ZOOM_HALF_MM / w.spacing))
    nk = w.hu.shape[0]
    kc = nk - 1 - k  # coronal planes are flipped so superior is up

    def views(vol: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return _crop(vol[k], j, i, h), _crop(vol[:, j, :][::-1], kc, i, h)

    ct_ax, ct_co = views(w.hu)
    m_ax, m_co = views(m)
    tiles = [
        ("CT axial (120 mm)", _tile(ct_ax, m_ax, -150.0, 350.0, "gray")),
        ("CT coronal (120 mm)", _tile(ct_co, m_co, -150.0, 350.0, "gray")),
    ]
    if w.suv is not None:
        pet_ax, pet_co = views(w.suv)
        tiles += [
            ("PET axial, SUV 0-5", _tile(pet_ax, m_ax, 0.0, 5.0, "gray_inverted")),
            ("PET coronal, SUV 0-5", _tile(pet_co, m_co, 0.0, 5.0, "gray_inverted")),
        ]
    tiles.append(
        (
            "CT coronal (location)",
            _tile(w.hu[:, j, :][::-1], m[:, j, :][::-1], -150.0, 350.0, "gray", up=2),
        )
    )
    sheet = compose_grid([tiles], title=title, tile=300)
    size = f"{p.diameter_mm:g} mm" + (f" x {p.length_mm:g} mm" if p.length_mm else "")
    return png_bytes(
        add_footer(
            sheet,
            [
                f"AUTOMATIC PROPOSAL ({p.algorithm_version}) - REQUIRES HUMAN REVIEW BEFORE USE",
                f"{p.region} {p.method} centre (LPS mm) {p.centre_patient_mm} size {size}",
                f"proposal_sha256 {p.sha256}",
                "RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS",
            ],
            mm_per_px=w.spacing / UPSCALE,
        )
    )


# --------------------------------------------------------------------------------------
# Review page panels (any region geometry: proposal, or a reviewer's moved candidate)
# --------------------------------------------------------------------------------------

PET_MAX_SUV = 5.0


def _fused(ct: np.ndarray, suv: np.ndarray) -> np.ndarray:
    """CT grey (-150..350 HU) with PET hot overlay (SUV 0..5, opacity rising with SUV)."""
    base = colorize(ct, -150.0, 350.0, "gray").astype(np.float64)
    hot = colorize(suv, 0.0, PET_MAX_SUV, "hot").astype(np.float64)
    a = (np.clip(suv / PET_MAX_SUV, 0.0, 1.0) * 0.65)[..., None]
    return np.round(base * (1 - a) + hot * a).astype(np.uint8)


def _outlined(rgb_small: np.ndarray, mask: np.ndarray, color, up: int = UPSCALE) -> np.ndarray:
    big = np.kron(rgb_small, np.ones((up, up, 1), dtype=np.uint8))
    mbig = np.kron(mask.astype(np.uint8), np.ones((up, up), np.uint8)) > 0
    return paint(big, _thick(contour(mbig)), color)


def review_panels(
    w: WorkGrid, geometry, *, neighbour_offsets_mm: tuple[float, ...] = (-12, -6, 6, 12)
) -> dict[str, list[tuple[str, np.ndarray]]]:
    """{'main': [...], 'neighbours': [...], 'context': [...]} of (label, RGB) tiles around
    ``geometry`` (anything with method / centre_patient_mm / diameter_mm / length_mm).
    Display only, on the 3 mm working grid; measurements come from the PET grid."""
    m = region_mask_on_work(w, geometry)
    k, j, i = w.index_of(geometry.centre_patient_mm)
    nk = w.hu.shape[0]
    h = int(round(ZOOM_HALF_MM / w.spacing))
    if not (0 <= k < nk and 0 <= j < w.hu.shape[1] and 0 <= i < w.hu.shape[2]):
        raise ValueError("centre outside the CT working grid")
    suv = w.suv if w.suv is not None else np.zeros_like(w.hu)

    def ax(vol, kk):
        return _crop(vol[kk], j, i, h)

    main = [
        (
            "PET axial (SUV 0-5)",
            _outlined(colorize(ax(suv, k), 0, PET_MAX_SUV, "gray_inverted"), ax(m, k), MAGENTA),
        ),
        (
            "CT axial (HU -150..350)",
            _outlined(colorize(ax(w.hu, k), -150, 350, "gray"), ax(m, k), GREEN),
        ),
        ("Fused PET/CT axial", _outlined(_fused(ax(w.hu, k), ax(suv, k)), ax(m, k), (0, 255, 255))),
    ]
    neighbours = []
    for off in neighbour_offsets_mm:
        kk = k + int(round(off / w.spacing))
        if 0 <= kk < nk:
            neighbours.append(
                (
                    f"fused axial {off:+g} mm" + ("" if ax(m, kk).any() else " (outside region)"),
                    _outlined(_fused(ax(w.hu, kk), ax(suv, kk)), ax(m, kk), (0, 255, 255)),
                )
            )
    kc = nk - 1 - k
    co_hu = _crop(w.hu[:, j, :][::-1], kc, i, h)
    co_suv = _crop(suv[:, j, :][::-1], kc, i, h)
    co_m = _crop(m[:, j, :][::-1], kc, i, h)
    context = [
        ("Fused PET/CT coronal", _outlined(_fused(co_hu, co_suv), co_m, (0, 255, 255))),
        (
            "CT coronal (location)",
            _outlined(
                colorize(w.hu[:, j, :][::-1], -150, 350, "gray"), m[:, j, :][::-1], GREEN, up=2
            ),
        ),
    ]
    return {"main": main, "neighbours": neighbours, "context": context}
