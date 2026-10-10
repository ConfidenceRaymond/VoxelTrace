"""Partner-drop intake mapping (VT-INTAKE-MAPPING-1): how source folders were interpreted.

  map_intake(drop, levels=("site", "subject", "timepoint"), timepoint_map=None) -> mapping
  stage_intake(mapping, drop, out, trial_id=...)  -> <out>/<subject>/<timepoint>/{PET,CT,SEG}

Headers only (no pixel data); nothing in the drop is modified. The mapping is an OPERATOR
artefact: it records source-relative paths and series descriptions so the operator can check
the interpretation, and is not part of the delivery package.

Folder levels are positional and explicit (default ``site/subject/timepoint``); everything
below the timepoint folder belongs to that scan. Files above it, hidden files, ``__MACOSX`` and
non-DICOM files are listed as ignored with the reason.

Timepoint names are normalised by a fixed alias table (or an explicit ``timepoint_map``):
baseline / BL / pre / T0 ... -> ``baseline``; follow-up / FU / post / FU1 / T1 ... -> ``followup``;
FU2 / T2 ... -> ``followup2``. An unrecognised name, or two folders of one subject mapping to the
same name (e.g. ``Follow-Up`` and ``FU1``), is NEEDS_REVIEW, never guessed.

PET series selection uses only these deterministic exclusion rules, in order, and selects a
series only when exactly one candidate remains:
  R1 NAC          exclude PET whose CorrectedImage is present and lacks ATTN
  R2 SC           exclude secondary-capture SOP classes (not quantitative images)
  R3 UNITS        when at least one candidate has Units BQML, exclude candidates with other
                  units (processed copies such as SUV-unit series)
Zero or several remaining candidates -> NEEDS_REVIEW with every candidate listed. Series
descriptions, series numbers and file counts are NEVER used to choose.

CT: selected only when exactly one multi-image CT shares the selected PET's frame of
reference; SEG / RTSTRUCT: selected only when exactly one is present. Otherwise the item is
left unselected with a WARNING (both are optional for the strict SUV path).
"""

from __future__ import annotations

import hashlib
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

INTAKE_MAPPING_SCHEMA = "VT-INTAKE-MAPPING-1"
SC_PREFIX = "1.2.840.10008.5.1.4.1.1.7"
_TAGS = ["Modality", "SeriesInstanceUID", "StudyInstanceUID", "SOPClassUID", "SeriesDescription",
         "ImageType", "CorrectedImage", "Units", "FrameOfReferenceUID", "PatientID",
         "AcquisitionDate", "SeriesDate", "RadiopharmaceuticalInformationSequence"]  # fmt: skip
BASELINE = {
    "baseline",
    "bl",
    "base",
    "pre",
    "pretreatment",
    "pretherapy",
    "tp0",
    "t0",
    "v0",
    "visit0",
}
FOLLOWUP = {"followup", "fu", "post", "posttreatment", "posttherapy"}
_NUM = re.compile(r"^(followup|fu|tp|t|visit|v|post)(\d+)$")


def _h(s: str | None, n: int = 16) -> str | None:
    return hashlib.sha256(s.encode()).hexdigest()[:n] if s else None


def canonical_timepoint(raw: str, timepoint_map: dict[str, str] | None = None) -> str | None:
    """Fixed alias table; ``None`` when the name is not recognised."""
    if timepoint_map and raw in timepoint_map:
        return timepoint_map[raw]
    k = re.sub(r"[\s_\-]+", "", raw.casefold())
    if k in BASELINE:
        return "baseline"
    if k in FOLLOWUP:
        return "followup"
    m = _NUM.match(k)
    if m:
        prefix, n = m.group(1), int(m.group(2))
        if n == 0:
            return "baseline" if prefix not in ("followup", "fu", "post") else None
        return "followup" if n == 1 else f"followup{n}"  # the first follow-up is 'followup'
    return None


def _order_key(tp: str) -> tuple[int, int]:
    if tp == "baseline":
        return (0, 0)
    m = re.match(r"followup(\d*)$", tp)
    return (1, int(m.group(1) or 0)) if m else (2, 0)


def _read(p: Path):
    import pydicom

    try:
        return pydicom.dcmread(p, stop_before_pixels=True, specific_tags=_TAGS)
    except Exception:  # noqa: BLE001 - not DICOM (or unreadable): listed as ignored
        return None


def _series_info(files: list[tuple[str, Any]]) -> dict[str, Any]:
    ds = files[0][1]
    rp = getattr(ds, "RadiopharmaceuticalInformationSequence", None)
    tracer = str(getattr(rp[0], "Radiopharmaceutical", "") or "") or None if rp else None
    date = str(getattr(ds, "AcquisitionDate", "") or getattr(ds, "SeriesDate", "") or "")
    pids = {str(getattr(d, "PatientID", "") or "") for _, d in files}
    return {
        "modality": str(getattr(ds, "Modality", "") or ""),
        "series_pseudonym": "s_" + (_h(str(getattr(ds, "SeriesInstanceUID", ""))) or "none"),
        "study_pseudonym": "st_" + (_h(str(getattr(ds, "StudyInstanceUID", ""))) or "none"),
        "frame_of_reference": _h(str(getattr(ds, "FrameOfReferenceUID", "") or "")),
        "sop_class": str(getattr(ds, "SOPClassUID", "") or ""),
        "image_type": list(getattr(ds, "ImageType", []) or []),
        "corrected_image": list(getattr(ds, "CorrectedImage", []) or [])
        if "CorrectedImage" in ds
        else None,
        "units": str(getattr(ds, "Units", "") or "") or None,
        "series_description": str(getattr(ds, "SeriesDescription", "") or ""),
        "tracer": tracer,
        "acquisition_date": f"{date[:4]}-{date[4:6]}-{date[6:8]}" if len(date) == 8 else None,
        "patient_id_sha256": [hashlib.sha256(p.encode()).hexdigest() for p in sorted(pids) if p],
        "instances": len(files),
        "files": sorted(rel for rel, _ in files),
    }


def _select_pet(cands: list[dict[str, Any]]) -> tuple[dict | None, list[dict[str, Any]]]:
    """-> (selected or None, [{series, excluded_by}])."""
    log, alive = [], list(cands)
    rules = (
        (
            "R1_NAC",
            lambda s: s["corrected_image"] is not None and "ATTN" not in s["corrected_image"],
        ),
        ("R2_SECONDARY_CAPTURE", lambda s: s["sop_class"].startswith(SC_PREFIX)),
    )
    for rid, bad in rules:
        for s in [x for x in alive if bad(x)]:
            alive.remove(s)
            log.append({"series": s["series_pseudonym"], "excluded_by": rid})
    if any(s["units"] == "BQML" for s in alive):
        for s in [x for x in alive if x["units"] != "BQML"]:
            alive.remove(s)
            log.append({"series": s["series_pseudonym"], "excluded_by": "R3_UNITS"})
    return (alive[0] if len(alive) == 1 else None), log + [
        {"series": s["series_pseudonym"], "excluded_by": None} for s in alive
    ]


def map_intake(
    drop: str | Path,
    *,
    levels: tuple[str, ...] = ("site", "subject", "timepoint"),
    timepoint_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    drop = Path(drop)
    if "subject" not in levels or "timepoint" not in levels:
        raise ValueError("levels must include 'subject' and 'timepoint'")
    depth = len(levels)
    ignored: list[dict[str, str]] = []
    groups: dict[tuple[str, ...], dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for root, dirs, files in os.walk(drop, followlinks=True):
        dirs[:] = sorted(d for d in dirs)
        rel_root = Path(root).relative_to(drop)
        for d in list(dirs):
            if d.startswith(".") or d == "__MACOSX":
                ignored.append(
                    {
                        "path": (rel_root / d).as_posix() + "/",
                        "reason": "hidden or archive-metadata folder",
                    }
                )
                dirs.remove(d)
        for f in sorted(files):
            rel = (rel_root / f).as_posix()
            parts = Path(rel).parts
            if f.startswith("."):
                ignored.append({"path": rel, "reason": "hidden file"})
                continue
            if len(parts) <= depth:
                ignored.append(
                    {
                        "path": rel,
                        "reason": f"file above the {levels[-1]} level (not part of a scan)",
                    }
                )
                continue
            ds = _read(drop / rel)
            if ds is None or not getattr(ds, "Modality", None):
                ignored.append(
                    {
                        "path": rel,
                        "reason": "not DICOM (e.g. protocol PDF, sidecar, notes); not used",
                    }
                )
                continue
            key = tuple(parts[:depth])
            groups[key][str(getattr(ds, "SeriesInstanceUID", rel))].append((rel, ds))

    scans = []
    for key in sorted(groups):
        lab = dict(zip(levels, key, strict=True))
        series = sorted(
            (_series_info(v) for v in groups[key].values()), key=lambda s: s["series_pseudonym"]
        )
        findings: list[dict[str, str]] = []
        tp = canonical_timepoint(lab["timepoint"], timepoint_map)
        if tp is None:
            findings.append({"code": "TIMEPOINT_NAME_UNRECOGNISED", "severity": "NEEDS_REVIEW",
                             "detail": f"'{lab['timepoint']}' is not in the alias table; supply a timepoint map"})  # fmt: skip
        pet_cands = [s for s in series if s["modality"] == "PT"]
        pet, sel_log = _select_pet(pet_cands)
        if not pet_cands:
            findings.append(
                {"code": "NO_PET_SERIES", "severity": "NEEDS_REVIEW", "detail": "no PT series"}
            )
        elif pet is None:
            findings.append({"code": "MULTIPLE_PET_CANDIDATES" if len([x for x in sel_log if x["excluded_by"] is None]) > 1
                             else "NO_QUANTITATIVE_PET", "severity": "NEEDS_REVIEW",
                             "detail": f"{len(pet_cands)} PET series; deterministic rules R1-R3 leave "
                             f"{len([x for x in sel_log if x['excluded_by'] is None])}; VoxelTrace will not choose"})  # fmt: skip
        ct = [s for s in series if s["modality"] == "CT" and s["instances"] > 1
              and pet is not None and s["frame_of_reference"] == pet["frame_of_reference"]]  # fmt: skip
        ct_sel = ct[0] if len(ct) == 1 else None
        if pet is not None and len(ct) != 1:
            findings.append({"code": "CT_NOT_SELECTED", "severity": "WARNING",
                             "detail": f"{len(ct)} volumetric CT series share the PET frame of reference (need exactly 1); "
                             "reference-region proposals will be unavailable"})  # fmt: skip
        segs = [s for s in series if s["modality"] in ("SEG", "RTSTRUCT")]
        seg_sel = segs[0] if len(segs) == 1 else None
        if len(segs) > 1:
            findings.append({"code": "SEGMENTATION_AMBIGUOUS", "severity": "WARNING",
                             "detail": f"{len(segs)} SEG/RTSTRUCT series; none selected"})  # fmt: skip
        pids = {h for s in series for h in s["patient_id_sha256"]}
        if len(pids) > 1:
            findings.append({"code": "MIXED_PATIENT_IN_SCAN", "severity": "NEEDS_REVIEW",
                             "detail": f"{len(pids)} different patient identifiers in one scan folder"})  # fmt: skip
        chosen = {x["series_pseudonym"] for x in (pet, ct_sel, seg_sel) if x}
        sev = {f["severity"] for f in findings}
        scans.append({
            **lab, "timepoint_raw": lab["timepoint"], "timepoint": tp,
            "status": "NEEDS_REVIEW" if "NEEDS_REVIEW" in sev else "MAPPED_WITH_WARNINGS" if sev else "MAPPED",
            "pet_selected": pet["series_pseudonym"] if pet else None,
            "pet_selection": sel_log,
            "ct_selected": ct_sel["series_pseudonym"] if ct_sel else None,
            "segmentation_selected": seg_sel["series_pseudonym"] if seg_sel else None,
            "ignored_series": [{"series": s["series_pseudonym"], "modality": s["modality"],
                                "reason": "not selected" if s["modality"] in ("PT", "CT", "SEG", "RTSTRUCT")
                                else f"modality {s['modality']} not used"}
                               for s in series if s["series_pseudonym"] not in chosen],  # fmt: skip
            "series": series,
            "findings": findings,
        })  # fmt: skip
    _subject_checks(scans, levels)
    from voxeltrace.trial.pairing_audit import ScanIdentity, audit_pairing

    ids = []
    for s in scans:
        if s["pet_selected"] and s["timepoint"]:
            pet = next(x for x in s["series"] if x["series_pseudonym"] == s["pet_selected"])
            ids.append(ScanIdentity(subject=s["staged_subject"], timepoint=s["timepoint"],
                                    patient_id_sha256=(pet["patient_id_sha256"] or [None])[0],
                                    pet_series_pseudonym=pet["series_pseudonym"],
                                    acquisition_date=pet["acquisition_date"], tracer=pet["tracer"]))  # fmt: skip
    order = sorted({i.timepoint for i in ids}, key=_order_key)
    pairing = audit_pairing(ids, order)
    statuses = [s["status"] for s in scans]
    status = ("NO_SCANS" if not scans else "NEEDS_REVIEW" if "NEEDS_REVIEW" in statuses
              or pairing["status"] != "OK" else "MAPPED_WITH_WARNINGS" if "MAPPED_WITH_WARNINGS" in statuses
              else "MAPPED")  # fmt: skip
    return {
        "schema": INTAKE_MAPPING_SCHEMA,
        "drop_label": drop.name,
        "levels": list(levels),
        "status": status,
        "rules": ["R1_NAC", "R2_SECONDARY_CAPTURE", "R3_UNITS"],
        "timepoint_order": order,
        "scans": scans,
        "ignored_files": ignored,
        "pairing": pairing,
        "note": "OPERATOR ARTEFACT (contains source-relative paths and series descriptions); "
        "not for delivery. Headers only; the drop is not modified.",
    }


def _subject_checks(scans: list[dict[str, Any]], levels: tuple[str, ...]) -> None:
    """Staged subject names (site prefix only when subject names collide across sites) and
    duplicate canonical timepoints within a subject."""
    by_name: dict[str, set[str]] = defaultdict(set)
    for s in scans:
        by_name[s["subject"]].add(s.get("site", ""))
    prefix = "site" in levels and any(len(v) > 1 for v in by_name.values())
    for s in scans:
        s["staged_subject"] = f"{s['site']}-{s['subject']}" if prefix else s["subject"]
    seen: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for s in scans:
        if s["timepoint"]:
            seen[(s["staged_subject"], s["timepoint"])].append(s)
    for group in seen.values():
        if len(group) > 1:
            for s in group:
                s["findings"].append({"code": "DUPLICATE_TIMEPOINT", "severity": "NEEDS_REVIEW",
                                      "detail": f"{[g['timepoint_raw'] for g in group]} all map to '{s['timepoint']}'"})  # fmt: skip
                s["status"] = "NEEDS_REVIEW"


def stage_intake(
    mapping: dict[str, Any], drop: str | Path, out: str | Path, *, trial_id: str
) -> dict[str, Any]:
    """Symlink the selected series of every MAPPED / MAPPED_WITH_WARNINGS scan into a
    <subject>/<timepoint>/{PET,CT,SEG} trial folder with a trial.yaml (sites + timepoint order).
    NEEDS_REVIEW scans are not staged. Never overwrites."""
    import yaml

    drop, out = Path(drop).resolve(), Path(out)
    if out.exists():
        raise FileExistsError(f"{out} exists (never overwritten)")
    staged, skipped, sites = [], [], {}
    blocked = set(mapping["pairing"]["subjects_blocked"])
    for s in mapping["scans"]:
        if s["status"] == "NEEDS_REVIEW" or s["staged_subject"] in blocked:
            skipped.append(
                {"scan": f"{s['staged_subject']}/{s['timepoint_raw']}", "status": s["status"]}
            )
            continue
        by_ps = {x["series_pseudonym"]: x for x in s["series"]}
        for role, key in (
            ("PET", "pet_selected"),
            ("CT", "ct_selected"),
            ("SEG", "segmentation_selected"),
        ):
            if not s[key]:
                continue
            d = out / s["staged_subject"] / s["timepoint"] / role
            d.mkdir(parents=True, exist_ok=True)
            for i, rel in enumerate(by_ps[s[key]]["files"]):
                (d / f"{i:05d}.dcm").symlink_to(drop / rel)
        staged.append(f"{s['staged_subject']}/{s['timepoint']}")
        if "site" in s:
            sites[s["staged_subject"]] = s["site"]
    if not staged:
        raise ValueError("nothing to stage: every scan needs review")
    order = sorted({t.split("/", 1)[1] for t in staged}, key=_order_key)
    cfg = {"trial_id": trial_id, "ruleset": "qiba-fdg-1.14", "timepoint_order": order,
           "reference_proposals": "auto", "reference_review_file": "reference_review.yaml",
           "lesion_review_file": "lesion_review.jsonl", "lesion_evidence_policy": "REVIEW_REQUIRED"}  # fmt: skip
    if sites:
        cfg["sites"] = dict(sorted(sites.items()))
    (out / "trial.yaml").write_text("# written by voxeltrace intake-map --stage from the intake mapping\n"
                                   + yaml.safe_dump(cfg, sort_keys=False))  # fmt: skip
    return {"staged": staged, "skipped": skipped, "trial_yaml": str(out / "trial.yaml")}
