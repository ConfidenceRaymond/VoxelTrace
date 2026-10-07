#!/usr/bin/env python3
"""Inspect a local PET/CT(/SEG) case directory. Deterministic; no AI; no SUV.

Usage:
    python scripts/inspect_case.py /path/to/case [--json] [--load-pixels] [--mask m.nii.gz]
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from voxeltrace.ingest import IngestError, build_case, decode_dicom_seg, load_series_volume
from voxeltrace.quant import compute_image_stats
from voxeltrace.schemas import VoxelTraceCase


def _fmt(v: Any, nd: int = 4) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{nd}g}"
    if isinstance(v, tuple | list):
        return "(" + ", ".join(_fmt(x, nd) for x in v) + ")"
    return str(v)


def load_pixels(case: VoxelTraceCase) -> dict[str, Any]:
    """Load PET/CT volumes and decode DICOM SEG. Returns a JSON-safe summary."""
    out: dict[str, Any] = {"volumes": {}, "segmentations": {}}
    for s in case.series:
        if s.category not in ("PET", "CT"):
            continue
        try:
            vol = load_series_volume(s)
        except IngestError as exc:
            out["volumes"][s.series_uid] = {"error": str(exc)}
            continue
        out["volumes"][s.series_uid] = {
            "array_shape_kji": list(vol.array.shape),
            "rescaled": vol.rescaled,
            "stats": compute_image_stats(vol.array).model_dump(),
        }
    for seg in case.segmentations:
        if seg.source != "DICOM_SEG":
            continue
        results = {}
        for ref_uid in seg.referenced_series_uids:
            try:
                ref = case.get_series(ref_uid)
                dec = decode_dicom_seg(seg.path, ref)
            except (KeyError, IngestError) as exc:
                results[ref_uid] = {"error": str(exc)}
                continue
            seg.pixel_decoding = "DECODED"
            seg.geometry_matches_reference = True
            results[ref_uid] = {
                "voxels_per_segment": {str(n): int(m.sum()) for n, m in dec.masks.items()}
            }
        if results and all("error" in r for r in results.values()):
            seg.pixel_decoding = "REFUSED"
        out["segmentations"][seg.series_uid or seg.path] = results
    return out


def render_text(case: VoxelTraceCase, pixels: dict[str, Any] | None) -> str:
    p = case.provenance
    lines: list[str] = []
    h = lines.append

    h("CASE")
    h(f"  source:        {p.source_path}")
    h(
        f"  dataset:       {_fmt(p.dataset)}   collection: {_fmt(p.collection)}   "
        f"subject: {_fmt(p.subject_id)}"
    )
    h(
        f"  files scanned: {p.files_scanned}  dicom: {p.dicom_files}  "
        f"non-dicom ignored: {p.non_dicom_files_ignored}  unreadable: {p.unreadable_files}"
    )
    h(f"  inspected:     {p.inspected_at}  (voxeltrace {p.voxeltrace_version})")
    h("  NOTE: research prototype; no SUV calculated.")

    h("\nSTUDIES")
    for st in case.studies:
        h(f"  {st.study_uid}  '{_fmt(st.study_description)}'  series={len(st.series_uids)}")

    h("\nSERIES")
    for s in case.series:
        h(
            f"  [{s.category:5}] modality={_fmt(s.modality)} #{_fmt(s.series_number)} "
            f"'{_fmt(s.series_description)}' instances={s.instance_count} "
            f"matrix={_fmt(s.rows)}x{_fmt(s.columns)} frames={_fmt(s.number_of_frames)}"
        )
        h(f"          uid={s.series_uid}")
        h(
            f"          scanner={_fmt(s.manufacturer)} / {_fmt(s.manufacturer_model_name)} "
            f"sw={_fmt(s.software_versions)}"
        )

    h("\nPET METADATA  (as recorded; no unit conversion, no defaults)")
    if not case.pet_metadata:
        h("  none")
    for uid, m in case.pet_metadata.items():
        h(f"  series {uid}")
        for label, val in [
            ("Units", m.units),
            ("DecayCorrection", m.decay_correction),
            ("CorrectedImage", m.corrected_image),
            ("PatientWeight [kg]", m.patient_weight),
            ("SeriesDate/Time", f"{_fmt(m.series_date)} {_fmt(m.series_time)}"),
            ("AcquisitionDate/Time", f"{_fmt(m.acquisition_date)} {_fmt(m.acquisition_time)}"),
            ("Radiopharmaceutical", m.radiopharmaceutical),
            ("RadionuclideTotalDose [Bq]", m.radionuclide_total_dose),
            ("RadionuclideHalfLife [s]", m.radionuclide_half_life),
            ("RadiopharmStartTime", m.radiopharmaceutical_start_time),
            ("RadiopharmStartDateTime", m.radiopharmaceutical_start_datetime),
            (
                "RescaleSlope (distinct)",
                f"{len(m.rescale_slopes)} value(s) {_fmt(m.rescale_slopes[:3])}",
            ),
            ("RescaleIntercept (distinct)", _fmt(m.rescale_intercepts[:3])),
            ("ReconstructionMethod", m.reconstruction_method),
            ("ReconstructionDiameter", m.reconstruction_diameter),
        ]:
            h(f"    {label:28} {_fmt(val, 8)}")

    h("\nGEOMETRY  (i=column, j=row, k=slice; DICOM affine in LPS mm)")
    if not case.geometries:
        h("  none")
    for uid, g in case.geometries.items():
        cat = case.get_series(uid).category
        h(f"  [{cat}] {uid}")
        h(
            f"    shape_ijk={_fmt(g.shape_ijk)} spacing_mm={_fmt(g.spacing_ijk)} "
            f"uniform_k={_fmt(g.uniform_slice_spacing)}"
        )
        h(f"    origin={_fmt(g.origin)} extent_mm={_fmt(g.extent_mm)}")
        h(f"    direction={_fmt(g.direction, 3)}")

    h("\nSEGMENTATIONS")
    if not case.segmentations:
        h("  none")
    for sg in case.segmentations:
        h(
            f"  [{sg.source}] type={_fmt(sg.segmentation_type)} frames={_fmt(sg.number_of_frames)}"
            f" pixel_decoding={sg.pixel_decoding}"
            f" geometry_match={_fmt(sg.geometry_matches_reference)}"
        )
        h(f"    references={sg.referenced_series_uids or '—'}")
        for seg in sg.segments:
            h(
                f"    segment {seg.number}: label={_fmt(seg.label)} type={_fmt(seg.type)} "
                f"category={_fmt(seg.category)} algorithm={_fmt(seg.algorithm_type)}"
            )
        if sg.label_values is not None:
            h(f"    label values={sg.label_values} counts={sg.label_voxel_counts}")

    if pixels is not None:
        h("\nPIXELS  (stored * RescaleSlope + RescaleIntercept; source units)")
        for uid, v in pixels["volumes"].items():
            if "error" in v:
                h(f"  {uid}: NOT LOADED: {v['error']}")
                continue
            s = v["stats"]
            h(
                f"  {uid}: array[k,j,i]={v['array_shape_kji']} finite={s['finite_count']} "
                f"min={_fmt(s['finite_min'])} max={_fmt(s['finite_max'])} "
                f"mean={_fmt(s['finite_mean'])} p99={_fmt(s['p99'])}"
            )
        for uid, res in pixels["segmentations"].items():
            h(f"  SEG {uid}: {json.dumps(res)}")

    h("\nMISSING METADATA")
    if not case.missing:
        h("  none")
    for m in case.missing:
        raw = f" raw='{m.raw_value}'" if m.raw_value is not None else ""
        h(
            f"  {'REQUIRED' if m.required else 'optional'} {m.field}: {m.status}{raw}"
            f" ({m.scope[-12:]}){' - ' + m.note if m.note else ''}"
        )

    h("\nWARNINGS")
    if not case.warnings:
        h("  none")
    for w in case.warnings:
        where = w.series_uid[-12:] if w.series_uid else (w.path or "")
        h(f"  {w.severity.upper():7} {w.code}: {w.message} [{where}]")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", help="case directory (searched recursively)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    ap.add_argument(
        "--load-pixels", action="store_true", help="also load PET/CT volumes and decode DICOM SEG"
    )
    ap.add_argument("--mask", action="append", default=[], help="NIfTI mask (repeatable)")
    ap.add_argument("--dataset")
    ap.add_argument("--collection")
    ap.add_argument("--subject")
    args = ap.parse_args(argv)

    case = build_case(
        args.path,
        dataset=args.dataset,
        collection=args.collection,
        subject_id=args.subject,
        nifti_masks=args.mask,
    )
    pixels = load_pixels(case) if args.load_pixels else None
    if args.json:
        payload = json.loads(case.model_dump_json(exclude={"series": {"__all__": {"instances"}}}))
        if pixels is not None:
            payload["pixels"] = pixels
        print(json.dumps(payload, indent=2))
    else:
        print(render_text(case, pixels))
    return 1 if any(w.code == "ROOT_NOT_A_DIRECTORY" for w in case.warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
