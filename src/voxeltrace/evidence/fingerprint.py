"""Canonical protocol fingerprint (VT-PROTOCOL-FP-1) and fingerprint comparison.

A fingerprint is a FIXED, ordered list of protocol fields built from the extracted
ProtocolEvidence (same extractors the rules use). Every field is always present: a missing
value is serialized explicitly as status MISSING, never dropped. Each field carries a trust
level (reconstruction trust model): LEVEL_A structured standard attribute (incl. values
derived from standard geometry/timing), LEVEL_D vendor free text, LEVEL_U unsupported, plus
NOT_APPLICABLE / NONE (missing).

Two hashes:
  protocol_fingerprint_sha256  protocol-defining fields only (scanner, software, reconstruction,
                               corrections, units, geometry, tracer): identical protocols on
                               different patients give the same hash
  scan_fingerprint_sha256      all fields incl. scan-specific uptake and injected activity

``compare_protocol_fingerprints`` is a REPORTING layer (drift, audit tables). Rule verdicts
still come from ``compare_protocols`` / the rule sets; the comparison mirrors their policy
(including the "same reconstruction text implies same iterations/subsets/TOF/PSF" fallback,
reported at LEVEL_D) so the two never disagree on identity.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from voxeltrace.evidence.comparability import (
    ACTIVITY_REL_TOLERANCE,
    CORRECTIONS_COMPARED,
    UPTAKE_TOLERANCE_S,
    VOXEL_TOLERANCE_MM,
)
from voxeltrace.evidence.protocol import ProtocolEvidence

FP_SCHEMA = "VT-PROTOCOL-FP-1"
Trust = Literal["LEVEL_A", "LEVEL_B", "LEVEL_C", "LEVEL_D", "LEVEL_E", "LEVEL_U", "NONE", "NOT_APPLICABLE"]  # fmt: skip
_A = {"standard_tag", "standard_enumeration", "derived_from_geometry", "derived_from_timing",
      "validated_suv_input"}  # fmt: skip

# (field, quantitative relevance, severity if DIFFERENT, rule impact, in protocol hash)
FIELD_POLICY: dict[str, tuple[str, str, list[str], bool]] = {
    "modality": ("HIGH", "DIFFERENT", ["all"], True),
    "tracer": ("HIGH", "DIFFERENT", ["VT-TRACER-SAME"], True),
    "radionuclide": ("HIGH", "DIFFERENT", ["VT-PROTOCOL-IDENTITY"], True),
    "manufacturer": ("HIGH", "DIFFERENT", ["VT-PROTOCOL-IDENTITY", "QIBA-SAME-SYSTEM", "PERCIST-SAME-SCANNER-SOFTWARE", "EANM-SAME-SYSTEM-SETTINGS"], True),
    "scanner_model": ("HIGH", "DIFFERENT", ["VT-PROTOCOL-IDENTITY", "QIBA-SAME-SYSTEM", "PERCIST-SAME-SCANNER-SOFTWARE", "EANM-SAME-SYSTEM-SETTINGS"], True),
    "software": ("MEDIUM", "WARNING", ["QIBA-SAME-SYSTEM", "PERCIST-SAME-SCANNER-SOFTWARE"], True),
    "scanner_architecture": ("MEDIUM", "INFO", [], True),
    "series_type": ("LOW", "INFO", [], True),
    "acquisition_mode_2d_3d": ("MEDIUM", "INFO", [], True),
    "matrix": ("MEDIUM", "INFO", [], True),
    "voxel_size_mm": ("HIGH", "DIFFERENT", ["VT-PROTOCOL-IDENTITY"], True),
    "slice_thickness_mm": ("MEDIUM", "WARNING", [], True),
    "reconstruction_method": ("HIGH", "DIFFERENT", ["VT-PROTOCOL-IDENTITY", "EANM-SAME-SYSTEM-SETTINGS"], True),
    "iterations": ("HIGH", "DIFFERENT", ["VT-PROTOCOL-IDENTITY", "EANM-SAME-SYSTEM-SETTINGS"], True),
    "subsets": ("HIGH", "DIFFERENT", ["VT-PROTOCOL-IDENTITY", "EANM-SAME-SYSTEM-SETTINGS"], True),
    "filter_kernel": ("HIGH", "DIFFERENT", ["VT-PROTOCOL-IDENTITY", "EANM-SAME-SYSTEM-SETTINGS"], True),
    "time_of_flight": ("HIGH", "DIFFERENT", ["VT-PROTOCOL-IDENTITY", "EANM-SAME-SYSTEM-SETTINGS"], True),
    "psf_resolution_modelling": ("HIGH", "DIFFERENT", ["VT-PROTOCOL-IDENTITY", "EANM-SAME-SYSTEM-SETTINGS"], True),
    "corrections": ("HIGH", "DIFFERENT", ["VT-PROTOCOL-IDENTITY"], True),
    "harmonization": ("MEDIUM", "WARNING", ["EANM-EARL-RECON"], True),
    "units": ("HIGH", "DIFFERENT", ["VT-PROTOCOL-IDENTITY", "VT-SUV-BOTH"], True),
    "decay_correction": ("HIGH", "DIFFERENT", ["VT-PROTOCOL-IDENTITY", "VT-SUV-BOTH"], True),
    "uptake_interval_s": ("HIGH", "WARNING", ["QIBA-UPTAKE-DIFF", "EANM-UPTAKE-DIFF", "PERCIST-UPTAKE-DIFF"], False),
    "injected_activity_bq": ("MEDIUM", "WARNING", ["PERCIST-DOSE-DIFF"], False),
}  # fmt: skip
FIELDS = tuple(FIELD_POLICY)
RECON_IMPLIED = ("iterations", "subsets", "time_of_flight", "psf_resolution_modelling")


class FPField(BaseModel):
    value: Any = None
    status: Literal["PRESENT", "MISSING", "AMBIGUOUS", "UNSUPPORTED", "NOT_APPLICABLE"]
    trust: Trust
    source: str | None = None


class ProtocolFingerprint(BaseModel):
    schema_version: Literal["VT-PROTOCOL-FP-1"] = FP_SCHEMA
    series_pseudonym: str | None = None
    fields: dict[str, FPField]
    completeness: dict[str, Any] = Field(default_factory=dict)
    protocol_fingerprint_sha256: str = ""
    scan_fingerprint_sha256: str = ""

    def canonical(self, *, protocol_only: bool) -> str:
        keep = [f for f in FIELDS if FIELD_POLICY[f][3] or not protocol_only]
        doc = {
            "schema": FP_SCHEMA,
            "fields": [
                [f, _canon(self.fields[f].value), self.fields[f].status, self.fields[f].trust]
                for f in keep
            ],
        }
        return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _canon(v: Any) -> Any:
    if isinstance(v, float):
        return round(v, 6)
    if isinstance(v, (list, tuple)):
        return [_canon(x) for x in v]
    if isinstance(v, str):
        return " ".join(v.split())
    return v


def _from(ev, name: str) -> FPField:
    st = {"PRESENT": "PRESENT", "MISSING": "MISSING", "PRESENT_BUT_AMBIGUOUS": "AMBIGUOUS",
          "UNSUPPORTED": "UNSUPPORTED"}.get(ev.status, "MISSING")  # fmt: skip
    if st == "MISSING" or ev.value is None and st != "UNSUPPORTED":
        return FPField(status="MISSING", trust="NONE", source=ev.source)
    if st == "UNSUPPORTED":
        return FPField(status="UNSUPPORTED", trust="LEVEL_U", source=ev.source)
    trust = "LEVEL_D" if ev.derivation == "free_text_pattern" else "LEVEL_A"
    if ev.derivation not in _A and ev.derivation != "free_text_pattern" and ev.derivation:
        trust = "LEVEL_U"
    v = list(ev.value) if isinstance(ev.value, tuple) else ev.value
    return FPField(value=v, status=st, trust=trust, source=ev.source)  # type: ignore[arg-type]


def architecture_of(model: str | None) -> str | None:
    m = (model or "").casefold()
    if not m:
        return None
    if "uexplorer" in m:
        return "TOTAL_BODY"
    if "quadra" in m:
        return "LONG_AFOV"
    if any(k in m for k in ("mmr", "signa pet", "upmr", "pet/mr")):
        return "PET_MR"
    return "CONVENTIONAL_AFOV"


def build_fingerprint(
    proto: ProtocolEvidence,
    *,
    series_pseudonym: str | None = None,
    harmonization: str | None = None,
) -> ProtocolFingerprint:
    sc, ac, rc, co = proto.scanner, proto.acquisition, proto.reconstruction, proto.corrections
    f: dict[str, FPField] = {
        "modality": _from(sc.modality, "modality"),
        "tracer": _from(ac.radiopharmaceutical_code if ac.radiopharmaceutical_code.known else ac.tracer, "tracer"),
        "radionuclide": _from(ac.radionuclide, "radionuclide"),
        "manufacturer": _from(sc.manufacturer, "manufacturer"),
        "scanner_model": _from(sc.manufacturer_model_name, "scanner_model"),
        "software": _from(sc.software_versions, "software"),
        "series_type": _from(ac.series_type, "series_type"),
        "acquisition_mode_2d_3d": FPField(status="MISSING", trust="NONE",
                                          source="not extracted: no classic PET IOD attribute"),
        "voxel_size_mm": _from(rc.voxel_size_mm, "voxel_size_mm"),
        "slice_thickness_mm": _from(rc.slice_thickness_mm, "slice_thickness_mm"),
        "reconstruction_method": _from(rc.reconstruction_method, "reconstruction_method"),
        "iterations": _from(rc.iterations, "iterations"),
        "subsets": _from(rc.subsets, "subsets"),
        "filter_kernel": _from(rc.convolution_kernel, "filter_kernel"),
        "time_of_flight": _from(rc.time_of_flight, "time_of_flight"),
        "psf_resolution_modelling": _from(rc.psf_resolution_modelling, "psf_resolution_modelling"),
        "units": _from(ac.image_units, "units"),
        "decay_correction": _from(ac.decay_correction, "decay_correction"),
        "uptake_interval_s": _from(ac.uptake_interval_s, "uptake_interval_s"),
        "injected_activity_bq": _from(ac.injected_activity_bq, "injected_activity_bq"),
    }  # fmt: skip
    arch = architecture_of(
        sc.manufacturer_model_name.value if sc.manufacturer_model_name.known else None
    )
    f["scanner_architecture"] = (
        FPField(value=arch, status="PRESENT", trust="LEVEL_A", source="derived from model name")
        if arch
        else FPField(status="MISSING", trust="NONE")
    )
    mr, mc = rc.matrix_rows, rc.matrix_columns
    f["matrix"] = (
        FPField(
            value=[mr.value, mc.value], status="PRESENT", trust="LEVEL_A", source="Rows/Columns"
        )
        if mr.known and mc.known
        else FPField(status="MISSING", trust="NONE")
    )
    applied = co.applied_set()
    f["corrections"] = (
        FPField(value=sorted(applied & set(CORRECTIONS_COMPARED)), status="PRESENT",
                trust="LEVEL_A", source="CorrectedImage (0028,0051)")
        if applied is not None
        else FPField(status="MISSING", trust="NONE", source="CorrectedImage")
    )  # fmt: skip
    f["harmonization"] = (
        FPField(
            value=harmonization, status="PRESENT", trust="LEVEL_C", source="trial configuration"
        )
        if harmonization
        else FPField(status="MISSING", trust="NONE", source="not encoded in DICOM; not configured")
    )
    fields = {k: f[k] for k in FIELDS}
    present = [k for k, v in fields.items() if v.status == "PRESENT"]
    fp = ProtocolFingerprint(
        series_pseudonym=series_pseudonym,
        fields=fields,
        completeness={
            "present": len(present),
            "total": len(FIELDS),
            "missing": [k for k, v in fields.items() if v.status != "PRESENT"],
            "by_trust": {t: sum(v.trust == t for v in fields.values()) for t in
                         ("LEVEL_A", "LEVEL_B", "LEVEL_C", "LEVEL_D", "LEVEL_U", "NONE")},
        },
    )  # fmt: skip
    fp.protocol_fingerprint_sha256 = hashlib.sha256(
        fp.canonical(protocol_only=True).encode()
    ).hexdigest()
    fp.scan_fingerprint_sha256 = hashlib.sha256(
        fp.canonical(protocol_only=False).encode()
    ).hexdigest()
    return fp


# ------------------------------------------------------------------ comparison

Result = Literal["IDENTICAL", "COMPATIBLE_WITH_WARNINGS", "DIFFERENT", "INSUFFICIENT_INFORMATION"]


class FieldDifference(BaseModel):
    field: str
    status: Literal["SAME", "WITHIN_TOLERANCE", "DIFFERENT", "UNKNOWN", "IMPLIED_SAME"]
    baseline: Any = None
    followup: Any = None
    trust: str
    severity: Literal["DIFFERENT", "WARNING", "INFO", "NONE"]
    quantitative_relevance: str
    rule_impact: list[str]
    note: str = ""


class FingerprintComparison(BaseModel):
    schema_version: Literal["VT-PROTOCOL-FP-1"] = FP_SCHEMA
    result: Result
    differences: list[FieldDifference]
    blocking_unknown: list[str]
    blocking_different: list[str]
    warnings: list[str]


_ORDER = [
    "LEVEL_A",
    "LEVEL_B",
    "LEVEL_C",
    "LEVEL_D",
    "LEVEL_E",
    "LEVEL_U",
    "NONE",
    "NOT_APPLICABLE",
]


def _weaker(a: str, b: str) -> str:
    return max(a, b, key=_ORDER.index)


def _norm(v: Any) -> Any:
    if isinstance(v, str):
        return " ".join(v.split()).casefold()
    if isinstance(v, list):
        return [_norm(x) for x in v]
    return v


def _equal(field: str, a: Any, b: Any) -> str:
    if field == "voxel_size_mm":
        ok = all(abs(x - y) <= VOXEL_TOLERANCE_MM for x, y in zip(a, b, strict=True))
        return ("SAME" if a == b else "WITHIN_TOLERANCE") if ok else "DIFFERENT"
    if field == "uptake_interval_s":
        return "WITHIN_TOLERANCE" if abs(a - b) <= UPTAKE_TOLERANCE_S else "DIFFERENT"
    if field == "injected_activity_bq":
        return (
            "WITHIN_TOLERANCE" if abs(a - b) <= ACTIVITY_REL_TOLERANCE * max(a, b) else "DIFFERENT"
        )
    return "SAME" if _norm(a) == _norm(b) else "DIFFERENT"


def compare_protocol_fingerprints(
    a: ProtocolFingerprint, b: ProtocolFingerprint
) -> FingerprintComparison:
    diffs: list[FieldDifference] = []
    same_text = (
        a.fields["reconstruction_method"].status == "PRESENT"
        and b.fields["reconstruction_method"].status == "PRESENT"
        and _norm(a.fields["reconstruction_method"].value)
        == _norm(b.fields["reconstruction_method"].value)
    )
    for name in FIELDS:
        rel, sev, impact, _ = FIELD_POLICY[name]
        fa, fb = a.fields[name], b.fields[name]
        trust = _weaker(fa.trust, fb.trust)
        if fa.status == "PRESENT" and fb.status == "PRESENT":
            st = _equal(name, fa.value, fb.value)
            diffs.append(FieldDifference(field=name, status=st, baseline=fa.value, followup=fb.value,
                                         trust=trust, severity=sev if st == "DIFFERENT" else "NONE",
                                         quantitative_relevance=rel, rule_impact=impact))  # fmt: skip
        elif name in RECON_IMPLIED and same_text:
            diffs.append(FieldDifference(
                field=name, status="IMPLIED_SAME", baseline=fa.value, followup=fb.value,
                trust="LEVEL_D", severity="WARNING", quantitative_relevance=rel, rule_impact=impact,
                note="not encoded; identical reconstruction description implies identity (same "
                "policy as compare_protocols)"))  # fmt: skip
        else:
            # unknown severity mirrors compare_protocols: unknown iterations/subsets/TOF/PSF
            # and filter are warnings there; other DIFFERENT-severity fields block
            soft = name in RECON_IMPLIED or name == "filter_kernel"
            unk_sev = "DIFFERENT" if sev == "DIFFERENT" and not soft else (
                "WARNING" if sev in ("DIFFERENT", "WARNING") else "INFO")  # fmt: skip
            diffs.append(FieldDifference(field=name, status="UNKNOWN", baseline=fa.value,
                                         followup=fb.value, trust=trust, severity=unk_sev,
                                         quantitative_relevance=rel, rule_impact=impact,
                                         note=f"{fa.status} / {fb.status}"))  # fmt: skip
    blocking_unknown = [
        d.field for d in diffs if d.status == "UNKNOWN" and d.severity == "DIFFERENT"
    ]
    blocking_different = [
        d.field for d in diffs if d.status == "DIFFERENT" and d.severity == "DIFFERENT"
    ]
    warnings = [d.field for d in diffs if d.severity == "WARNING"
                and d.status in ("DIFFERENT", "UNKNOWN", "IMPLIED_SAME")]  # fmt: skip
    if blocking_different:
        result: Result = "DIFFERENT"
    elif blocking_unknown:
        result = "INSUFFICIENT_INFORMATION"
    elif warnings or any(d.status == "DIFFERENT" for d in diffs):
        result = "COMPATIBLE_WITH_WARNINGS"
    else:
        result = "IDENTICAL"
    return FingerprintComparison(result=result, differences=diffs, blocking_unknown=blocking_unknown,
                                 blocking_different=blocking_different, warnings=warnings)  # fmt: skip


# fields of VT-PROTOCOL-IDENTITY (rules/common.py RECON_CHECKS; uptake/dose/tracer excluded)
IDENTITY_FIELDS = (
    "manufacturer", "scanner_model", "units", "decay_correction", "corrections", "voxel_size_mm",
    "reconstruction_method", "iterations", "subsets", "time_of_flight",
    "psf_resolution_modelling", "filter_kernel",
)  # fmt: skip


def identity_view(c: FingerprintComparison) -> Literal["PASS", "FAIL", "UNKNOWN"]:
    """The comparison restricted to VT-PROTOCOL-IDENTITY's fields, as PASS/FAIL/UNKNOWN."""
    d = [x for x in c.differences if x.field in IDENTITY_FIELDS]
    if any(x.status == "DIFFERENT" for x in d):
        return "FAIL"
    if any(x.status == "UNKNOWN" for x in d):  # the rule blocks on ANY unknown field
        return "UNKNOWN"
    return "PASS"
