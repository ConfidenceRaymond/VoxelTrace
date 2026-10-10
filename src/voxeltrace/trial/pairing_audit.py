"""Longitudinal pairing safety audit (VT-PAIRING-AUDIT-1). Reporting only; no rule reads it.

Pairs are built by ``trial/pairing.py`` from the folder layout (baseline = first timepoint in
``timepoint_order``). This module checks that the layout is a safe basis for that pairing and
never re-pairs anything itself. Findings:

  BLOCKING      the pair results of the subject must not be used until the layout is fixed
    DUPLICATE_TIMEPOINT              two timepoint folders normalise to the same name
                                     (e.g. ``Baseline`` and ``baseline``, ``follow-up`` and
                                     ``followup``)
    SAME_SCAN_LINKED_TWICE           one PET series (UID or voxel content) under two
                                     timepoints of one subject
    SCAN_LINKED_TO_MULTIPLE_SUBJECTS one PET series under two subjects
    TIMEPOINT_ORDER_ANOMALY          a later timepoint was acquired before the baseline
  NEEDS_REVIEW  a person must confirm the layout
    TIMEPOINT_ORDER_UNDECLARED       no ``timepoint_order``: the order falls back to folder
                                     name sorting
    UNDECLARED_TIMEPOINT             a timepoint folder is not in ``timepoint_order``
    INCONSISTENT_SUBJECT_PSEUDONYM   the DICOM patient identifier differs between timepoints
                                     of one subject folder
    SUBJECT_PSEUDONYM_SHARED         two subject folders carry the same patient identifier
    SAME_DAY_TIMEPOINTS              two timepoints of one subject on the same date
  WARNING
    MISSING_TIMEPOINT                a subject has fewer than two timepoints, or lacks one
                                     declared in ``timepoint_order``
    MIXED_TRACER                     the tracer differs within a subject (VT-TRACER-SAME
                                     also decides this pair; reported here for intake)
    ACQUISITION_DATE_UNKNOWN         the ordering cannot be checked for a timepoint

Declared synthetic perturbations (test fixtures) reuse their parent's series by design; their
cross-subject / same-scan findings are downgraded to INFO with that reason.

Patient identifiers are compared as sha256 only and never written in clear.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

PAIRING_AUDIT_SCHEMA = "VT-PAIRING-AUDIT-1"
SEVERITY_ORDER = ("INFO", "WARNING", "NEEDS_REVIEW", "BLOCKING")
# code -> (severity for real data, remediation)
PAIRING_CODES: dict[str, tuple[str, str]] = {
    "DUPLICATE_TIMEPOINT": ("BLOCKING", "keep one folder per visit; rename or remove the duplicate after checking the site's visit records"),
    "SAME_SCAN_LINKED_TWICE": ("BLOCKING", "replace the duplicated scan with the correct visit's PET export"),
    "SCAN_LINKED_TO_MULTIPLE_SUBJECTS": ("BLOCKING", "confirm which subject the scan belongs to with the site and remove it from the other"),
    "TIMEPOINT_ORDER_ANOMALY": ("BLOCKING", "check the visit labels against the site's visit dates; correct the folder names or timepoint_order"),
    "TIMEPOINT_ORDER_UNDECLARED": ("NEEDS_REVIEW", "declare timepoint_order in trial.yaml (voxeltrace init-trial --timepoints ...)"),
    "UNDECLARED_TIMEPOINT": ("NEEDS_REVIEW", "add the timepoint to timepoint_order in its chronological position"),
    "INCONSISTENT_SUBJECT_PSEUDONYM": ("NEEDS_REVIEW", "confirm with the site that both timepoints belong to the same participant"),
    "SUBJECT_PSEUDONYM_SHARED": ("NEEDS_REVIEW", "confirm with the site whether the two subject folders are the same participant"),
    "SAME_DAY_TIMEPOINTS": ("NEEDS_REVIEW", "confirm with the site that the scans are distinct visits"),
    "MISSING_TIMEPOINT": ("WARNING", "supply the missing visit if it exists"),
    "MIXED_TRACER": ("WARNING", "confirm the tracer of each visit with the site"),
    "ACQUISITION_DATE_UNKNOWN": ("WARNING", "re-export with acquisition date/time, or confirm the visit dates from site records"),
}  # fmt: skip


class ScanIdentity(BaseModel):
    """What the pairing audit needs to know about one scan (no clear identifiers)."""

    subject: str
    timepoint: str
    patient_id_sha256: str | None = None
    pet_series_pseudonym: str | None = None
    pet_content_sha256: str | None = None
    acquisition_date: str | None = Field(default=None, description="ISO date (may be shifted)")
    tracer: str | None = None
    synthetic: bool = False


class PairingFinding(BaseModel):
    code: str
    severity: str
    subject: str
    timepoints: list[str] = Field(default_factory=list)
    detail: str


def normalise_timepoint(name: str) -> str:
    """Case, space, hyphen and underscore insensitive (``Follow-Up`` == ``followup``)."""
    return re.sub(r"[\s_\-]+", "", name.casefold())


def patient_id_sha256(scan_dir: str | Path) -> str | None:
    """sha256 of PatientID from the first PET header found (sorted walk; headers only)."""
    import pydicom

    for p in sorted(x for x in Path(scan_dir).rglob("*") if x.is_file()):
        try:
            ds = pydicom.dcmread(
                p, stop_before_pixels=True, specific_tags=["Modality", "PatientID"]
            )
        except Exception:  # noqa: BLE001 - not DICOM
            continue
        if getattr(ds, "Modality", None) == "PT":
            pid = str(getattr(ds, "PatientID", "") or "").strip()
            return hashlib.sha256(pid.encode()).hexdigest() if pid else None
    return None


def audit_pairing(
    scans: list[ScanIdentity], timepoint_order: list[str] | None = None
) -> dict[str, Any]:
    order = list(timepoint_order or [])
    findings: list[PairingFinding] = []
    by_subject: dict[str, list[ScanIdentity]] = defaultdict(list)
    for s in scans:
        by_subject[s.subject].append(s)

    def add(code: str, severity: str, subject: str, tps: list[str], detail: str) -> None:
        # severity is always the catalogued one, except the documented INFO downgrade for
        # declared synthetic perturbations
        assert severity in (PAIRING_CODES[code][0], "INFO"), (code, severity)
        findings.append(PairingFinding(code=code, severity=severity, subject=subject,
                                       timepoints=sorted(tps), detail=detail))  # fmt: skip

    if not order and any(len(v) > 1 for v in by_subject.values()):
        add("TIMEPOINT_ORDER_UNDECLARED", "NEEDS_REVIEW", "*", [],
            "trial.yaml has no timepoint_order: baseline is chosen by folder-name sorting; "
            "declare timepoint_order (voxeltrace init-trial --timepoints ...)")  # fmt: skip
    for subj in sorted(by_subject):
        items = sorted(by_subject[subj], key=lambda s: s.timepoint)
        names = [s.timepoint for s in items]
        norm = defaultdict(list)
        for n in names:
            norm[normalise_timepoint(n)].append(n)
        for key, group in sorted(norm.items()):
            if len(group) > 1:
                add("DUPLICATE_TIMEPOINT", "BLOCKING", subj, group,
                    f"timepoint folders {group} all normalise to '{key}'")  # fmt: skip
        if order:
            for n in names:
                if n not in order:
                    add("UNDECLARED_TIMEPOINT", "NEEDS_REVIEW", subj, [n],
                        f"'{n}' is not in timepoint_order {order}; its position is guessed")  # fmt: skip
            absent = [t for t in order if t not in names]
            if absent and len(names) >= 1:
                add("MISSING_TIMEPOINT", "WARNING", subj, absent,
                    f"declared timepoint(s) {absent} not supplied")  # fmt: skip
        if len(names) < 2:
            add("MISSING_TIMEPOINT", "WARNING", subj, names,
                "fewer than two timepoints: no pair can be formed")  # fmt: skip
        # same scan under two timepoints of the subject
        for attr, label in (("pet_series_pseudonym", "PET series UID"),
                            ("pet_content_sha256", "PET voxel content")):  # fmt: skip
            seen: dict[str, list[str]] = defaultdict(list)
            for s in items:
                if getattr(s, attr):
                    seen[getattr(s, attr)].append(s.timepoint)
            for tps in seen.values():
                if len(tps) > 1:
                    syn = any(s.synthetic for s in items if s.timepoint in tps)
                    add("SAME_SCAN_LINKED_TWICE", "INFO" if syn else "BLOCKING", subj, tps,
                        f"identical {label} at {tps}" + (" (declared synthetic perturbation)" if syn else ""))  # fmt: skip
        # patient identifier consistency
        pids = {s.patient_id_sha256 for s in items if s.patient_id_sha256}
        if len(pids) > 1:
            add("INCONSISTENT_SUBJECT_PSEUDONYM", "NEEDS_REVIEW", subj, names,
                f"{len(pids)} different DICOM patient identifiers within one subject folder")  # fmt: skip
        # tracer
        tracers = {(s.tracer or "").strip().casefold() for s in items if s.tracer}
        if len(tracers) > 1:
            add("MIXED_TRACER", "WARNING", subj, names, f"tracers differ: {sorted(tracers)}")
        # ordering by acquisition date
        rank = {t: (order.index(t) if t in order else len(order)) for t in names}
        ranked = sorted(items, key=lambda s: (rank[s.timepoint], s.timepoint))
        for s in ranked:
            if not s.acquisition_date:
                add("ACQUISITION_DATE_UNKNOWN", "WARNING", subj, [s.timepoint],
                    "acquisition date unknown; timepoint order cannot be checked")  # fmt: skip
        dated = [s for s in ranked if s.acquisition_date]
        if dated:
            base = dated[0]
            for s in dated[1:]:
                if s.acquisition_date < base.acquisition_date:  # type: ignore[operator]
                    add("TIMEPOINT_ORDER_ANOMALY", "BLOCKING", subj, [base.timepoint, s.timepoint],
                        f"'{s.timepoint}' ({s.acquisition_date}) precedes baseline "
                        f"'{base.timepoint}' ({base.acquisition_date})")  # fmt: skip
            dates = Counter(s.acquisition_date for s in dated)
            for d, n in sorted(dates.items()):
                if n > 1:
                    fixture = any(s.synthetic for s in items)
                    add("SAME_DAY_TIMEPOINTS", "INFO" if fixture else "NEEDS_REVIEW", subj,
                        [s.timepoint for s in dated if s.acquisition_date == d],
                        f"{n} timepoints acquired on {d}: "
                        + ("declared synthetic fixture" if fixture else "confirm they are distinct visits"))  # fmt: skip
    # cross-subject checks. A subject with any declared synthetic perturbation is a test
    # fixture; fixtures may reuse a real scan by design (INFO). Two or more REAL subjects sharing
    # a scan or a patient identifier keep the catalogued severity, whatever fixtures also share it.
    fixtures = {s.subject for s in scans if s.synthetic}
    for attr, code, label in (
        ("pet_series_pseudonym", "SCAN_LINKED_TO_MULTIPLE_SUBJECTS", "PET series UID"),
        ("pet_content_sha256", "SCAN_LINKED_TO_MULTIPLE_SUBJECTS", "PET voxel content"),
        ("patient_id_sha256", "SUBJECT_PSEUDONYM_SHARED", "DICOM patient identifier"),
    ):
        owners: dict[str, set[str]] = defaultdict(set)
        for s in scans:
            v = getattr(s, attr)
            if v:
                owners[v].add(s.subject)
        for _, subj_set in sorted(owners.items()):
            if len(subj_set) < 2:
                continue
            real = subj_set - fixtures
            for subj in sorted(subj_set):
                if len(real) >= 2 and subj in real:
                    add(code, PAIRING_CODES[code][0], subj, [], f"same {label} under subjects {sorted(real)}"
                        + (f" (also reused by declared synthetic fixtures {sorted(subj_set & fixtures)})" if subj_set & fixtures else ""))  # fmt: skip
                else:
                    add(code, "INFO", subj, [], f"same {label} under subjects {sorted(subj_set)} "
                        "(declared synthetic fixture reuse)")  # fmt: skip
    findings.sort(
        key=lambda f: (-SEVERITY_ORDER.index(f.severity), f.subject, f.code, f.timepoints)
    )
    counts = Counter(f.severity for f in findings)
    blocked = sorted({f.subject for f in findings if f.severity == "BLOCKING"})
    review = sorted({f.subject for f in findings if f.severity == "NEEDS_REVIEW"})
    status = "BLOCKED" if blocked else "NEEDS_REVIEW" if review else "OK"
    return {
        "schema": PAIRING_AUDIT_SCHEMA,
        "status": status,
        "subjects": len(by_subject),
        "scans": len(scans),
        "severity_counts": {k: counts.get(k, 0) for k in SEVERITY_ORDER},
        "subjects_blocked": blocked,
        "subjects_needing_review": review,
        "findings": [f.model_dump() for f in findings],
        "note": "Reporting only: pairs are never re-paired or dropped and no verdict is changed. "
        "A BLOCKING finding means the subject's pair results must not be used until the layout "
        "is corrected.",
    }


def pairing_status_by_subject(report: dict[str, Any]) -> dict[str, str]:
    """subject -> worst severity of its findings ('OK' when none is above INFO). Dataset-wide
    findings (subject '*') apply to every subject."""
    rank = SEVERITY_ORDER.index
    glob = max((f["severity"] for f in report["findings"] if f["subject"] == "*"),
               key=rank, default="INFO")  # fmt: skip
    worst: dict[str, str] = {}
    for f in report["findings"]:
        if f["subject"] != "*":
            worst[f["subject"]] = max(worst.get(f["subject"], glob), f["severity"], key=rank)
    out = {k: ("OK" if v == "INFO" else v) for k, v in sorted(worst.items())}
    out["*"] = "OK" if glob == "INFO" else glob
    return out


def scan_identities_from_audit(audit: Any, layout: Any) -> list[ScanIdentity]:
    """Build ScanIdentity rows from a TrialAudit's timepoints and the trial layout."""
    out = []
    for t in audit.timepoints:
        date = tracer = None
        if t.protocol is not None:
            dt = t.protocol.acquisition.acquisition_start_datetime
            date = str(dt.value)[:10] if dt.known else None
            tracer = _tracer_name(t.protocol)
        d = layout.scans.get(t.subject_id, {}).get(t.timepoint)
        out.append(ScanIdentity(
            subject=t.subject_id, timepoint=t.timepoint,
            patient_id_sha256=patient_id_sha256(d) if d else None,
            pet_series_pseudonym=t.pet_series_pseudonym, pet_content_sha256=t.pet_content_sha256,
            acquisition_date=date, tracer=tracer,
            synthetic=bool(t.synthetic_perturbation) or f"{t.subject_id}/{t.timepoint}" in layout.synthetic,
        ))  # fmt: skip
    return out


def _tracer_name(protocol: Any) -> str | None:
    """Same precedence as the protocol fingerprint: coded radiopharmaceutical, then free text."""
    ac = protocol.acquisition
    ev = ac.radiopharmaceutical_code if ac.radiopharmaceutical_code.known else ac.tracer
    return str(ev.value) if ev.known else None
