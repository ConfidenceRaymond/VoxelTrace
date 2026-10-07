"""Exact 2-D annotations for rendered axial views + render/annotation consistency checks.

All annotations are derived from the supplied segmentation and validated voxel coordinates
through ``PlaneMapping`` (no image analysis of the rendered PNG). ``verify_axial_render``
re-derives everything from the arrays and the evidence JSON and raises on any mismatch.
"""

from __future__ import annotations

import json
import math
from typing import Any

import numpy as np

from voxeltrace.quant.lesions import PEAK_RADIUS_MM
from voxeltrace.training.schema import Annotation2D, gt
from voxeltrace.visualization.overlays import (
    CYAN,
    GREEN,
    MAGENTA,
    YELLOW,
    circle,
    contour,
    crosshair,
    paint,
    rectangle,
)
from voxeltrace.visualization.render import PlaneMapping, RenderError


class RenderVerificationError(RenderError):
    pass


def _gt(value: Any, ref: str):
    return gt(value, "DETERMINISTIC_DERIVATION", ref, "geometry_transform")


def visible_mask_px(mask: np.ndarray, k: int, m: PlaneMapping) -> np.ndarray:
    return m.expand(mask[k, m.b0 : m.b0 + m.n_b, m.a0 : m.a0 + m.n_a])


def mask_annotations(mask: np.ndarray, k: int, m: PlaneMapping, target: str) -> list[Annotation2D]:
    sl = mask[k, m.b0 : m.b0 + m.n_b, m.a0 : m.a0 + m.n_a]
    js, is_ = np.nonzero(sl)
    if len(js) == 0:
        return []
    box = m.voxel_box_to_px(
        int(is_.min()) + m.a0, int(js.min()) + m.b0, int(is_.max()) + m.a0, int(js.max()) + m.b0
    )
    ref = f"reference segmentation slice k={k} -> PlaneMapping"
    return [
        Annotation2D(kind="bbox", target=target, value=_gt(box, ref)),
        Annotation2D(
            kind="mask_pixel_count", target=target, value=_gt(int(sl.sum()) * m.sx * m.sy, ref)
        ),
    ]


def point_annotation(
    kji: tuple[int, int, int], k: int, m: PlaneMapping, target: str, ref: str
) -> Annotation2D | None:
    if kji[0] != k or not m.contains(kji[2], kji[1]):
        return None
    return Annotation2D(
        kind="point", target=target, value=_gt(list(m.voxel_to_px(kji[2], kji[1])), ref)
    )


def peak_circle(
    center_kji: tuple[int, int, int],
    k: int,
    slice_spacing: float,
    m: PlaneMapping,
    mm_per_px: float,
    ref: str,
) -> Annotation2D | None:
    """Intersection of the 1 cm³ SUVpeak sphere with slice k (radius in px)."""
    dz = abs(k - center_kji[0]) * slice_spacing
    if dz > PEAK_RADIUS_MM or not m.contains(center_kji[2], center_kji[1]):
        return None
    r_px = math.sqrt(PEAK_RADIUS_MM**2 - dz**2) / mm_per_px
    x, y = m.voxel_to_px(center_kji[2], center_kji[1])
    return Annotation2D(
        kind="circle", target="suvpeak_sphere", value=_gt([x, y, round(r_px, 4)], ref)
    )


def draw(
    rgb: np.ndarray,
    mask_px: np.ndarray | None,
    anns: list[Annotation2D],
    *,
    outline: bool = True,
    markers: bool = True,
    boxes: bool = False,
) -> np.ndarray:
    out = rgb
    shape = rgb.shape[:2]
    for a in anns:
        v = a.value.value
        if boxes and a.kind == "bbox":
            out = paint(out, rectangle(shape, v), YELLOW)
        if markers and a.kind == "point" and a.target == "suvmax":
            out = paint(out, crosshair(shape, v[0], v[1], arm=max(6, shape[0] // 40)), GREEN)
        if markers and a.kind == "circle":
            out = paint(out, circle(shape, v[0], v[1], v[2]), MAGENTA)
    if outline and mask_px is not None:  # last, so the outline is exact on the mask boundary
        out = paint(out, contour(mask_px), CYAN)
    return out


def resolve(evidence: dict[str, Any], path: str) -> Any:
    """Resolve 'measured.lesions[0].suv_max' style paths in evidence JSON."""
    cur: Any = evidence
    for part in path.replace("]", "").split("."):
        name, _, idx = part.partition("[")
        cur = cur[name] if name else cur
        if idx:
            cur = cur[int(idx)]
    return cur


def displayed_value(
    evidence: dict[str, Any], path: str, label: str, fmt: str = ".3f", unit: str = ""
) -> dict[str, Any]:
    v = resolve(evidence, path)
    return {
        "label": label,
        "evidence_path": path,
        "value": v,
        "format": fmt,
        "unit": unit,
        "text": _text(label, v, fmt, unit),
    }


def _text(label: str, v: Any, fmt: str, unit: str) -> str:
    return f"{label} {format(v, fmt)}{(' ' + unit) if unit else ''}"


def verify_axial_render(
    *,
    rgb: np.ndarray,
    mask: np.ndarray,
    suv: np.ndarray,
    k: int,
    m: PlaneMapping,
    anns: list[Annotation2D],
    segment_number: int,
    expected_segment: int,
    suvmax_kji: tuple[int, int, int] | None,
    suv_max: float | None,
    displayed: list[dict[str, Any]],
    suvpeak_kji: tuple[int, int, int] | None = None,
    slice_spacing_mm: float | None = None,
    mm_per_px: float | None = None,
    evidence_json_text: str,
    outline_drawn: bool,
) -> None:
    """Part K checks. Raises RenderVerificationError on any mismatch."""
    if segment_number != expected_segment:
        raise RenderVerificationError("displayed lesion id does not map to the rendered segment")
    mask_px = visible_mask_px(mask, k, m)
    sl = mask[k, m.b0 : m.b0 + m.n_b, m.a0 : m.a0 + m.n_a]
    if int(mask_px.sum()) != int(sl.sum()) * m.sx * m.sy:
        raise RenderVerificationError("rendered mask pixel count != slice voxel count × block")
    for a in anns:
        if a.kind == "mask_pixel_count" and a.value.value != int(mask_px.sum()):
            raise RenderVerificationError("mask_pixel_count annotation mismatch")
        if a.kind == "bbox":
            ys, xs = np.nonzero(mask_px)
            if a.value.value != [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]:
                raise RenderVerificationError("bbox annotation != rendered mask extent")
        if a.kind == "point" and a.target == "suvmax":
            if suvmax_kji is None or suv_max is None:
                raise RenderVerificationError("SUVmax marker without SUVmax coordinate")
            vi, vj = m.px_to_voxel(*a.value.value)
            if (k, vj, vi) != tuple(suvmax_kji) or suv[k, vj, vi] != suv_max:
                raise RenderVerificationError("SUVmax marker does not map to the SUVmax voxel")
        if a.kind == "circle" and a.target == "suvpeak_sphere":
            if suvpeak_kji is None or slice_spacing_mm is None or mm_per_px is None:
                raise RenderVerificationError("SUVpeak marker without SUVpeak centre")
            x, y, r_px = a.value.value
            vi, vj = m.px_to_voxel(int(x), int(y))
            if (vj, vi) != (suvpeak_kji[1], suvpeak_kji[2]):
                raise RenderVerificationError("SUVpeak marker centre != SUVpeak centre voxel")
            dz = abs(k - suvpeak_kji[0]) * slice_spacing_mm
            expect = math.sqrt(max(PEAK_RADIUS_MM**2 - dz**2, 0.0)) / mm_per_px
            if dz > PEAK_RADIUS_MM or abs(r_px - round(expect, 4)) > 1e-9:
                raise RenderVerificationError("SUVpeak circle radius inconsistent with sphere")
    if outline_drawn and mask_px.any():
        c = contour(mask_px)
        if not np.all(rgb[: mask_px.shape[0]][c] == np.array(CYAN, np.uint8)):
            raise RenderVerificationError("outline pixels not drawn exactly on mask boundary")
    evidence = json.loads(evidence_json_text)
    for d in displayed:
        v = resolve(evidence, d["evidence_path"])
        if v != d["value"] or d["text"] != _text(d["label"], v, d["format"], d["unit"]):
            raise RenderVerificationError(f"displayed value {d['text']!r} != evidence")
