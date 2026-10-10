"""Partner intake contract (VT-PARTNER-INTAKE-1): the partner's own declaration of what was
sent, checked against the files before any audit.

  validate_partner_intake(yaml_path, root=None, check_dicom=True) -> report

The YAML lists one entry per subject/timepoint with relative paths into the transfer. The
validator checks the schema, the paths, duplicates and obvious cross-subject / timepoint
inconsistencies, and compares the declared vendor / model / software / date with the first PET
header. It reads headers only, never infers a missing value, and **never accepts a human
decision**: review decisions, acceptances or verdicts in the intake file are refused.

Severities: BLOCKING (the intake cannot be used), NEEDS_REVIEW (a person must resolve it),
WARNING. Status: INVALID / NEEDS_REVIEW / VALID_WITH_WARNINGS / VALID.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import yaml

PARTNER_INTAKE_SCHEMA = "VT-PARTNER-INTAKE-1"
REPORT_SCHEMA = "VT-PARTNER-INTAKE-REPORT-1"
REQUIRED = ("site_id", "subject_id", "timepoint", "tracer", "expected_vendor", "expected_scanner_model",
            "pet_path", "partner_review_required", "partner_reviewer_role")  # fmt: skip
OPTIONAL = ("expected_software_version", "expected_acquisition_date", "ct_path", "segmentation_path",
            "protocol_document_path", "notes")  # fmt: skip
TOP_REQUIRED = ("schema", "organization_id", "study_id", "entries")
# fields that would carry a human decision: intake never accepts them
DECISION_FIELDS = re.compile(
    r"(decision|accept|approv|verdict|adjudicat|review_result|reviewed_by|signed_off)", re.I
)
SEVERITY = ("WARNING", "NEEDS_REVIEW", "BLOCKING")
# code -> (severity, plain language, remediation, re-export, documentation, human review, permanent)
PARTNER_CODES: dict[str, tuple[str, str, str, str, str, str, str]] = {
    "SCHEMA_INVALID": ("BLOCKING", "The intake file does not follow the template.", "correct the file using partner_intake.yaml", "NO", "YES", "NO", "NO"),
    "REQUIRED_FIELD_MISSING": ("BLOCKING", "A required field is empty.", "fill the field (no identifiers)", "NO", "YES", "NO", "NO"),
    "HUMAN_DECISION_NOT_ACCEPTED": ("BLOCKING", "The intake file contains a review decision; decisions are only recorded by a qualified reviewer in the review tools.", "remove the field; record reviews in VoxelTrace's review pages", "NO", "YES", "NO", "NO"),
    "UNKNOWN_FIELD": ("WARNING", "A field is not part of the template and is ignored.", "remove or rename it", "NO", "YES", "NO", "NO"),
    "PERSONAL_DATA_IN_ROLE": ("BLOCKING", "The reviewer field contains a name or e-mail; only a role is allowed.", "replace with a role such as PET_PHYSICIST", "NO", "YES", "NO", "NO"),
    "POSSIBLE_IDENTIFIER": ("NEEDS_REVIEW", "A field may contain an identifier.", "replace with a pseudonym", "NO", "YES", "NO", "NO"),
    "PATH_ABSOLUTE": ("BLOCKING", "A path is absolute; paths must be relative to the transfer root.", "make the path relative", "NO", "YES", "NO", "NO"),
    "PATH_ESCAPES_ROOT": ("BLOCKING", "A path points outside the transfer.", "point to a folder inside the transfer", "NO", "YES", "NO", "NO"),
    "PATH_NOT_FOUND": ("BLOCKING", "A declared folder or file is not in the transfer.", "send the missing data or correct the path", "YES", "YES", "NO", "NO"),
    "PET_PATH_NO_DICOM": ("BLOCKING", "The declared PET folder contains no readable DICOM.", "send the PET DICOM series", "YES", "NO", "NO", "NO"),
    "PET_PATH_NOT_PET": ("BLOCKING", "The declared PET folder contains another modality.", "point pet_path at the PET series", "NO", "YES", "NO", "NO"),
    "VENDOR_MISMATCH": ("NEEDS_REVIEW", "The declared vendor differs from the DICOM header.", "confirm which scanner was used", "NO", "YES", "YES", "NO"),
    "SCANNER_MODEL_MISMATCH": ("NEEDS_REVIEW", "The declared scanner model differs from the DICOM header.", "confirm which scanner was used", "NO", "YES", "YES", "NO"),
    "SOFTWARE_VERSION_MISMATCH": ("WARNING", "The declared software version differs from the DICOM header.", "confirm the software version", "NO", "YES", "NO", "NO"),
    "ACQUISITION_DATE_MISMATCH": ("NEEDS_REVIEW", "The declared acquisition date differs from the DICOM (date shifting?).", "confirm the visit and that dates were shifted consistently", "NO", "YES", "YES", "NO"),
    "MANUFACTURER_NOT_IN_DICOM": ("WARNING", "The vendor is declared but absent in the DICOM.", "retain device identity in the export", "YES", "YES", "NO", "NO"),
    "MANUFACTURERMODELNAME_NOT_IN_DICOM": ("WARNING", "The scanner model is declared but absent in the DICOM.", "retain device identity in the export", "YES", "YES", "NO", "NO"),
    "SOFTWAREVERSIONS_NOT_IN_DICOM": ("WARNING", "The software version is declared but absent in the DICOM.", "retain device identity in the export", "YES", "YES", "NO", "NO"),
    "DUPLICATE_ENTRY": ("BLOCKING", "The same subject and timepoint are declared more than once.", "keep one entry per visit", "NO", "YES", "NO", "NO"),
    "SCAN_MAPPED_TWICE": ("BLOCKING", "One scan is declared for two visits of a subject.", "correct the mapping with the visit records", "NO", "YES", "YES", "NO"),
    "SCAN_MAPPED_TO_MULTIPLE_SUBJECTS": ("BLOCKING", "One scan is declared for more than one subject.", "correct the mapping with the site", "NO", "YES", "YES", "NO"),
    "SUBJECT_SITE_INCONSISTENT": ("NEEDS_REVIEW", "One subject is declared at more than one site.", "confirm the site", "NO", "YES", "NO", "NO"),
    "SINGLE_TIMEPOINT": ("WARNING", "A subject has one timepoint, so no pair can be formed.", "send the missing visit if it exists", "YES", "NO", "NO", "MAYBE"),
}  # fmt: skip
EXIT_CODES = {"VALID": 0, "VALID_WITH_WARNINGS": 0, "NEEDS_REVIEW": 2, "INVALID": 3}


def _first_pet_header(d: Path):
    import pydicom

    files = (
        [d]
        if d.is_file()
        else sorted(x for x in d.rglob("*") if x.is_file() and not x.name.startswith("."))
    )
    for p in files:
        try:
            ds = pydicom.dcmread(p, stop_before_pixels=True, specific_tags=[
                "Modality", "Manufacturer", "ManufacturerModelName", "SoftwareVersions", "AcquisitionDate", "SeriesDate"])  # fmt: skip
        except Exception:  # noqa: BLE001 - not DICOM
            continue
        if getattr(ds, "Modality", None):
            return ds, len(files)
    return None, len(files)


def _norm(v: Any) -> str:
    return " ".join(str(v or "").casefold().split())


def validate_partner_intake(
    path: str | Path, root: str | Path | None = None, *, check_dicom: bool = True
) -> dict[str, Any]:
    from voxeltrace.intake import canonical_timepoint
    from voxeltrace.privacy_scan import scan_text
    from voxeltrace.validate_input import tracer_class

    path = Path(path)
    root = Path(root) if root else path.parent
    findings: list[dict[str, Any]] = []

    def add(code: str, severity: str, detail: str, entry: int | None = None) -> None:
        findings.append({"code": code, "severity": severity, "entry": entry, "detail": detail})

    try:
        doc = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        add("SCHEMA_INVALID", "BLOCKING", f"cannot read YAML: {str(exc).splitlines()[0]}")
        return _report(path, findings, [])
    if not isinstance(doc, dict):
        add(
            "SCHEMA_INVALID",
            "BLOCKING",
            "the file must be a mapping with schema, organization_id, study_id, entries",
        )
        return _report(path, findings, [])
    for k in TOP_REQUIRED:
        if not doc.get(k):
            add("REQUIRED_FIELD_MISSING", "BLOCKING", f"top-level '{k}' missing")
    if doc.get("schema") and doc["schema"] != PARTNER_INTAKE_SCHEMA:
        add(
            "SCHEMA_INVALID",
            "BLOCKING",
            f"schema must be {PARTNER_INTAKE_SCHEMA}, got {doc['schema']}",
        )
    for k in doc:
        if DECISION_FIELDS.search(str(k)):
            add(
                "HUMAN_DECISION_NOT_ACCEPTED",
                "BLOCKING",
                f"top-level '{k}': review decisions are never part of intake",
            )
    entries = doc.get("entries") or []
    if not isinstance(entries, list):
        add("SCHEMA_INVALID", "BLOCKING", "'entries' must be a list")
        entries = []

    good: list[dict[str, Any]] = []
    for i, e in enumerate(entries, 1):
        if not isinstance(e, dict):
            add("SCHEMA_INVALID", "BLOCKING", "entry is not a mapping", i)
            continue
        for k in e:
            if DECISION_FIELDS.search(str(k)):
                add("HUMAN_DECISION_NOT_ACCEPTED", "BLOCKING",
                    f"'{k}': review decisions, acceptances and verdicts are recorded by a qualified reviewer in "
                    "VoxelTrace's review tools, never in the intake file", i)  # fmt: skip
            elif k not in REQUIRED + OPTIONAL:
                add(
                    "UNKNOWN_FIELD",
                    "WARNING",
                    f"field '{k}' is not part of {PARTNER_INTAKE_SCHEMA} and is ignored",
                    i,
                )
        missing = [k for k in REQUIRED if e.get(k) in (None, "")]
        if missing:
            add("REQUIRED_FIELD_MISSING", "BLOCKING", f"missing {missing}", i)
        if "partner_review_required" in e and not isinstance(e["partner_review_required"], bool):
            add("SCHEMA_INVALID", "BLOCKING", "partner_review_required must be true or false", i)
        if "@" in str(e.get("partner_reviewer_role", "")):
            add(
                "PERSONAL_DATA_IN_ROLE",
                "BLOCKING",
                "partner_reviewer_role must be a role (e.g. PET_PHYSICIST), not an e-mail or name",
                i,
            )
        d = e.get("expected_acquisition_date")
        if d not in (None, ""):
            try:
                date.fromisoformat(str(d))
            except ValueError:
                add(
                    "SCHEMA_INVALID",
                    "BLOCKING",
                    f"expected_acquisition_date '{d}' is not YYYY-MM-DD",
                    i,
                )
        for k in ("subject_id", "site_id", "notes", "timepoint"):
            hits = [
                h
                for h in scan_text(str(e.get(k, "")), extra_words=[])
                if h["category"] != "DICOM_UID"
            ]
            if hits:
                add(
                    "POSSIBLE_IDENTIFIER",
                    "NEEDS_REVIEW",
                    f"'{k}' looks like it contains {sorted({h['category'] for h in hits})}; use pseudonyms only",
                    i,
                )
        if e.get("timepoint") and canonical_timepoint(str(e["timepoint"])) is None:
            add(
                "TIMEPOINT_NAME_UNRECOGNISED",
                "WARNING",
                f"timepoint '{e['timepoint']}' is not a recognised baseline/follow-up name; its order must be declared",
                i,
            )
        tc = tracer_class(str(e.get("tracer") or ""))
        if e.get("tracer") and tc in ("PSMA", "AMYLOID", "TAU"):
            add(
                "NON_FDG_TRACER",
                "NEEDS_REVIEW",
                f"{e['tracer']} ({tc}): outside the FDG rule sets (reported UNSUPPORTED)",
                i,
            )
        elif e.get("tracer") and tc == "OTHER":
            add(
                "TRACER_NOT_RECOGNISED",
                "NEEDS_REVIEW",
                f"'{e['tracer']}' is not recognised as FDG",
                i,
            )
        # paths
        for k in ("pet_path", "ct_path", "segmentation_path", "protocol_document_path"):
            v = e.get(k)
            if v in (None, ""):
                continue
            pv = Path(str(v))
            sev = "BLOCKING" if k == "pet_path" else "NEEDS_REVIEW"
            if pv.is_absolute():
                add("PATH_ABSOLUTE", "BLOCKING", f"{k} must be relative to the transfer root", i)
                continue
            full = (root / pv).resolve()
            if not full.is_relative_to(root.resolve()):
                add("PATH_ESCAPES_ROOT", "BLOCKING", f"{k} points outside the transfer root", i)
                continue
            if not full.exists():
                add("PATH_NOT_FOUND", sev, f"{k} '{v}' does not exist", i)
                continue
            if k == "pet_path" and check_dicom:
                ds, n = _first_pet_header(full)
                if ds is None:
                    add(
                        "PET_PATH_NO_DICOM",
                        "BLOCKING",
                        f"no readable DICOM under pet_path ({n} file(s))",
                        i,
                    )
                elif ds.Modality != "PT":
                    add(
                        "PET_PATH_NOT_PET",
                        "BLOCKING",
                        f"first DICOM under pet_path has Modality {ds.Modality}",
                        i,
                    )
                else:
                    _compare(e, ds, add, i)
        good.append({**e, "_i": i})

    # duplicates and cross-entry consistency
    key_count = Counter((str(e.get("subject_id")), str(e.get("timepoint"))) for e in good)
    for (s, t), n in sorted(key_count.items()):
        if n > 1:
            add("DUPLICATE_ENTRY", "BLOCKING", f"{s}/{t} declared {n} times")
    norm_tp: dict[tuple[str, str], set] = defaultdict(set)
    for e in good:
        norm_tp[
            (
                str(e.get("subject_id")),
                re.sub(r"[\s_\-]+", "", str(e.get("timepoint", "")).casefold()),
            )
        ].add(str(e.get("timepoint")))
    for (s, _), names in sorted(norm_tp.items()):
        if len(names) > 1:
            add(
                "DUPLICATE_TIMEPOINT",
                "BLOCKING",
                f"{s}: timepoints {sorted(names)} are the same visit name written differently",
            )
    for k in ("pet_path", "ct_path", "segmentation_path"):
        owners: dict[str, list] = defaultdict(list)
        for e in good:
            if e.get(k):
                owners[Path(str(e[k])).as_posix().rstrip("/")].append(
                    f"{e.get('subject_id')}/{e.get('timepoint')}"
                )
        for pth, who in sorted(owners.items()):
            if len(who) > 1:
                subj = {w.split("/")[0] for w in who}
                code = "SCAN_MAPPED_TO_MULTIPLE_SUBJECTS" if len(subj) > 1 else "SCAN_MAPPED_TWICE"
                add(code, "BLOCKING", f"{k} '{pth}' is declared for {sorted(who)}")
    sites: dict[str, set] = defaultdict(set)
    tps: dict[str, list] = defaultdict(list)
    for e in good:
        sites[str(e.get("subject_id"))].add(str(e.get("site_id")))
        tps[str(e.get("subject_id"))].append(str(e.get("timepoint")))
    for s, ss in sorted(sites.items()):
        if len(ss) > 1:
            add(
                "SUBJECT_SITE_INCONSISTENT",
                "NEEDS_REVIEW",
                f"{s} is declared at sites {sorted(ss)}",
            )
        if len(tps[s]) < 2:
            add("SINGLE_TIMEPOINT", "WARNING", f"{s} has one timepoint: no pair can be formed")
    for s in sorted(tps):
        tracers = {_norm(e.get("tracer")) for e in good if str(e.get("subject_id")) == s}
        if len(tracers) > 1:
            add("MIXED_TRACER", "NEEDS_REVIEW", f"{s} declares different tracers {sorted(tracers)}")
    return _report(path, findings, good, doc)


def _compare(e: dict, ds: Any, add, i: int) -> None:
    """Declared vs DICOM; a mismatch is for a person to resolve, never auto-corrected."""
    for decl, attr, code, sev in (
        ("expected_vendor", "Manufacturer", "VENDOR_MISMATCH", "NEEDS_REVIEW"),
        (
            "expected_scanner_model",
            "ManufacturerModelName",
            "SCANNER_MODEL_MISMATCH",
            "NEEDS_REVIEW",
        ),
        ("expected_software_version", "SoftwareVersions", "SOFTWARE_VERSION_MISMATCH", "WARNING"),
    ):
        want = e.get(decl)
        got = getattr(ds, attr, None)
        got = (
            "\\".join(map(str, got))
            if isinstance(got, (list, tuple)) or type(got).__name__ == "MultiValue"
            else got
        )
        if want in (None, ""):
            continue
        if got in (None, ""):
            add(
                f"{attr.upper()}_NOT_IN_DICOM",
                "WARNING",
                f"{decl} declared but {attr} is absent in the DICOM",
                i,
            )
        elif _norm(want) not in _norm(got) and _norm(got) not in _norm(want):
            add(code, sev, f"{decl} '{want}' but DICOM {attr} is '{got}'", i)
    d = e.get("expected_acquisition_date")
    raw = str(getattr(ds, "AcquisitionDate", "") or getattr(ds, "SeriesDate", "") or "")
    if d not in (None, "") and len(raw) == 8:
        got = f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
        if got != str(d):
            add("ACQUISITION_DATE_MISMATCH", "NEEDS_REVIEW",
                f"declared {d}, DICOM {got} (de-identification may shift dates; confirm the shift is consistent)", i)  # fmt: skip


def _report(
    path: Path, findings: list[dict], good: list[dict], doc: dict | None = None
) -> dict[str, Any]:
    sev = {f["severity"] for f in findings}
    status = ("INVALID" if "BLOCKING" in sev else "NEEDS_REVIEW" if "NEEDS_REVIEW" in sev
              else "VALID_WITH_WARNINGS" if sev else "VALID")  # fmt: skip
    findings.sort(
        key=lambda f: (-SEVERITY.index(f["severity"]), f["entry"] or 0, f["code"], f["detail"])
    )
    return {
        "schema": REPORT_SCHEMA,
        "intake_schema": PARTNER_INTAKE_SCHEMA,
        "file": path.name,
        "status": status,
        "organization_id": (doc or {}).get("organization_id"),
        "study_id": (doc or {}).get("study_id"),
        "entries": len(good),
        "subjects": len({str(e.get("subject_id")) for e in good}),
        "review_required_entries": sum(e.get("partner_review_required") is True for e in good),
        "counts": dict(Counter(f["severity"] for f in findings)),
        "findings": findings,
        "note": "Intake check only: no SUV is computed, no verdict is produced and no human decision is "
        "inferred or accepted. RESEARCH PROTOTYPE.",
    }
