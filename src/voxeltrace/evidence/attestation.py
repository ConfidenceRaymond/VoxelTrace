"""External reconstruction attestation (trust LEVEL_C): schema, loading and validation.

QIBA-ONLY evidence path. The QIBA FDG-PET/CT Profile v1.14 accepts metadata that the scanner
does not capture from "trial documentation, e.g., case report forms" and lists
"Reconstruction method" among the fields to record (lines 934-939; Appendix E). EANM 2.0 and
PERCIST 1.0 are silent (docs/reconstruction_attestation_policy.md). Therefore:

  * only the QIBA rule set reads attestations (rules/qiba_identity.py);
  * an attestation can at most give ESTABLISHED_WITH_WARNING, never DICOM-proven identity;
  * nothing in VoxelTrace creates or signs an attestation.

Validation (``validate_attestation``) checks, in order:
  schema / simulated flag, attestor role (+ countersignature for technologists),
  source type (charter policy), source and corroborating document hash binding,
  subject / timepoint / study / series binding, scanner / model / software binding.
Status: VALID, EXPECTED_PROTOCOL_ONLY (charter without scan-level corroboration),
STALE (a bound document, series, study, scanner or software changed) or INVALID.
Rule-scope is checked by the consuming rule (``in_scope``).
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

SCHEMA = "voxeltrace.recon-attestation/2"

AttestorRole = Literal[
    "QUALIFIED_PET_PHYSICIST",
    "NUCLEAR_MEDICINE_PHYSICIST",
    "IMAGING_CORE_QC_LEAD",
    "SITE_PET_TECHNOLOGIST",
    # expressible so that they can be REJECTED explicitly:
    "INVESTIGATOR",
    "RADIOLOGIST",
    "STUDY_COORDINATOR",
    "VENDOR_REPRESENTATIVE",
    "OTHER",
]
QUALIFIED_ROLES = ("QUALIFIED_PET_PHYSICIST", "NUCLEAR_MEDICINE_PHYSICIST", "IMAGING_CORE_QC_LEAD")
COUNTERSIGN_REQUIRED = ("SITE_PET_TECHNOLOGIST",)

SourceType = Literal[
    "SCANNER_PROTOCOL_EXPORT",
    "SITE_PROTOCOL_RECORD",
    "SIGNED_ATTESTATION",
    "TRIAL_IMAGING_CHARTER",
    "UNSIGNED_NOTE",
]
# a charter defines the EXPECTED protocol; it needs one of these, scan-bound, to count
CHARTER_CORROBORATION = ("SCANNER_PROTOCOL_EXPORT", "SITE_PROTOCOL_RECORD", "SIGNED_ATTESTATION")

RECON_PARAMETERS = (
    "reconstruction_method",
    "iterations",
    "subsets",
    "post_filter",
    "time_of_flight",
    "psf_resolution_modelling",
)
Status = Literal["VALID", "EXPECTED_PROTOCOL_ONLY", "STALE", "INVALID"]
_HEX64 = re.compile(r"[0-9a-f]{64}")


class SourceDocument(BaseModel):
    source_type: SourceType
    path: str = Field(min_length=1, description="relative to the attestation file")
    sha256: str

    @field_validator("sha256")
    @classmethod
    def _sha(cls, v: str) -> str:
        if not _HEX64.fullmatch(v):
            raise ValueError("sha256 must be 64 lowercase hex characters")
        return v


class Countersignature(BaseModel):
    signer_id: str = Field(min_length=1)
    signer_role: AttestorRole
    signed_at: datetime
    qc_responsibility_documented: bool = False


class CharterBinding(BaseModel):
    """Applicability of a trial imaging charter: all four are required."""

    site: str = Field(min_length=1)
    scanner_model: str = Field(min_length=1)
    software_version_or_period: str = Field(min_length=1)
    scan_level_applicability: str = Field(
        min_length=1, description="study/series list or explicit scan-level statement"
    )


class ReconstructionAttestation(BaseModel):
    """One scan's externally attested reconstruction (trust LEVEL_C). Never machine-made."""

    schema_version: Literal["voxeltrace.recon-attestation/2"] = SCHEMA
    attestation_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    timepoint: str = Field(min_length=1)
    study_instance_uid: str = Field(min_length=1)
    series_instance_uid: str = Field(min_length=1)
    manufacturer: str = Field(min_length=1)
    manufacturer_model_name: str = Field(min_length=1)
    software_version: str = Field(min_length=1)
    reconstruction_method: str | None = None
    iterations: int | None = None
    subsets: int | None = None
    post_filter: str | None = None
    time_of_flight: bool | None = None
    psf_resolution_modelling: bool | None = None
    corrections: list[str] | None = Field(default=None, description="e.g. ATTN, SCAT, DECY")
    source: SourceDocument
    corroborating_sources: list[SourceDocument] = Field(default_factory=list)
    charter_binding: CharterBinding | None = None
    attestor_id: str = Field(min_length=1)
    attestor_role: AttestorRole
    attestor_qc_responsibility_documented: bool = False
    countersignature: Countersignature | None = None
    attested_at: datetime
    rule_scope: list[str] = Field(min_length=1)
    notes: str = ""
    confidence: Literal["CONFIRMED", "BELIEVED"]
    trust_level: Literal["LEVEL_C"] = "LEVEL_C"
    simulated: bool = False

    def value(self, parameter: str) -> Any:
        return getattr(self, parameter)


class AttestationOutcome(BaseModel):
    attestation_id: str
    subject_id: str
    timepoint: str
    status: Status
    reasons: list[str] = Field(default_factory=list)
    attestor_role: str | None = None
    source_type: str | None = None
    source_sha256: str | None = None
    rule_scope: list[str] = Field(default_factory=list)
    trust_level: str = "LEVEL_C"
    attestation: ReconstructionAttestation | None = Field(default=None, exclude=True)

    def in_scope(self, ruleset_id: str) -> bool:
        return self.status == "VALID" and ruleset_id in self.rule_scope


class ScanFacts(BaseModel):
    """What the audited scan actually is (from its DICOM), for binding checks."""

    subject_id: str
    timepoint: str
    study_instance_uid: str | None = None
    series_instance_uid: str | None = None
    manufacturer: str | None = None
    manufacturer_model_name: str | None = None
    software_versions: list[str] | None = None


# ------------------------------------------------------------------ loading


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_attestations(
    path: str | Path | None, *, allow_simulated: bool = False
) -> tuple[dict[str, list[ReconstructionAttestation]], list[AttestationOutcome]]:
    """Read ``{schema, attestations: [...]}``. Returns ({"subject/timepoint": [...]},
    outcomes for records rejected at load time). A missing file means no attestations."""
    if path is None or not Path(path).exists():
        return {}, []
    raw = yaml.safe_load(Path(path).read_text()) or {}
    if raw.get("schema") != SCHEMA:
        raise ValueError(f"attestation file schema must be {SCHEMA!r}")
    good: dict[str, list[ReconstructionAttestation]] = {}
    rejected: list[AttestationOutcome] = []
    for i, rec in enumerate(raw.get("attestations") or []):
        try:
            att = ReconstructionAttestation.model_validate(rec)
        except ValidationError as exc:
            rejected.append(
                AttestationOutcome(
                    attestation_id=str((rec or {}).get("attestation_id", f"#{i}")),
                    subject_id=str((rec or {}).get("subject_id", "")),
                    timepoint=str((rec or {}).get("timepoint", "")),
                    status="INVALID",
                    reasons=[f"SCHEMA_INVALID: {e['loc']} {e['msg']}" for e in exc.errors()],
                )
            )
            continue
        if att.simulated and not allow_simulated:
            rejected.append(_outcome(att, "INVALID", ["SIMULATED_NOT_ALLOWED_IN_PRODUCTION"]))
            continue
        good.setdefault(f"{att.subject_id}/{att.timepoint}", []).append(att)
    return good, rejected


# ------------------------------------------------------------------ validation


def _outcome(att: ReconstructionAttestation, status: Status, reasons: list[str]):
    return AttestationOutcome(
        attestation_id=att.attestation_id,
        subject_id=att.subject_id,
        timepoint=att.timepoint,
        status=status,
        reasons=reasons,
        attestor_role=att.attestor_role,
        source_type=att.source.source_type,
        source_sha256=att.source.sha256,
        rule_scope=list(att.rule_scope),
        attestation=att,
    )


def role_problems(att: ReconstructionAttestation) -> list[str]:
    role = att.attestor_role
    if role in QUALIFIED_ROLES:
        if role == "IMAGING_CORE_QC_LEAD" and not att.attestor_qc_responsibility_documented:
            return ["QC_LEAD_WITHOUT_DOCUMENTED_PET_QC_RESPONSIBILITY"]
        return []
    if role in COUNTERSIGN_REQUIRED:
        cs = att.countersignature
        if cs is None:
            return ["TECHNOLOGIST_REQUIRES_COUNTERSIGNATURE"]
        if cs.signer_role not in QUALIFIED_ROLES:
            return [f"COUNTERSIGNER_ROLE_NOT_ACCEPTED:{cs.signer_role}"]
        if cs.signer_role == "IMAGING_CORE_QC_LEAD" and not cs.qc_responsibility_documented:
            return ["COUNTERSIGNER_QC_LEAD_WITHOUT_DOCUMENTED_PET_QC_RESPONSIBILITY"]
        if cs.signer_id == att.attestor_id:
            return ["SELF_COUNTERSIGNATURE"]
        return []
    return [f"ATTESTOR_ROLE_NOT_ACCEPTED:{role}"]


def _norm(v: Any) -> str:
    if isinstance(v, (list, tuple)):
        return "\\".join(_norm(x) for x in v)
    return " ".join(str(v).casefold().split())


def validate_attestation(
    att: ReconstructionAttestation, scan: ScanFacts, document_root: Path
) -> AttestationOutcome:
    invalid: list[str] = []
    stale: list[str] = []
    if att.confidence != "CONFIRMED":
        invalid.append("CONFIDENCE_NOT_CONFIRMED")
    invalid += role_problems(att)
    if att.source.source_type == "UNSIGNED_NOTE":
        invalid.append("UNSIGNED_NOTE_NOT_ACCEPTED")
    for doc in [att.source, *att.corroborating_sources]:
        p = document_root / doc.path
        if not p.is_file():
            invalid.append(f"SOURCE_DOCUMENT_MISSING:{doc.path}")
        elif sha256_file(p) != doc.sha256:
            stale.append(f"SOURCE_DOCUMENT_CHANGED:{doc.path}")
    # binding to the audited scan
    if att.subject_id != scan.subject_id:
        invalid.append("SUBJECT_MISMATCH")
    if att.timepoint != scan.timepoint:
        invalid.append("TIMEPOINT_MISMATCH")
    for name, want, have in (
        ("STUDY", att.study_instance_uid, scan.study_instance_uid),
        ("SERIES", att.series_instance_uid, scan.series_instance_uid),
    ):
        if have is None:
            invalid.append(f"{name}_UNVERIFIABLE")
        elif want != have:
            stale.append(f"{name}_CHANGED")
    for name, want, have in (
        ("MANUFACTURER", att.manufacturer, scan.manufacturer),
        ("MODEL", att.manufacturer_model_name, scan.manufacturer_model_name),
    ):
        if have is None:
            invalid.append(f"{name}_UNVERIFIABLE")
        elif _norm(want) != _norm(have):
            stale.append(f"{name}_CHANGED")
    if scan.software_versions is None:
        invalid.append("SOFTWARE_UNVERIFIABLE")
    elif _norm(att.software_version) not in {_norm(s) for s in scan.software_versions}:
        stale.append("SOFTWARE_CHANGED")
    if invalid:
        return _outcome(att, "INVALID", invalid + stale)
    if stale:
        return _outcome(att, "STALE", stale)
    if att.source.source_type == "TRIAL_IMAGING_CHARTER":
        corr = [d for d in att.corroborating_sources if d.source_type in CHARTER_CORROBORATION]
        if att.charter_binding is None or not corr:
            return _outcome(
                att,
                "EXPECTED_PROTOCOL_ONLY",
                [
                    "CHARTER_DEFINES_EXPECTED_PROTOCOL_ONLY"
                    + ("" if att.charter_binding else ":NO_CHARTER_BINDING")
                    + ("" if corr else ":NO_SCAN_LEVEL_CORROBORATION")
                ],
            )
    return _outcome(att, "VALID", [])
