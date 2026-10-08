#!/usr/bin/env python3
"""First REAL longitudinal validation: ACRIN-NSCLC-FDG-PET-094 and -153 (no AI).

Inputs: ../data/acrin_longitudinal/<subject>/<baseline|followup>/{PET,CT} (bounded download).
Outputs: ../outputs/acrin_longitudinal/
  trial/                          trial.yaml + read-only links (distinct review namespace)
  ingestion.json                  per-timepoint ingestion validation (stops if any fails)
  suv_sul.json                    strict SUVbw and SUL per timepoint
  protocol_fingerprints.json      normalized fingerprint per scan + baseline->follow-up diff
  audit_<ruleset>/                full audit exports (QIBA, PERCIST, EANM)
  pair_rules.csv                  every rule x pair x rule set, with review dependence
  census_crosscheck.csv           census PREDICTED vs ACTUAL
  reference_review/               QC images + worksheet for the NEW real proposals; the
                                  review file (reference_review.yaml) is created only by a
                                  human on the review page. No decision is created here.
  ACRIN_LONGITUDINAL_REPORT.md
"""

from __future__ import annotations

import csv
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pydicom
import yaml

from voxeltrace.config import REPO_ROOT
from voxeltrace.evidence.comparability import compare_protocols
from voxeltrace.evidence.outputs import protocol_for_run
from voxeltrace.ingest import build_case
from voxeltrace.ingest.dicom import load_series_volume
from voxeltrace.quant.evidence import input_audit, quantify_case
from voxeltrace.quant.sul import compute_sul
from voxeltrace.trial.audit import run_trial_audit
from voxeltrace.trial.export import export_audit

HACK = REPO_ROOT.parent
DATA = HACK / "data" / "acrin_longitudinal"
OUT = HACK / "outputs" / "acrin_longitudinal"
CENSUS = HACK / "data" / "census" / "acrin_nsclc_fdg_pet"
CENSUS_V2 = HACK / "data" / "census" / "acrin_nsclc_fdg_pet_v2"
SUBJECTS: tuple[str, ...] = ("ACRIN-NSCLC-FDG-PET-094", "ACRIN-NSCLC-FDG-PET-153")
TRIAL_ID = "ACRIN-NSCLC-FDG-PET-LONGITUDINAL-1"
TPS = ("baseline", "followup")
RULESETS = ("percist-1.0", "qiba-fdg-1.14", "eanm-fdg-2.0")
REVIEW_REASONS = {
    "REFERENCE_REVIEW_REQUIRED",
    "REFERENCE_AUTO_NOT_FOUND",
    "REFERENCE_REVIEW_OUTDATED",
    "REFERENCE_REVIEW_INVALID",
    "REFERENCE_REJECTED_BY_REVIEWER",
    "REFERENCE_QC_FAILED",
    "MANUAL_OR_REFERENCE_MASK_REQUIRED",
}


def pet_uid(subject: str, tp: str) -> str:
    """SeriesInstanceUID of the downloaded PET series (read from the files)."""
    f = next((DATA / subject / tp / "PET").glob("*.dcm"))
    return str(pydicom.dcmread(f, stop_before_pixels=True).SeriesInstanceUID)


def blocked_by(c) -> str:
    """Why a non-PASS rule is unresolved: SUV_REFUSED (no validated quantitation),
    REFERENCE_REVIEW (a human reference decision is pending), or the rule's own evidence."""
    if c.status == "PASS":
        return ""
    codes = {r.code for r in c.reasons}
    details = " ".join(r.detail for r in c.reasons)
    if codes & {"SUV_REFUSED", "INCONSISTENT_METADATA"} or "no quantitative SUV" in details:
        return "SUV_REFUSED"
    if codes & REVIEW_REASONS:
        return "REFERENCE_REVIEW"
    return "OWN_EVIDENCE:" + ";".join(sorted(codes))


def proposals_without_suv(subject: str, tp: str, qc_dir: Path) -> list[dict]:
    """CT-guided proposals for REAL scans whose strict SUV was refused (the audit does not
    propose regions it cannot measure). Same proposer and hash as the audit; CT-only QC
    renders; NO measurement and NO decision."""
    from voxeltrace.quant.reference_auto import propose_reference_regions
    from voxeltrace.training.ground_truth import pseudonym
    from voxeltrace.visualization.reference_qc import render_proposal_qc

    case = build_case(DATA / subject / tp, subject_id=subject)
    (pet,) = case.series_by_category("PET")
    pet_for = set(pet.frame_of_reference_uids)
    cts = [c for c in case.series_by_category("CT") if set(c.frame_of_reference_uids) == pet_for]
    base = {"subject": subject, "timepoint": tp, "pet_series": pseudonym(pet.series_uid, "pet")}
    if len(cts) != 1:
        why = "no CT series shares the PET FrameOfReferenceUID"
        return [
            {**base, "region": r, "status": "AUTO_NOT_FOUND", "reason": why}
            for r in ("LIVER", "BLOOD_POOL")
        ]
    ct = load_series_volume(cts[0])
    props, work = propose_reference_regions(
        ct.array,
        ct.geometry,
        pet_series_pseudonym=base["pet_series"],
        ct_series_pseudonym=pseudonym(cts[0].series_uid, "ct"),
    )
    out = []
    for region, p in props.items():
        row = {**base, "region": region, "status": p.status, "reason": p.failure_reason}
        if p.status == "PROPOSED" and work is not None:
            qc_dir.mkdir(parents=True, exist_ok=True)
            name = f"{subject}_{tp}_{region}.png"
            (qc_dir / name).write_bytes(
                render_proposal_qc(work, p, title=f"{subject} {tp} {region} (REAL; SUV refused)")
            )
            row.update(
                proposal_sha256=p.sha256,
                method=p.method,
                centre_patient_mm=list(p.centre_patient_mm),
                diameter_mm=p.diameter_mm,
                length_mm=p.length_mm,
                ct_hu_mean=round(p.qc.get("ct_hu_mean", float("nan")), 1),
                qc_image=f"qc/{name}",
            )
        out.append(row)
    return out


def ev(f) -> dict:
    v = f.value
    if isinstance(v, tuple):
        v = list(v)
    return {"value": v, "status": f.status, "source": f.source}


def ingestion(subject: str, tp: str) -> dict:
    d = DATA / subject / tp
    case = build_case(d, subject_id=subject)
    pets = case.series_by_category("PET")
    cts = case.series_by_category("CT")
    r: dict = {
        "subject": subject,
        "timepoint": tp,
        "series": {s.category: len(case.series_by_category(s.category)) for s in case.series},
        "case_warnings": [f"{w.code}: {w.message}" for w in case.warnings],
    }
    ok = len(pets) == 1
    for name, series in (("PET", pets), ("CT", cts)):
        if not series:
            r[name] = {"present": False}
            continue
        (s,) = series
        vol = load_series_volume(s)
        g = vol.geometry
        r[name] = {
            "present": True,
            "loaded": True,
            "shape_kji": list(vol.array.shape),
            "spacing_ijk_mm": list(g.spacing_ijk),
            "uniform_slice_spacing": g.uniform_slice_spacing,
            "slice_order_unambiguous": not any(w.severity == "error" for w in vol.warnings),
            "load_warnings": [f"{w.code}: {w.message}" for w in vol.warnings],
            "frame_of_reference_uids": s.frame_of_reference_uids,
            "value_range": [float(np.min(vol.array)), float(np.max(vol.array))],
        }
        ok &= r[name]["slice_order_unambiguous"] and g.spacing_ijk[2] is not None
    if pets and cts:
        r["pet_ct_same_frame_of_reference"] = set(pets[0].frame_of_reference_uids) == set(
            cts[0].frame_of_reference_uids
        )
    r["ingestion_ok"] = bool(ok)
    return r


def suv_sul(subject: str, tp: str) -> tuple[dict, dict]:
    d = DATA / subject / tp
    case = build_case(d, subject_id=subject)
    run = quantify_case(case, subject=subject)
    e = run.evidence
    q = e.quantitative_inputs
    out = {
        "subject": subject,
        "timepoint": tp,
        "suv_status": e.measured.suv_status,
        "refusal_reasons": [f"{r.code}: {r.message}" for r in e.refusal_reasons],
        "units": q.units,
        "decay_correction": q.decay_correction,
        "corrected_image": q.corrected_image,
        "weight_kg": q.patient_weight_kg,
        "dose_bq": q.radionuclide_total_dose_bq,
        "half_life_s": q.radionuclide_half_life_s,
        "uptake_interval_min": round(q.decay_interval_s / 60, 3) if q.decay_interval_s else None,
        "injection_datetime_source": q.injection_datetime_source,
        "scan_reference_datetime_source": q.scan_reference_datetime_source,
        "suv_per_bqml": e.scale_factors.suv_per_bqml if e.scale_factors else None,
    }
    src = (run.outcome.result or run.outcome.refusal) if run.outcome else None
    codes = [r.code for r in src.validation.reasons] if src else []
    warns = [w.code for w in src.validation.warnings] if src else []
    out["suv_warning_codes"] = warns
    if "DECAY_FACTOR_INCONSISTENT" in codes:
        out["decay_factor_crosscheck"] = "FAILED"
    elif "DECAY_FACTOR_UNVERIFIED" in warns:
        out["decay_factor_crosscheck"] = "NOT_AVAILABLE"
        out["quantitative_warning"] = "STORED_DECAY_FACTOR_NOT_AVAILABLE"
    elif src is not None and any(
        c.name == "Vendor decay factor" and c.passed for c in src.validation.checks
    ):
        out["decay_factor_crosscheck"] = "VERIFIED"
    else:
        out["decay_factor_crosscheck"] = "NOT_EVALUATED (validator stopped before this check)"
    hs = [
        pydicom.dcmread(i.path, stop_before_pixels=True)
        for i in run.case.get_series(run.pet_series_uid or "").instances
    ]
    out["decay_tags_present"] = {
        "DecayFactor": sum(h.get("DecayFactor") is not None for h in hs),
        "FrameReferenceTime": sum(h.get("FrameReferenceTime") is not None for h in hs),
        "slices": len(hs),
    }
    st = e.measured.suv_volume_stats
    if st is not None:
        out["suv_range"] = [st.finite_min, st.finite_max]
        out["suv_mean_whole_volume"] = st.finite_mean
    pet = case.get_series(run.pet_series_uid or "")
    headers = [pydicom.dcmread(i.path, stop_before_pixels=True) for i in pet.instances]
    out["anthropometrics"] = {
        "PatientWeight": str(headers[0].get("PatientWeight")),
        "PatientSize": str(headers[0].get("PatientSize")),
        "PatientSex": str(headers[0].get("PatientSex")),
    }
    out["sul"] = {}
    if run.passed and run.outcome and run.outcome.result:
        for f in ("LBMJAMES128", "LBMJANMA"):
            s = compute_sul(run.outcome.result, headers, f)  # type: ignore[arg-type]
            out["sul"][f] = {
                "status": s.status,
                "lbm_kg": s.lbm_kg,
                "refusals": [f"{r.code}: {r.message}" for r in s.refusals],
            }
    proto, _ = protocol_for_run(run)
    sc, ac, rc, co = proto.scanner, proto.acquisition, proto.reconstruction, proto.corrections
    fp = {
        "manufacturer": ev(sc.manufacturer),
        "model": ev(sc.manufacturer_model_name),
        "software": ev(sc.software_versions),
        "tracer": ev(ac.tracer),
        "radionuclide": ev(ac.radionuclide),
        "matrix": [ev(ac.matrix_rows), ev(ac.matrix_columns)],
        "voxel_size_mm": ev(rc.voxel_size_mm),
        "slice_thickness_mm": ev(rc.slice_thickness_mm),
        "reconstruction_description": ev(rc.reconstruction_method),
        "algorithm_family": ev(rc.algorithm_family),
        "iterations": ev(rc.iterations),
        "subsets": ev(rc.subsets),
        "time_of_flight": ev(rc.time_of_flight),
        "psf": ev(rc.psf_resolution_modelling),
        "convolution_kernel": ev(rc.convolution_kernel),
        "filter": ev(rc.filter_type),
        "post_filter_width": ev(rc.post_filter_gaussian_width),
        "corrected_image": ev(co.corrected_image),
        "decay_correction": ev(co.decay_correction),
        "attenuation_correction_method": ev(co.attenuation_correction_method),
        "scatter_correction_method": ev(co.scatter_correction_method),
        "uptake_interval_s": ev(ac.uptake_interval_s),
        "injected_dose_bq": ev(ac.injected_activity_bq),
        "units": ev(ac.image_units),
        "harmonization": {
            "value": None,
            "status": "UNKNOWN",
            "source": "not encoded in DICOM; no trial configuration declares EARL/harmonization",
        },
        "unsupported_private_metadata": rc.unsupported_private_metadata,
    }
    out["quant_input_fields"] = [
        {
            "field": f["name"],
            "tag": f["tag"],
            "present_slices": f"{f['slices_present']}/{f['slices_total']}",
            "n_distinct": f["n_distinct"],
            "value": f["value"],
        }
        for f in input_audit(run)["fields"]
    ]
    return out, {"fingerprint": fp, "protocol": proto}


def diff(a: dict, b: dict) -> dict:
    out = {}
    for k in a:
        if k in ("unsupported_private_metadata",):
            continue
        va, vb = a[k], b[k]
        if isinstance(va, list):
            va = [x["value"] for x in va]
            vb = [x["value"] for x in vb]
            sa = sb = "PRESENT"
        else:
            sa, sb = va["status"], vb["status"]
            va, vb = va["value"], vb["value"]
        if sa != "PRESENT" or sb != "PRESENT":
            out[k] = {"result": "UNKNOWN", "baseline": va, "followup": vb, "status": [sa, sb]}
        elif k in ("uptake_interval_s", "injected_dose_bq"):
            out[k] = {
                "result": "EQUAL" if va == vb else "DIFFERENT",
                "baseline": va,
                "followup": vb,
            }
        else:
            out[k] = {"result": "SAME" if va == vb else "DIFFERENT", "baseline": va, "followup": vb}
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse

    global OUT, SUBJECTS, TRIAL_ID
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", nargs="+", default=list(SUBJECTS))
    ap.add_argument("--out-name", default="acrin_longitudinal")
    ap.add_argument("--trial-id", default=TRIAL_ID)
    a = ap.parse_args(argv)
    SUBJECTS, OUT, TRIAL_ID = tuple(a.subjects), HACK / "outputs" / a.out_name, a.trial_id
    OUT.mkdir(parents=True, exist_ok=True)
    # ---------------------------------------------------------------- 1. ingestion
    ing = [ingestion(s, t) for s in SUBJECTS for t in TPS]
    (OUT / "ingestion.json").write_text(json.dumps(ing, indent=2, default=str) + "\n")
    if not all(r["ingestion_ok"] for r in ing):
        print("STOP: ingestion checks failed", json.dumps(ing, indent=1, default=str))
        return 2
    print("ingestion OK for all four timepoints")
    # ---------------------------------------------------------------- 2. SUV / SUL / fingerprint
    res, fps, protos = [], {}, {}
    for s in SUBJECTS:
        for t in TPS:
            r, f = suv_sul(s, t)
            res.append(r)
            fps[(s, t)] = f["fingerprint"]
            protos[(s, t)] = f["protocol"]
    (OUT / "suv_sul.json").write_text(json.dumps(res, indent=2, default=str) + "\n")
    fp_doc = {}
    for s in SUBJECTS:
        b, f = protos[(s, "baseline")], protos[(s, "followup")]
        cmp = compare_protocols(b, f)
        fp_doc[s] = {
            "baseline": fps[(s, "baseline")],
            "followup": fps[(s, "followup")],
            "diff": diff(fps[(s, "baseline")], fps[(s, "followup")]),
            "protocol_comparability": {
                "category": cmp.category,
                "blocking_differences": cmp.blocking_differences,
                "blocking_unknowns": cmp.blocking_unknowns,
                "warnings": cmp.warnings,
            },
        }
    (OUT / "protocol_fingerprints.json").write_text(
        json.dumps(fp_doc, indent=2, default=str) + "\n"
    )
    # ---------------------------------------------------------------- 3. trial audits
    trial = OUT / "trial"
    trial.mkdir(exist_ok=True)
    for s in SUBJECTS:
        (trial / s).mkdir(exist_ok=True)
        for t in TPS:
            link = trial / s / t
            if not link.exists():
                link.symlink_to(DATA / s / t, target_is_directory=True)
    rv_dir = OUT / "reference_review"
    rv_dir.mkdir(exist_ok=True)
    (trial / "trial.yaml").write_text(
        yaml.safe_dump(
            {
                "trial_id": TRIAL_ID,
                "ruleset": "percist-1.0",
                "timepoint_order": list(TPS),
                "reference_proposals": "auto",
                "reference_review_file": "../reference_review/reference_review.yaml",
                "note": "REAL public data (ACRIN 6668 via IDC, CC BY 3.0). Reviews of these "
                "real proposals live ONLY in reference_review/reference_review.yaml, written by "
                "a human on the review page.",
            },
            sort_keys=False,
        )
    )
    if (rv_dir / "reference_review.yaml").exists():
        print("note: a human review file exists and will be consumed read-only")
    audits = {}
    for rs in RULESETS:
        a = run_trial_audit(trial, ruleset=rs, qc_dir=rv_dir / "qc")
        export_audit(a, OUT / f"audit_{rs}")
        audits[rs] = a
    shutil.copy(
        OUT / "audit_percist-1.0" / "reference_review_worksheet.yaml",
        rv_dir / "reference_review_worksheet.yaml",
    )
    rows = []
    for rs, a in audits.items():
        for p in a.pairs:
            for c in p.checks:
                codes = sorted({r.code for r in c.reasons})
                rows.append(
                    {
                        "subject": p.pair.subject_id,
                        "ruleset": rs,
                        "pair_verdict": p.verdict,
                        "rule_id": c.rule_id,
                        "impact": c.impact,
                        "status": c.status,
                        "observed": json.dumps(c.observed, default=str),
                        "condition": c.expected,
                        "reason_codes": ";".join(codes),
                        "blocked_by": blocked_by(c),
                        "reason_detail": " | ".join(dict.fromkeys(r.detail for r in c.reasons))[
                            :300
                        ],
                    }
                )
    with (OUT / "pair_rules.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    # ---------------------------------------------------------------- 4. census cross-check
    cand = {r["PatientID"]: r for r in csv.DictReader((CENSUS / "candidate_pairs.csv").open())}
    risk = {
        r["SeriesInstanceUID"]: r for r in csv.DictReader((CENSUS / "pet_series_risk.csv").open())
    }
    cc = []
    by = {(r["subject"], r["timepoint"]): r for r in res}
    ig = {(r["subject"], r["timepoint"]): r for r in ing}
    for s in SUBJECTS:
        c = cand[s]
        for t in TPS:
            pr = risk[pet_uid(s, t)]
            act = by[(s, t)]
            fpt = fps[(s, t)]
            sul_ok = act["sul"].get("LBMJAMES128", {}).get("status")
            cc.append(
                {
                    "subject": s,
                    "timepoint": t,
                    "scanner_predicted": pr["Manufacturer"],
                    "scanner_actual": fpt["manufacturer"]["value"],
                    "model_predicted": pr["Model"],
                    "model_actual": fpt["model"]["value"],
                    "height_predicted": pr["has_height"],
                    "height_actual": act["anthropometrics"]["PatientSize"] not in ("None", ""),
                    "recon_predicted": pr["ReconstructionMethod"] or pr["ConvolutionKernel"],
                    "recon_actual": fpt["reconstruction_description"]["value"],
                    "iterations_actual": fpt["iterations"]["value"],
                    "subsets_actual": fpt["subsets"]["value"],
                    "ct_predicted": "CT in study (frame of reference not checked)",
                    "ct_actual": (
                        "CT in PET frame of reference"
                        if ig[(s, t)].get("pet_ct_same_frame_of_reference")
                        else "no CT downloaded (study CTs not in the PET frame of reference)"
                        if not ig[(s, t)]["CT"]["present"]
                        else "CT present, different frame of reference"
                    ),
                    "suv_predicted": pr["risk"],
                    "suv_actual": act["suv_status"],
                    "sul_actual": sul_ok,
                    "ii_predicted": pr["ii_reasons"] or pr["warnings"],
                }
            )
    with (OUT / "census_crosscheck.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cc[0]))
        w.writeheader()
        w.writerows(cc)
    # ---------------------------------------------------------------- 4b. census v2 vs actual
    v2_pet = {
        json.loads(x)["SeriesInstanceUID"]: json.loads(x)
        for x in (CENSUS_V2 / "pet_series_v2_enriched.jsonl").read_text().splitlines()
    }
    v2_pairs = {r["PatientID"]: r for r in csv.DictReader((CENSUS_V2 / "pairs_v2.csv").open())}
    v2rows = []
    for s in SUBJECTS:
        pr = v2_pairs.get(s)
        for t in TPS:
            act = by[(s, t)]
            p2 = v2_pet.get(pet_uid(s, t), {})
            sul_act = act["sul"].get("LBMJAMES128", {}).get("status", "NOT_ATTEMPTED")
            v2rows.append(
                {
                    "subject": s,
                    "timepoint": t,
                    "suv_v2": "PASS" if p2.get("suv_eligible") else "REFUSED",
                    "suv_actual": act["suv_status"],
                    "suv_refusal_v2": ";".join(p2.get("refusal_codes", [])),
                    "suv_refusal_actual": ";".join(x.split(":")[0] for x in act["refusal_reasons"]),
                    "decay_crosscheck_v2": (
                        "FAILED"
                        if "DECAY_FACTOR_INCONSISTENT" in p2.get("refusal_codes", [])
                        else "NOT_AVAILABLE"
                        if "DECAY_FACTOR_UNVERIFIED" in p2.get("warning_codes", [])
                        else "VERIFIED_ON_SAMPLE"
                    ),
                    "decay_crosscheck_actual": act["decay_factor_crosscheck"],
                    "sul_v2": "LIKELY_PASS"
                    if p2.get("height_present")
                    else "LIKELY_REFUSE (no height)",
                    "sul_actual": sul_act,
                    "ct_for_v2": p2.get("ct_same_for"),
                    "ct_for_actual": ig[(s, t)].get("pet_ct_same_frame_of_reference"),
                    "tracer_v2": (p2.get("tracer") or {}).get("status"),
                    "tracer_actual": fps[(s, t)]["tracer"]["status"],
                    "recon_v2": (p2.get("recon_description") or {}).get("value"),
                    "recon_actual": fps[(s, t)]["reconstruction_description"]["value"],
                    "iterations_v2": (p2.get("iterations") or {}).get("status"),
                    "iterations_actual": fps[(s, t)]["iterations"]["status"],
                    "pair_category_v2": pr["category"] if pr else None,
                    "qiba_v2": pr["qiba_predicted"] if pr else None,
                    "qiba_actual": next(
                        p.verdict for p in audits["qiba-fdg-1.14"].pairs if p.pair.subject_id == s
                    ),
                }
            )
    with (OUT / "census_v2_crosscheck.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(v2rows[0]))
        w.writeheader()
        w.writerows(v2rows)
    # ---------------------------------------------------------------- 5. real proposals
    refused = {(r["subject"], r["timepoint"]) for r in res if r["suv_status"] != "PASS"}
    props = [
        r
        for s in SUBJECTS
        for t in TPS
        if (s, t) in refused
        for r in proposals_without_suv(s, t, rv_dir / "qc")
    ]
    audit_ws = yaml.safe_load(
        (OUT / "audit_percist-1.0" / "reference_review_worksheet.yaml").read_text()
    )
    pending = dict(audit_ws.get("reviews") or {})
    for r in props:
        if r["status"] != "PROPOSED":
            continue
        pending.setdefault(f"{r['subject']}/{r['timepoint']}", {})[r["region"]] = {
            "subject": r["subject"],
            "timepoint": r["timepoint"],
            "region": r["region"],
            "decision": "PENDING",
            "proposal_sha256": r["proposal_sha256"],
            "proposal_geometry": {
                k: r[k] for k in ("method", "centre_patient_mm", "diameter_mm", "length_mm")
            },
            "qc_image": r["qc_image"],
            "measurement": "NOT AVAILABLE: strict SUVbw refused at this timepoint "
            "(DECAY_FACTOR_INCONSISTENT); PERCIST liver rules stay UNKNOWN even after review",
        }
    for t in audits["percist-1.0"].timepoints:
        for region, res_ in (("LIVER", t.liver), ("BLOOD_POOL", t.blood_pool)):
            if res_ is not None and res_.status in ("PROPOSED_REQUIRES_REVIEW", "AUTO_NOT_FOUND"):
                props.append(
                    {
                        "subject": t.subject_id,
                        "timepoint": t.timepoint,
                        "region": region,
                        "status": "PROPOSED"
                        if res_.status == "PROPOSED_REQUIRES_REVIEW"
                        else "NOT_FOUND",
                        "reason": res_.refusal,
                        "proposal_sha256": res_.proposal_sha256,
                        "measured_suv_mean_preview": res_.suv_mean,
                        "measured_sul_mean_preview": res_.sul_mean,
                        "cov_preview": res_.cov,
                        "qc_image": res_.qc_image,
                        "source": "trial audit (quantitative PET available)",
                    }
                )
    (rv_dir / "reference_review_worksheet.yaml").write_text(
        "# REAL ACRIN proposals (distinct namespace from the synthetic demo reviews).\n"
        "# Decisions are recorded ONLY by a human. Nothing here is a decision.\n"
        + yaml.safe_dump({"schema": "voxeltrace.reference-review/2", "reviews": pending})
    )
    (rv_dir / "proposals.json").write_text(json.dumps(props, indent=2, default=str) + "\n")
    summary = {
        "real_proposals": {
            f"{r['subject'][-3:]}/{r['timepoint']}/{r['region']}": r["status"] for r in props
        },
        "ingestion_ok": [r["ingestion_ok"] for r in ing],
        "suv": {f"{r['subject'][-3:]}/{r['timepoint']}": r["suv_status"] for r in res},
        "sul": {
            f"{r['subject'][-3:]}/{r['timepoint']}": {k: v["status"] for k, v in r["sul"].items()}
            for r in res
        },
        "verdicts": {
            rs: {p.pair.subject_id: p.verdict for p in a.pairs} for rs, a in audits.items()
        },
        "reference_regions": {
            f"{t.subject_id[-3:]}/{t.timepoint}": {
                "liver": t.liver.status if t.liver else None,
                "blood_pool": t.blood_pool.status if t.blood_pool else None,
            }
            for t in audits["percist-1.0"].timepoints
        },
        "protocol_comparability": {s: fp_doc[s]["protocol_comparability"] for s in SUBJECTS},
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
