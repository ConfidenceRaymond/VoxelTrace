"""Multimodal example generation from ground truth (no model involvement).

Every rendered image is verified (``verify_axial_render``) before it is saved, and every
target is taken from a GTValue that is usable as a target (TrainingExample enforces this).

Slice selection rules (also recorded in the manifest):
  POSITIVE (per supplied segment, max ``MAX_POSITIVE`` slices):
    P1 slice containing the segment's SUVmax voxel;
    P2 slice of the SUVpeak sphere centre;
    P3 for each 26-connected component (largest first) the slice with its largest
       in-slice area;
    a candidate is skipped if within ``MIN_SLICE_GAP`` slices of an already selected slice
    (avoids near-duplicate images).
  NEGATIVE (lesion-negative, ``N_NEGATIVE`` slices):
    slices with no voxel of any supplied segment, at least ``NEG_MIN_DISTANCE`` slices from
    any segmented slice, with PET signal present (>= 5 % of voxels > 0, which excludes masked /
    defaced / out-of-field slices) and body present on CT (>= 5 % of voxels > -500 HU);
    chosen deterministically at the 15/40/65/90 % quantiles of the eligible list.
    Label meaning: "no reference-segmented target in this slice" -- NOT "normal".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from voxeltrace.evidence.claims import ClaimEvidence, claim_quantity
from voxeltrace.evidence.comparability import compare_protocols
from voxeltrace.evidence.protocol import ProtocolEvidence
from voxeltrace.schemas import EvidenceField, QuantEvidence
from voxeltrace.training.ground_truth import CaseArrays
from voxeltrace.training.schema import (
    GroundTruthCase,
    GroundTruthLesion,
    GTValue,
    ImageRef,
    SplitName,
    TrainingExample,
    VisualGroundTruth,
    gt,
)
from voxeltrace.visualization import (
    crop_box,
    ct_axial,
    fused_axial,
    mask_annotations,
    peak_circle,
    pet_axial,
    pet_coronal_mip,
    png_bytes,
    point_annotation,
    verify_axial_render,
)
from voxeltrace.visualization.annotations import displayed_value, draw, visible_mask_px
from voxeltrace.visualization.render import add_footer, sha256_bytes

GENERATOR_VERSION = "vt-examples-1"
MAX_POSITIVE = 8
MIN_SLICE_GAP = 3
N_NEGATIVE = 4
NEG_MIN_DISTANCE = 10
NEG_QUANTILES = (0.15, 0.40, 0.65, 0.90)
ZERO_SUV_EXCLUDE = 0.5
FULL_SCALE = 2
CROP_SCALE = 6
CROP_MM = 80.0

SELECTION_RULES = [
    "positive P1: slice containing each supplied segment's SUVmax voxel",
    "positive P2: slice of the SUVpeak sphere centre",
    "positive P3: per 26-connected component (largest first) its largest in-slice area",
    f"skip candidates within {MIN_SLICE_GAP} slices of a selected slice; "
    f"max {MAX_POSITIVE} positive slices",
    f"negative: no segment voxels, >= {NEG_MIN_DISTANCE} slices from any segmented slice, "
    "PET signal on >= 5 % of voxels, CT body (> -500 HU) on >= 5 % of voxels; "
    f"quantiles {NEG_QUANTILES} of eligible slices",
    "negative label means 'no reference-segmented target in this slice', not 'normal'",
    f"positive candidates are EXCLUDED when > {ZERO_SUV_EXCLUDE:.0%} of the segment's in-slice "
    "voxels have SUV exactly 0 (reference mask over masked/zeroed PET, e.g. outside the body); "
    "such slices are kept only in the human-review audit",
]


# --------------------------------------------------------------------------------------
# Slice selection
# --------------------------------------------------------------------------------------


def zero_suv_fraction(les: GroundTruthLesion, k: int) -> float:
    n = les.voxels_per_slice.value.get(str(k), 0)
    z = (
        (les.zero_suv_voxels_per_slice.value or {}).get(str(k), 0)
        if les.zero_suv_voxels_per_slice
        else 0
    )
    return z / n if n else 0.0


def select_positive_slices(
    case: GroundTruthCase,
    excluded: list[tuple[int, str, str]] | None = None,
) -> list[tuple[int, str, str]]:
    """[(k, lesion_id, rule)] following SELECTION_RULES. Excluded candidates are appended to
    ``excluded`` (with reason) for the audit trail."""
    chosen: list[tuple[int, str, str]] = []
    lesions = {x.lesion_id: x for x in case.quantitative.lesions}

    def add(k: int | None, lid: str, rule: str) -> None:
        if k is None or len(chosen) >= MAX_POSITIVE:
            return
        if zero_suv_fraction(lesions[lid], int(k)) > ZERO_SUV_EXCLUDE:
            if excluded is not None and all(e[0] != k for e in excluded):
                excluded.append((int(k), lid, f"{rule}:excluded_zero_suv"))
            return
        if all(abs(k - c[0]) >= MIN_SLICE_GAP for c in chosen):
            chosen.append((int(k), lid, rule))

    for les in case.quantitative.lesions:
        add(les.suvmax_voxel_kji.value[0], les.lesion_id, "P1")
        if les.suvpeak_center_kji.value is not None:
            add(les.suvpeak_center_kji.value[0], les.lesion_id, "P2")
    for les in case.quantitative.lesions:
        vps = {int(k): v for k, v in les.voxels_per_slice.value.items()}
        for comp in les.components:
            ks = comp.slices_k.value
            best = max(ks, key=lambda k: (vps.get(k, 0), -k)) if ks else None
            add(best, les.lesion_id, f"P3:component{comp.component_index}")
    return sorted(chosen)


def select_negative_slices(arrays: CaseArrays) -> list[int]:
    union = np.zeros(arrays.suv.shape[0], bool)
    for m in arrays.masks.values():
        union |= m.any(axis=(1, 2))
    seg_k = np.flatnonzero(union)
    eligible = []
    for k in range(arrays.suv.shape[0]):
        if union[k]:
            continue
        if seg_k.size and np.abs(seg_k - k).min() < NEG_MIN_DISTANCE:
            continue
        if (arrays.suv[k] > 0).mean() < 0.05:
            continue
        if arrays.ct_on_pet is not None and (arrays.ct_on_pet[k] > -500).mean() < 0.05:
            continue
        eligible.append(k)
    if not eligible:
        return []
    picks = [eligible[int(round(q * (len(eligible) - 1)))] for q in NEG_QUANTILES]
    return sorted(set(picks))


# --------------------------------------------------------------------------------------
# Rendering with verification
# --------------------------------------------------------------------------------------


@dataclass
class RenderedImage:
    vgt: VisualGroundTruth
    png: bytes
    role: str  # "model_input" | "audit"
    lesion_id: str | None
    rgb: np.ndarray = field(repr=False, default_factory=lambda: np.zeros((1, 1, 3), np.uint8))


class Renderer:
    def __init__(self, case: GroundTruthCase, arrays: CaseArrays, evidence_json_text: str):
        self.case = case
        self.a = arrays
        self.ev_text = evidence_json_text
        self.ev = json.loads(evidence_json_text)
        self.images: dict[str, RenderedImage] = {}

    def _lesion(self, lid: str) -> tuple[GroundTruthLesion, int]:
        for i, les in enumerate(self.case.quantitative.lesions):
            if les.lesion_id == lid:
                return les, i
        raise KeyError(lid)

    def axial(
        self,
        view: str,
        k: int,
        *,
        lesion_id: str | None,
        crop: bool,
        outline: bool,
        markers: bool,
        boxes: bool,
        show_values: bool,
        role: str,
    ) -> RenderedImage:
        g = self.a.geometry
        les, li = self._lesion(lesion_id) if lesion_id else (None, -1)
        crop_v = None
        scale = FULL_SCALE
        if crop and les is not None:
            crop_v = crop_box(
                crop_center(self.a.masks[les.segment_number.value], k, les), g, CROP_MM
            )
            scale = CROP_SCALE
        if view == "fused":
            if self.a.ct_on_pet is None:
                raise ValueError("fusion requires CT")
            rgb, m, params = fused_axial(
                self.a.suv, self.a.ct_on_pet, g, k, scale=scale, crop=crop_v
            )
        elif view == "pet":
            rgb, m, params = pet_axial(self.a.suv, g, k, scale=scale, crop=crop_v)
        elif view == "ct":
            if self.a.ct_on_pet is None:
                raise ValueError("CT view requires CT")
            rgb, m, params = ct_axial(self.a.ct_on_pet, g, k, scale=scale, crop=crop_v)
        else:
            raise ValueError(view)
        anns = []
        mask = None
        displayed: list[dict[str, Any]] = []
        if les is not None:
            mask = self.a.masks[les.segment_number.value]
            anns += mask_annotations(mask, k, m, les.lesion_id)
            p = point_annotation(
                tuple(les.suvmax_voxel_kji.value), k, m, "suvmax", les.suvmax_voxel_kji.source_ref
            )
            if p:
                anns.append(p)
            if les.suvpeak_center_kji.value is not None:
                c = peak_circle(
                    tuple(les.suvpeak_center_kji.value),
                    k,
                    float(g.spacing_ijk[2]),
                    m,
                    params.mm_per_px_x,
                    les.suvpeak_center_kji.source_ref,
                )
                if c:
                    anns.append(c)
            if show_values:
                base = f"measured.lesions[{li}]"
                displayed = [
                    displayed_value(self.ev, f"{base}.suv_max", "SUVmax", unit="g/mL"),
                    displayed_value(self.ev, f"{base}.mtv_ml", "MTV", unit="mL"),
                ]
                if les.suv_peak.value is not None:
                    displayed.append(
                        displayed_value(self.ev, f"{base}.suv_peak.value", "SUVpeak", unit="g/mL")
                    )
        mask_px = visible_mask_px(mask, k, m) if mask is not None else None
        out = draw(rgb, mask_px, anns, outline=outline, markers=markers, boxes=boxes)
        if les is not None:
            verify_axial_render(
                rgb=out,
                mask=mask,
                suv=self.a.suv,
                k=k,
                m=m,
                anns=anns,  # type: ignore[arg-type]
                segment_number=les.segment_number.value,
                expected_segment=int(les.lesion_id.removeprefix("seg")),
                suvmax_kji=tuple(les.suvmax_voxel_kji.value),
                suv_max=les.suv_max.value,
                displayed=displayed,
                evidence_json_text=self.ev_text,
                outline_drawn=outline,
            )
        params.overlays = [
            o
            for o, on in (
                ("segmentation_outline", outline),
                ("suvmax_crosshair+suvpeak_circle", markers),
                ("bbox", boxes),
            )
            if on
        ]
        footer = [
            f"{view.upper()} axial k={k} | radiological: patient R on image left, anterior up"
        ]
        if view in ("pet", "fused"):
            footer.append("SUVbw display window 0-8 g/mL (display only)")
        footer += (
            [d["text"] + f" (segment {les.segment_number.value})" for d in displayed]
            if les is not None
            else []
        )
        final = add_footer(
            out, footer, mm_per_px=params.mm_per_px_x, scale_bar_mm=20 if crop_v else 50
        )
        png = png_bytes(final)
        image_id = (
            f"{self.case.subject_pseudonym}_k{k:03d}_{view}"
            f"{'_crop' if crop_v else ''}{'_outline' if outline else ''}"
            f"{'_markers' if markers else ''}{'_box' if boxes else ''}"
            f"{'_values' if show_values else ''}"
        )
        contains = any(m_[k].any() for m_ in self.a.masks.values())
        vgt = VisualGroundTruth(
            image_id=image_id,
            path=f"images/{image_id}.png",
            sha256=sha256_bytes(png),
            view=f"{view}_axial{'_crop' if crop_v else ''}",
            slice_k=k,
            width=final.shape[1],
            height=final.shape[0],
            render_params={**params.model_dump(), "image_region_height": out.shape[0]},
            annotations=anns,
            displayed_values=displayed,
            contains_segmented_target=contains,
        )
        ri = RenderedImage(vgt, png, role, lesion_id, final)
        self.images[image_id] = ri
        return ri

    def mip(self) -> RenderedImage:
        g = self.a.geometry
        rgb, m, params = pet_coronal_mip(self.a.suv, g, scale=2)
        anns = []
        for les in self.case.quantitative.lesions:
            k, _, i = les.suvmax_voxel_kji.value
            x, y = m.voxel_to_px(i, k)
            anns.append(point_annotation_mip(les, x, y))
        final = add_footer(
            rgb,
            [
                "PET coronal MIP (anterior view, superior up, patient R on image left)",
                "SUVbw display window 0-8 g/mL",
            ],
            mm_per_px=params.mm_per_px_x,
            scale_bar_mm=100,
        )
        png = png_bytes(final)
        image_id = f"{self.case.subject_pseudonym}_mip_coronal"
        vgt = VisualGroundTruth(
            image_id=image_id,
            path=f"images/{image_id}.png",
            sha256=sha256_bytes(png),
            view="pet_coronal_mip",
            width=final.shape[1],
            height=final.shape[0],
            render_params={**params.model_dump(), "image_region_height": rgb.shape[0]},
            annotations=anns,
            contains_segmented_target=True,
        )
        ri = RenderedImage(vgt, png, "model_input", None, final)
        self.images[image_id] = ri
        return ri


def crop_center(mask: np.ndarray, k: int, les: GroundTruthLesion) -> tuple[int, int]:
    """Crop centre (j, i): the segment's in-slice centroid; SUVmax voxel if the slice has none.

    Centring on the SUVmax voxel of a DIFFERENT slice would miss components elsewhere.
    """
    js, is_ = np.nonzero(mask[k])
    if len(js):
        return int(round(float(js.mean()))), int(round(float(is_.mean())))
    _, jc, ic = les.suvmax_voxel_kji.value
    return int(jc), int(ic)


def point_annotation_mip(les: GroundTruthLesion, x: int, y: int):
    from voxeltrace.training.schema import Annotation2D

    return Annotation2D(
        kind="point",
        target=f"{les.lesion_id}:suvmax_projection",
        value=gt(
            [x, y],
            "DETERMINISTIC_DERIVATION",
            les.suvmax_voxel_kji.source_ref,
            "geometry_transform",
        ),
    )


# --------------------------------------------------------------------------------------
# Compact evidence contexts (pseudonymised; no raw UIDs)
# --------------------------------------------------------------------------------------


def compact_quant(ev: QuantEvidence) -> dict[str, Any]:
    return {
        "suv_status": ev.measured.suv_status,
        "suv_units": "g/mL (SUVbw)",
        "lesions": [
            {
                "segment_number": x.segment_number,
                "segment_label": x.segment_label,
                "voxel_count": x.voxel_count,
                "mtv_ml": x.mtv_ml,
                "suv_max": x.suv_max,
                "suv_mean": x.suv_mean,
                "suv_median": x.suv_median,
                "suv_peak": x.suv_peak.value if x.suv_peak else None,
                "tlg": x.tlg,
                "n_components": x.n_components,
            }
            for x in ev.measured.lesions
        ],
        "not_established": ev.not_established,
    }


_PROTO_KEYS = {
    "scanner": ["manufacturer", "manufacturer_model_name", "software_versions"],
    "acquisition": [
        "tracer",
        "injected_activity_bq",
        "uptake_interval_s",
        "frame_duration_ms",
        "image_units",
        "decay_correction",
    ],
    "reconstruction": [
        "reconstruction_method",
        "iterations",
        "subsets",
        "time_of_flight",
        "psf_resolution_modelling",
        "convolution_kernel",
        "reconstruction_diameter_mm",
        "voxel_size_mm",
        "matrix_rows",
        "matrix_columns",
    ],
}


def _ef(f: EvidenceField) -> dict[str, Any]:
    return {"value": f.value, "unit": f.unit, "status": f.status, "derivation": f.derivation}


def compact_protocol(p: ProtocolEvidence) -> dict[str, Any]:
    out: dict[str, Any] = {
        cat: {k: _ef(getattr(getattr(p, cat), k)) for k in keys}
        for cat, keys in _PROTO_KEYS.items()
    }
    out["corrections"] = {
        "corrected_image": _ef(p.corrections.corrected_image),
        **{k: _ef(v) for k, v in p.corrections.applied.items()},
    }
    return out


# --------------------------------------------------------------------------------------
# Example builders
# --------------------------------------------------------------------------------------


class ExampleFactory:
    def __init__(self, case: GroundTruthCase, split: SplitName, provenance: dict[str, Any]):
        self.case = case
        self.split = split
        self.prov = provenance
        self.examples: list[TrainingExample] = []

    def add(
        self,
        cls: str,
        question: str,
        target: dict[str, Any],
        sources: list[GTValue],
        *,
        images: list[RenderedImage] = (),
        context: dict[str, Any] | None = None,  # type: ignore[assignment]
        synthetic: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> TrainingExample:
        n = sum(1 for e in self.examples if e.example_class == cls) + 1
        e = TrainingExample(
            example_id=f"{self.case.subject_pseudonym}-{cls.lower()}-{n:03d}",
            example_class=cls,  # type: ignore[arg-type]
            split=self.split,
            subject_pseudonym=self.case.subject_pseudonym,
            study_pseudonym=self.case.study_pseudonym,
            images=[
                ImageRef(
                    image_id=i.vgt.image_id, path=i.vgt.path, sha256=i.vgt.sha256, view=i.vgt.view
                )
                for i in images
            ],
            question=question,
            context=context,
            target=target,
            target_sources=sources,
            ground_truth_level=max(s.level for s in sources),
            synthetic_perturbation=synthetic,
            provenance={**self.prov, **(extra or {})},
        )
        self.examples.append(e)
        return e


def _status_target(c: ClaimEvidence) -> tuple[dict[str, Any], GTValue]:
    src = gt(c.status, "RULE_DERIVATION", f"claims-1:{c.claim_id}", "rule_engine")
    tgt: dict[str, Any] = {"status": c.status, "claim_type": c.claim_type}
    if c.status in ("NOT_ESTABLISHED",):
        tgt["missing_evidence"] = c.missing_evidence
    return tgt, src


def build_examples(
    case: GroundTruthCase,
    renderer: Renderer,
    ev: QuantEvidence,
    protocol: ProtocolEvidence,
    claims: list[ClaimEvidence],
    split: SplitName,
    provenance: dict[str, Any],
    negatives: list[int],
    positives: list[tuple[int, str, str]],
) -> list[TrainingExample]:
    f = ExampleFactory(case, split, provenance)
    quant_ctx = compact_quant(ev)
    proto_ctx = compact_protocol(protocol)
    pg = case.protocol.fields

    # 1. VISUAL_LOCALIZATION (positives with outline) + lesion-negative slices
    loc_q = (
        "The image is an axial PET/CT fusion. A supplied reference segmentation, if present "
        "in this slice, is outlined in cyan. Does the slice contain a reference-segmented "
        "target? If yes, give the segment number and its bounding box in image pixel "
        "coordinates [x_min, y_min, x_max, y_max] (inclusive, origin top-left)."
    )
    for k, lid, rule in positives:
        img = renderer.axial(
            "fused",
            k,
            lesion_id=lid,
            crop=False,
            outline=True,
            markers=False,
            boxes=False,
            show_values=False,
            role="model_input",
        )
        les = renderer._lesion(lid)[0]
        box = next(a for a in img.vgt.annotations if a.kind == "bbox").value
        f.add(
            "VISUAL_LOCALIZATION",
            loc_q,
            {
                "contains_segmented_target": True,
                "segment_number": les.segment_number.value,
                "slice_k": k,
                "bbox_px": box.value,
            },
            [box, les.segment_number],
            images=[img],
            extra={"selection_rule": rule},
        )
    for k in negatives:
        img = renderer.axial(
            "fused",
            k,
            lesion_id=None,
            crop=False,
            outline=True,
            markers=False,
            boxes=False,
            show_values=False,
            role="model_input",
        )
        src = gt(
            False,
            "REFERENCE_SEGMENTATION",
            f"reference segmentation: no voxels at k={k}",
            "segmentation_decode",
        )
        f.add(
            "VISUAL_LOCALIZATION",
            loc_q,
            {
                "contains_segmented_target": False,
                "slice_k": k,
                "note": "no reference-segmented target in this slice (not a statement that the "
                "slice is normal)",
            },
            [src],
            images=[img],
            extra={"selection_rule": "negative"},
        )

    # 2. QUANTITATIVE_READING and 8. VISUAL_QUANTITATIVE (per lesion, at SUVmax slice)
    for les in case.quantitative.lesions:
        k = les.suvmax_voxel_kji.value[0]
        crop_in = renderer.axial(
            "pet",
            k,
            lesion_id=les.lesion_id,
            crop=True,
            outline=True,
            markers=False,
            boxes=False,
            show_values=False,
            role="model_input",
        )
        renderer.axial(
            "pet",
            k,
            lesion_id=les.lesion_id,
            crop=True,
            outline=True,
            markers=True,
            boxes=True,
            show_values=True,
            role="audit",
        )
        f.add(
            "QUANTITATIVE_READING",
            f"Using the structured quantitative evidence (do not estimate from pixels), report "
            f"SUVmax, SUVmean, MTV and TLG for segment {les.segment_number.value}, with units.",
            {
                "segment_number": les.segment_number.value,
                "suv_max": {"value": les.suv_max.value, "unit": "g/mL"},
                "suv_mean": {"value": les.suv_mean.value, "unit": "g/mL"},
                "mtv": {"value": les.mtv_ml.value, "unit": "mL"},
                "tlg": {"value": les.tlg.value, "unit": "g"},
            },
            [les.suv_max, les.suv_mean, les.mtv_ml, les.tlg, les.segment_number],
            images=[crop_in],
            context={"quantitative_evidence": quant_ctx},
        )
        pt = next(a for a in crop_in.vgt.annotations if a.kind == "point" and a.target == "suvmax")
        f.add(
            "VISUAL_QUANTITATIVE",
            f"This lesion-centred PET crop shows segment {les.segment_number.value} outlined "
            "in cyan. Which pixel location corresponds to the segment's SUVmax voxel? Answer "
            "with [x, y] image pixel coordinates.",
            {
                "suvmax_px": pt.value.value,
                "suvmax_voxel_kji": les.suvmax_voxel_kji.value,
                "suv_max": {"value": les.suv_max.value, "unit": "g/mL"},
            },
            [pt.value, les.suvmax_voxel_kji, les.suv_max],
            images=[crop_in],
            context={"quantitative_evidence": quant_ctx},
        )

    # MIP-based quantitative reading (whole-body context)
    mip = renderer.mip()
    if case.quantitative.lesions:
        les = case.quantitative.lesions[0]
        f.add(
            "QUANTITATIVE_READING",
            "Using the structured evidence, what is the SUVpeak of segment "
            f"{les.segment_number.value} and how is SUVpeak defined in this evidence?",
            {
                "suv_peak": {"value": les.suv_peak.value, "unit": "g/mL"},
                "definition": "maximum mean SUV in a 1.0 cm^3 sphere (r = 6.2035 mm) centred on "
                "a voxel of the supplied segment",
            },
            [les.suv_peak],
            images=[mip],
            context={"quantitative_evidence": quant_ctx},
        )

    # 3. PROTOCOL_READING (validated standard attributes only)
    keys = [
        "scanner.manufacturer",
        "scanner.manufacturer_model_name",
        "scanner.software_versions",
        "reconstruction.reconstruction_method",
        "reconstruction.convolution_kernel",
        "corrections.corrected_image",
    ]
    srcs = [pg[k] for k in keys]
    f.add(
        "PROTOCOL_READING",
        "Which scanner (manufacturer, model, software) and which reconstruction (method text "
        "and convolution kernel) were used, and which corrections are declared?",
        {k: pg[k].value for k in keys},
        srcs,
        context={"protocol_evidence": proto_ctx},
    )
    up = pg["acquisition.uptake_interval_s"]
    f.add(
        "PROTOCOL_READING",
        "What was the uptake interval between injection and the scan reference time?",
        {"uptake_interval_s": up.value, "unit": "s"},
        [up],
        context={"protocol_evidence": proto_ctx},
    )

    # 4/5/6. CLAIMS
    for c in claims:
        tgt, src = _status_target(c)
        cls = {
            "SUPPORTED": "CLAIM_VERIFICATION",
            "PARTIALLY_SUPPORTED": "CLAIM_VERIFICATION",
            "CONTRADICTED": "CONTRADICTION",
            "NOT_ESTABLISHED": "REFUSAL",
        }[c.status]
        f.add(
            cls,
            f'Is the statement "{c.statement}" supported by the evidence? Answer with '
            "SUPPORTED, PARTIALLY_SUPPORTED, NOT_ESTABLISHED or CONTRADICTED.",
            tgt,
            [src],
            context={"quantitative_evidence": quant_ctx, "protocol_evidence": proto_ctx},
        )
    for les in case.quantitative.lesions:
        n = les.segment_number.value
        for metric, wrong in (
            ("suv_max", les.suv_max.value * 1.25),
            ("mtv_ml", les.mtv_ml.value * 0.5),
            ("tlg", les.tlg.value * 1.10),
        ):
            # 4 significant digits so the wrong value is wrong at its own stated precision;
            # the class always follows the rule engine's actual status, never the intent.
            c = claim_quantity(
                ev, metric, f"{wrong:.4g}", segment=n, claim_id=f"wrong-{metric}-seg{n}"
            )
            if c.status != "CONTRADICTED":
                continue
            tgt, src = _status_target(c)
            f.add(
                "CONTRADICTION",
                f'Is the statement "{c.statement}" supported by the evidence?',
                tgt,
                [src],
                context={"quantitative_evidence": quant_ctx},
            )

    # 7. MISSING_DATA: real absent field + synthetic removal of the filter fields
    rd = pg["reconstruction.reconstruction_diameter_mm"]
    if rd.validation_status == "VALIDATED_ABSENT":
        f.add(
            "MISSING_DATA",
            "What was the reconstruction diameter?",
            {
                "answer": "INSUFFICIENT_INFORMATION",
                "field": "reconstruction.reconstruction_diameter_mm",
            },
            [rd],
            context={"protocol_evidence": proto_ctx},
        )
    nb = pg["acquisition.number_of_bed_positions"]
    f.add(
        "MISSING_DATA",
        "How many bed positions were acquired?",
        {"answer": "INSUFFICIENT_INFORMATION", "field": "acquisition.number_of_bed_positions"},
        [nb],
        context={"protocol_evidence": proto_ctx},
    )
    pert = protocol.model_copy(deep=True)
    for name in ("convolution_kernel", "filter_type", "post_filter_gaussian_width"):
        setattr(
            pert.reconstruction,
            name,
            EvidenceField(name=name, status="MISSING", source="removed (synthetic test)"),
        )
    f.add(
        "MISSING_DATA",
        "What reconstruction filter was used?",
        {"answer": "INSUFFICIENT_INFORMATION", "field": "reconstruction.convolution_kernel"},
        [
            gt(
                None,
                "RULE_DERIVATION",
                "synthetic removal of reconstruction filter fields",
                "synthetic_perturbation",
                "VALIDATED_ABSENT",
            )
        ],
        context={"protocol_evidence": compact_protocol(pert)},
        synthetic=True,
    )

    # 9. PROTOCOL_COMPARABILITY: real protocol vs documented synthetic perturbations
    for label, b in _perturbations(protocol):
        res = compare_protocols(protocol, b)
        f.add(
            "PROTOCOL_COMPARABILITY",
            "Scan A and scan B protocol evidence are given. Are they quantitatively comparable? "
            "Answer COMPARABLE, COMPARABLE_WITH_WARNINGS, NOT_COMPARABLE or "
            "INSUFFICIENT_INFORMATION and list blocking differences.",
            {
                "category": res.category,
                "blocking_differences": res.blocking_differences,
                "blocking_unknowns": res.blocking_unknowns,
                "warnings": res.warnings,
            },
            [
                gt(
                    res.category,
                    "RULE_DERIVATION",
                    f"compare_protocols:{label}",
                    "synthetic_perturbation",
                )
            ],
            context={"scan_a": compact_protocol(protocol), "scan_b": compact_protocol(b)},
            synthetic=label != "identical",
            extra={"perturbation": label},
        )
    return f.examples


def _perturbations(p: ProtocolEvidence) -> list[tuple[str, ProtocolEvidence]]:
    out = [("identical", p.model_copy(deep=True))]

    def mod(label, fn):
        q = p.model_copy(deep=True)
        fn(q)
        out.append((label, q))

    def kernel(q):
        q.reconstruction.convolution_kernel.value = ["XYZ Gauss5.00"]

    def software(q):
        q.scanner.software_versions.value = ["SYNTHETIC-NEWER"]

    def no_model(q):
        q.scanner.manufacturer_model_name = EvidenceField(
            name="manufacturer_model_name", status="MISSING", source="removed"
        )

    def uptake(delta):
        def fn(q):
            if q.acquisition.uptake_interval_s.value is not None:
                q.acquisition.uptake_interval_s.value = (
                    float(q.acquisition.uptake_interval_s.value) + delta
                )

        return fn

    mod("kernel_changed", kernel)
    mod("software_changed", software)
    mod("scanner_model_missing", no_model)
    mod("uptake_plus_5min", uptake(300.0))
    mod("uptake_plus_20min", uptake(1200.0))
    return out


def write_images(out_dir: Path, renderer: Renderer) -> list[Path]:
    (out_dir / "images").mkdir(parents=True, exist_ok=True)
    paths = []
    for ri in renderer.images.values():
        p = out_dir / ri.vgt.path
        p.write_bytes(ri.png)
        paths.append(p)
    return paths
