"""Typed, versioned rule definitions and rule-check outcomes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from voxeltrace.trial.reasons import Reason

Standard = Literal[
    "PERCIST_1.0", "QIBA_FDG_PETCT_1.14", "EANM_FDG_2.0", "VOXELTRACE", "TRIAL_OVERRIDE"
]
Verification = Literal["PRIMARY_TEXT", "PRIMARY_TEXT_VIA_FETCH", "SECONDARY"]
Impact = Literal["blocking", "warning", "info"]
CheckStatus = Literal["PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"]


class RuleSource(BaseModel):
    citation: str
    url: str | None = None
    locator: str = Field(description="section / table / figure")
    quote: str
    verification: Verification


class Rule(BaseModel):
    rule_id: str
    name: str
    version: str
    standard: Standard
    modality: str = "PT"
    tracers: list[str] = Field(default_factory=lambda: ["FDG"])
    scope: Literal["pair", "timepoint"] = "pair"
    evidence_requirements: list[str]
    logic: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    impact: Impact
    sources: list[RuleSource]
    implementation_status: Literal["IMPLEMENTED", "DOCUMENTATION_ONLY"] = "IMPLEMENTED"
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    overridden_by: str | None = None


class RuleCheck(BaseModel):
    rule_id: str
    rule_version: str
    standard: Standard
    name: str
    impact: Impact
    status: CheckStatus
    observed: Any = None
    expected: str
    source: str
    reasons: list[Reason] = Field(default_factory=list)
    message: str = ""
