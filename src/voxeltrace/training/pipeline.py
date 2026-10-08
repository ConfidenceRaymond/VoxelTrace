"""End-to-end DEVELOPMENT dataset build for one case directory (no model involvement)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import voxeltrace
from voxeltrace.evaluation.adversarial import build_adversarial_examples
from voxeltrace.evidence.outputs import write_protocol_outputs
from voxeltrace.ingest import build_case, load_series_volume
from voxeltrace.quant.evidence import quantify_case, write_outputs
from voxeltrace.quant.suv import git_state
from voxeltrace.training.examples import (
    GENERATOR_VERSION,
    SELECTION_RULES,
    Renderer,
    build_examples,
    select_negative_slices,
    select_positive_slices,
    write_images,
)
from voxeltrace.training.export import export_examples
from voxeltrace.training.ground_truth import build_ground_truth, pseudonym
from voxeltrace.training.schema import DatasetManifest
from voxeltrace.training.splits import assign_patient_splits, summarize_splits
from voxeltrace.training.validation import assert_valid
from voxeltrace.visualization import resample_ct_to_pet
from voxeltrace.visualization.render import (
    RENDERER_VERSION,
    compose_grid,
    png_bytes,
    sha256_bytes,
)


def build_case_dataset(
    case_dir: str | Path,
    out_root: str | Path,
    *,
    subject: str,
    dataset: str,
    license: str,
    citation: str | None,
    evidence_dir: str | Path,
    audit_dir: str | Path | None = None,
    all_subjects: list[str] | None = None,
) -> dict[str, Any]:
    case_dir, out_root, evidence_dir = Path(case_dir), Path(out_root), Path(evidence_dir)
    case = build_case(case_dir, dataset=dataset, subject_id=subject)
    run = quantify_case(case, dataset=dataset, subject=subject)
    if not run.passed:
        raise ValueError(
            "strict SUV refused; no dataset generated for this case: "
            + ", ".join(r.code for r in run.evidence.refusal_reasons)
        )
    ev_files = write_outputs(run, evidence_dir)
    proto_files, proto = write_protocol_outputs(run, evidence_dir)
    evidence_files = {p.name: str(p) for p in ev_files + proto_files if p.suffix == ".json"}

    pet = case.get_series(run.pet_series_uid or "")
    ct_on_pet = None
    cts = [
        s
        for s in case.series_by_category("CT")
        if s.frame_of_reference_uids == pet.frame_of_reference_uids
    ]
    if len(cts) == 1:
        ct = load_series_volume(cts[0])
        ct_on_pet = resample_ct_to_pet(
            ct.array,
            ct.geometry,
            run.outcome.activity.geometry,
            cts[0].frame_of_reference_uids[0],
            pet.frame_of_reference_uids[0],
        )
    sha, dirty = git_state()
    provenance = {
        "generator": GENERATOR_VERSION,
        "renderer": RENDERER_VERSION,
        "voxeltrace_version": voxeltrace.__version__,
        "git_commit": sha,
        "git_dirty": dirty,
        "dataset": dataset,
        "license": license,
    }
    gtc, arrays = build_ground_truth(
        run,
        proto["protocol"],
        proto["claims"],
        dataset=dataset,
        license=license,
        citation=citation,
        ct_on_pet=ct_on_pet,
        evidence_files=evidence_files,
        provenance=provenance,
    )
    split = assign_patient_splits(all_subjects or [subject])[subject]
    evidence_text = Path(evidence_files["evidence.json"]).read_text()
    renderer = Renderer(gtc, arrays, evidence_text)
    excluded: list[tuple[int, str, str]] = []
    positives = select_positive_slices(gtc, excluded)
    # "No reference-segmented target" may only be asserted when the reference SEG was actually
    # decoded (possibly empty). A missing or refused SEG never yields negative labels.
    seg_decoded = run.seg is not None and run.seg_masks is not None
    negatives = select_negative_slices(arrays) if ct_on_pet is not None and seg_decoded else []
    examples = build_examples(
        gtc,
        renderer,
        run.evidence,
        proto["protocol"],
        proto["claims"],
        split,
        {**provenance, "evidence_sha256": gtc.evidence_sha256},
        negatives,
        positives,
    )
    examples += build_adversarial_examples(
        gtc,
        run.evidence,
        proto["protocol"],
        split,
        {**provenance, "evidence_sha256": gtc.evidence_sha256},
    )
    out_dir = out_root / subject
    out_dir.mkdir(parents=True, exist_ok=True)
    write_images(out_dir, renderer)
    gtc.images = [ri.vgt for ri in renderer.images.values()]
    (out_dir / "ground_truth.json").write_text(gtc.model_dump_json(indent=2) + "\n")
    exports = export_examples(examples, out_dir)

    contact = None
    if audit_dir is not None and gtc.quantitative.lesions:
        contact = _contact_sheet(renderer, gtc, positives + excluded, Path(audit_dir), subject)

    counts = Counter(e.example_class for e in examples)
    manifest = DatasetManifest(
        dataset_name=f"voxeltrace-dev-{subject}",
        purpose="DEVELOPMENT_ONLY: pipeline testing and model evaluation smoke tests. NOT a "
        "training set; not suitable for fine-tuning (single subject).",
        fine_tuning_suitable=False,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        voxeltrace_version=voxeltrace.__version__,
        git_commit=sha,
        git_dirty=dirty,
        renderer_version=RENDERER_VERSION,
        renderer_defaults={
            "full_scale": 2,
            "crop_scale": 6,
            "crop_mm": 80,
            "suv_window": [0, 8],
            "ct_window_center_width": [40, 400],
            "convention": "radiological",
        },
        sources=[
            {
                "dataset": dataset,
                "subject_pseudonym": subject,
                "study_pseudonym": gtc.study_pseudonym,
                "pet_series_pseudonym": gtc.pet_series_pseudonym,
                "seg_series_pseudonym": gtc.seg_series_pseudonym,
                "ct_series_pseudonym": pseudonym(cts[0].series_uid, "ct") if cts else None,
                "license": license,
                "citation": citation,
            }
        ],
        images=[
            {
                "path": v.path,
                "sha256": v.sha256,
                "view": v.view,
                "slice_k": v.slice_k,
                "role": renderer.images[v.image_id].role,
                "contains_segmented_target": v.contains_segmented_target,
                "render_params": v.render_params,
            }
            for v in gtc.images
        ],
        evidence_sha256=gtc.evidence_sha256,
        splits=summarize_splits(examples),
        example_counts=dict(sorted(counts.items())),
        label_provenance={
            str(k): v for k, v in sorted(Counter(e.ground_truth_level for e in examples).items())
        },
        selection_rules=SELECTION_RULES,
        notes=[
            "Images are PNG derivatives of CC BY 4.0 data; keep under the project root; "
            "never commit to Git.",
            "Negative slices mean 'no reference-segmented target', not 'normal'.",
            "Synthetic perturbations are flagged per example (synthetic_perturbation).",
            f"reference segmentation decoded: {seg_decoded} (negatives only if decoded)",
            "QC-excluded positive slices (reference mask over zero PET): "
            + (", ".join(f"k={e[0]}" for e in excluded) or "none"),
        ],
    )
    (out_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")
    forbidden = [
        case_uid
        for case_uid in {
            pet.study_uid,
            pet.series_uid,
            run.seg.series_uid if run.seg else "",
            *(s.series_uid for s in cts),
            *pet.frame_of_reference_uids,
        }
        if case_uid
    ]
    assert_valid(out_dir, examples, [gtc], forbidden_strings=forbidden)
    for p in exports.values():  # exported files must not contain raw UIDs either
        text = p.read_text()
        leaked = [u for u in forbidden if u in text]
        if leaked:
            raise RuntimeError(f"raw UID leaked into export {p.name}")
    return {
        "out_dir": out_dir,
        "examples": examples,
        "ground_truth": gtc,
        "manifest": manifest,
        "contact_sheet": contact,
        "positives": positives,
        "negatives": negatives,
        "excluded": excluded,
    }


def _contact_sheet(renderer: Renderer, gtc, positives, audit_dir: Path, subject: str) -> Path:
    rows = []
    # P1, P2, then P3 components; QC-excluded slices last (shown for human review)
    priority = sorted(positives, key=lambda p: ("excluded" in p[2], p[2][:2], p[0]))
    priority = [p for p in priority if "excluded" not in p[2]][:3] + [
        p for p in priority if "excluded" in p[2]
    ][:2]
    for k, lid, rule in priority:
        row = []
        for view, outline, markers, label in (
            ("pet", False, False, "PET"),
            ("ct", False, False, "CT"),
            ("fused", False, False, "PET/CT"),
            ("suvheat", False, False, "SUV heat map"),
            ("pet", True, False, "segmentation"),
            ("pet", True, True, "SUVmax + SUVpeak"),
        ):
            ri = renderer.axial(
                view,
                k,
                lesion_id=lid,
                crop=True,
                outline=outline,
                markers=markers,
                boxes=False,
                show_values=markers,
                role="audit",
            )
            row.append((f"k={k} {label} ({rule})", ri.rgb))
        rows.append(row)
    sheet = compose_grid(
        rows,
        title=f"VoxelTrace visual audit {subject} - RESEARCH PROTOTYPE, "
        "NOT FOR CLINICAL DIAGNOSIS - human review only",
    )
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / f"{subject}_contact_sheet.png"
    data = png_bytes(sheet)
    path.write_bytes(data)
    (audit_dir / f"{subject}_contact_sheet.json").write_text(
        json.dumps(
            {
                "sha256": sha256_bytes(data),
                "slices": priority,
                "columns": [
                    "PET",
                    "CT",
                    "PET/CT",
                    "SUV heat map",
                    "segmentation",
                    "SUVmax + SUVpeak",
                ],
                "note": "derived medical images: keep local, never commit",
            },
            indent=2,
        )
        + "\n"
    )
    return path
