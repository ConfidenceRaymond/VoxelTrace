"""Trial data model: subject × timepoint × site, pairs, and pair assessability.

Two DISTINCT layers (docs/trial_audit.md):
  ComparabilityAssessment (existing, voxeltrace.evidence.comparability)
      protocol layer: COMPARABLE / COMPARABLE_WITH_WARNINGS / NOT_COMPARABLE /
      INSUFFICIENT_INFORMATION; VoxelTrace engineering criteria on two protocols.
  PairAssessabilityResult (new)
      trial layer: ASSESSABLE / ASSESSABLE_WITH_WARNINGS / NOT_ASSESSABLE /
      INSUFFICIENT_INFORMATION under ONE explicitly selected, versioned rule set (PERCIST,
      QIBA or EANM) plus explicit VoxelTrace prerequisites. It may include the protocol layer
      as one input, but the two states are never renamed into each other.
Neither layer assesses biological response.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from voxeltrace.evidence.protocol import ProtocolEvidence
from voxeltrace.quant.reference_region import ReferenceRegionResult
from voxeltrace.quant.sul import SULResult
from voxeltrace.rules.schema import RuleCheck
from voxeltrace.trial.anonymization import AnonymizationAudit
from voxeltrace.trial.reasons import Reason

Verdict = Literal[
    "ASSESSABLE", "ASSESSABLE_WITH_WARNINGS", "NOT_ASSESSABLE", "INSUFFICIENT_INFORMATION"
]


class ScanTimepoint(BaseModel):
    subject_id: str
    timepoint: str
    site_id: str | None = None
    pet_series_pseudonym: str | None = None
    synthetic_perturbation: str | None = Field(
        default=None, description="non-null => SYNTHETIC_PERTURBATION (never real follow-up)"
    )
    suv_status: Literal["PASS", "REFUSED", "NOT_RUN"] = "NOT_RUN"
    suv_refusal_codes: list[str] = Field(default_factory=list)
    uptake_s: float | None = None
    injected_bq: float | None = None
    weight_kg: float | None = None
    lesion_suvpeak: float | None = None
    protocol: ProtocolEvidence | None = None
    liver: ReferenceRegionResult | None = None
    blood_pool: ReferenceRegionResult | None = None
    sul: dict[str, SULResult] = Field(default_factory=dict, description="formula -> result")
    anonymization: AnonymizationAudit | None = None
    reasons: list[Reason] = Field(default_factory=list)

    @property
    def scanner(self) -> str | None:
        if self.protocol is None:
            return None
        s = self.protocol.scanner
        return f"{s.manufacturer.value or '?'} {s.manufacturer_model_name.value or '?'}"

    @property
    def software(self) -> str | None:
        if self.protocol is None or not self.protocol.scanner.software_versions.known:
            return None
        return ",".join(self.protocol.scanner.software_versions.value)  # type: ignore[arg-type]

    @property
    def reconstruction(self) -> str | None:
        if self.protocol is None:
            return None
        return self.protocol.reconstruction.reconstruction_method.value  # type: ignore[return-value]


class ScanPair(BaseModel):
    subject_id: str
    baseline: str
    followup: str


class PairContext(BaseModel):
    pair: ScanPair
    baseline: ScanTimepoint
    followup: ScanTimepoint
    site_flags: dict[str, Any] = Field(default_factory=dict)


class PairEvidence(BaseModel):
    pair: ScanPair
    comparability_category: str | None = None
    checks: list[RuleCheck] = Field(default_factory=list)


class PairAssessabilityResult(BaseModel):
    pair: ScanPair
    ruleset_id: str
    ruleset_version: str
    standard: str
    verdict: Verdict
    checks: list[RuleCheck]
    reasons: list[Reason] = Field(default_factory=list)
    comparability_category: str | None = None
    synthetic_perturbation: bool = False
    layer_note: str = (
        "Trial-level assessability under the selected rule set; distinct from "
        "protocol comparability. Not a biological response assessment."
    )
    not_assessed: list[str] = Field(
        default_factory=lambda: ["biological/treatment response", "diagnosis", "prognosis"]
    )
