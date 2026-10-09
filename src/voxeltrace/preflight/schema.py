"""Preflight result models (schema VT-PREFLIGHT-1)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

PREFLIGHT_SCHEMA = "VT-PREFLIGHT-1"
Severity = Literal["BLOCKING", "NEEDS_REVIEW", "WARNING", "INFO"]
State = Literal["READY_TO_QUANTIFY", "READY_WITH_WARNINGS", "DO_NOT_QUANTIFY", "NEEDS_REVIEW"]
STATE_ORDER = ("DO_NOT_QUANTIFY", "NEEDS_REVIEW", "READY_WITH_WARNINGS", "READY_TO_QUANTIFY")


class PreflightFinding(BaseModel):
    reason_code: str
    severity: Severity
    field: str
    evidence: str
    remediation: str
    recoverable: Literal["YES", "NO", "MAYBE"]
    source: str = Field(description="check that produced the finding")


class SeriesPreflight(BaseModel):
    schema_version: Literal["VT-PREFLIGHT-1"] = PREFLIGHT_SCHEMA
    subject: str | None = None
    scan: str | None = None
    series_pseudonym: str
    modality: str
    n_instances: int
    state: State
    findings: list[PreflightFinding] = Field(default_factory=list)
    facts: dict[str, Any] = Field(default_factory=dict)
    note: str = "Preflight does not compute SUV/SUL. RESEARCH PROTOTYPE - NOT FOR CLINICAL USE."


class ScanPreflight(BaseModel):
    """One scan directory (e.g. subject/timepoint): its PET series plus scan-level checks."""

    schema_version: Literal["VT-PREFLIGHT-1"] = PREFLIGHT_SCHEMA
    subject: str | None = None
    scan: str | None = None
    path_label: str
    state: State
    series: list[SeriesPreflight] = Field(default_factory=list)
    findings: list[PreflightFinding] = Field(default_factory=list)


class BatchPreflight(BaseModel):
    schema_version: Literal["VT-PREFLIGHT-1"] = PREFLIGHT_SCHEMA
    root_label: str
    scans: list[ScanPreflight] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


def worst_state(findings: list[PreflightFinding]) -> State:
    sev = {f.severity for f in findings}
    if "BLOCKING" in sev:
        return "DO_NOT_QUANTIFY"
    if "NEEDS_REVIEW" in sev:
        return "NEEDS_REVIEW"
    if "WARNING" in sev:
        return "READY_WITH_WARNINGS"
    return "READY_TO_QUANTIFY"


def combine(states: list[State]) -> State:
    return min(states, key=STATE_ORDER.index) if states else "NEEDS_REVIEW"
