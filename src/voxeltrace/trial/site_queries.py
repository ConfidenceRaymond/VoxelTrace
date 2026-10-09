"""Deterministic DRAFT site queries from reason codes (VT-SITE-QUERY-1). Never sent.

Each query is generated from a fixed template keyed by the deterministic reason code; the
code and the evidence stay visible next to the wording. An AI may later rephrase the text,
but never remove or change the reason code, the evidence or the request.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

LABEL = "DRAFT SITE QUERY"
TEMPLATES: dict[str, str] = {
    "RECONSTRUCTION_INCOMPLETE": "The PET series does not record the full reconstruction "
    "(method, iterations, subsets, post-filter, TOF, PSF). Please provide the scanner "
    "reconstruction protocol for this scan, or re-export with the standard reconstruction "
    "attributes populated.",
    "AMBIGUOUS_RECONSTRUCTION": "Reconstruction identity between baseline and follow-up cannot "
    "be established from the images. Please provide the reconstruction protocol used at both "
    "timepoints (a scanner protocol export or a signed physicist record).",
    "MISSING_PATIENTSIZE": "Patient height is absent. Please provide height at the time of each "
    "scan (needed for lean-body-mass SUL); ensure de-identification retains patient "
    "characteristics (DICOM PS3.15 E.3.7).",
    "UNSUPPORTED_PATIENTSEX_FOR_SUL": "Patient sex is not recorded as M or F, so lean-body-mass "
    "SUL cannot be computed. Please confirm whether sex can be provided.",
    "ANTHROPOMETRICS_MISSING": "Height/weight/sex needed for SUL are missing. Please provide "
    "them from the site record.",
    "DECAY_FACTOR_INCONSISTENT": "The stored DecayFactor does not match the frame reference time "
    "under DICOM definitions. Please provide the original export and the scanner's decay-"
    "correction reference (vendor documentation); values will not be overridden.",
    "DECAY_FACTOR_UNVERIFIED": "DecayFactor / FrameReferenceTime are absent, so the decay "
    "correction cannot be cross-checked. Please confirm whether an export with these "
    "attributes is available.",
    "CT_NOT_IN_PET_FRAME": "No CT shares the PET frame of reference. Please provide the CT "
    "acquired with this PET (same FrameOfReferenceUID).",
    "CT_NOT_VOLUMETRIC": "The CT in the PET frame of reference is a single image. Please provide "
    "the volumetric attenuation/localisation CT.",
    "TRACER_UNKNOWN": "The radiopharmaceutical is not recorded. Please confirm the tracer for "
    "each scan.",
    "MISSING_REQUIRED_TAG": "A required DICOM attribute is missing (see field). Please re-export "
    "with it populated or provide the value from the site record.",
    "ANONYMIZATION_LOSS": "Quantitative attributes appear to have been removed during "
    "de-identification (see evidence). Please re-export with patient characteristics and "
    "timing retained.",
    "UNSUPPORTED_UNITS": "The PET is not in activity-concentration units (BQML). Please provide "
    "the original quantitative reconstruction.",
    "MISSING_INJECTION_TIME": "The injection time is missing. Please provide it from the site "
    "record.",
    "SUV_REFUSED": "The quantitative metadata were refused by the strict SUV validator (see "
    "evidence). Please review the listed attributes with the site.",
    "LESION_TARGET_MISSING": "No reviewed baseline lesion segmentation / target is available, "
    "so PERCIST baseline measurability cannot be assessed. Please provide the baseline target "
    "lesion annotation (it will be reviewed by a human before use).",
    "AMBIGUOUS_TIMING": "Uptake time could not be validated. Please confirm injection and scan "
    "start times.",
}


def site_queries(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """``items``: dicts with site, subject, scan, reason_code, field, evidence.
    Returns one DRAFT query per (site, subject, reason_code) with a known template."""
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for it in items:
        if it["reason_code"] in TEMPLATES:
            grouped[(it.get("site") or "UNASSIGNED", it["subject"], it["reason_code"])].append(it)
    out = []
    for (site, subject, code), its in sorted(grouped.items()):
        out.append(
            {
                "label": LABEL,
                "site": site,
                "subject": subject,
                "reason_code": code,
                "scans": sorted({str(i.get("scan")) for i in its}),
                "fields": sorted({str(i.get("field")) for i in its if i.get("field")}),
                "evidence": sorted(
                    {str(i.get("evidence"))[:200] for i in its if i.get("evidence")}
                ),
                "query_text": TEMPLATES[code],
                "sent": False,
            }
        )
    return out


def site_queries_md(queries: list[dict[str, Any]]) -> str:
    lines = [
        "# DRAFT SITE QUERIES (deterministic; not sent)",
        "",
        "Generated from reason codes. Review and edit before any contact with a site.",
        "",
    ]
    for q in queries:
        lines += [
            f"## {LABEL}: {q['site']} / {q['subject']} / `{q['reason_code']}`",
            "",
            f"- Scans: {', '.join(q['scans'])}",
            f"- Fields: {', '.join(q['fields']) or '-'}",
            f"- Evidence: {'; '.join(q['evidence']) or '-'}",
            "",
            q["query_text"],
            "",
        ]
    return "\n".join(lines) + "\n"
