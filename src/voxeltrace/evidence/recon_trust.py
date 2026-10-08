"""Reconstruction evidence trust model (REPORTING ONLY; no rule reads this module).

Decides whether baseline/follow-up reconstruction IDENTITY can be established from the
evidence available, and says what is missing. It never changes a verdict: VT-PROTOCOL-IDENTITY
and compare_protocols are unchanged.

Trust levels (highest first):
  LEVEL_A  structured standard DICOM attribute (e.g. NumberOfIterations (0018,9739))
  LEVEL_B  vendor private tag whose meaning is documented in a cited source
  LEVEL_C  scanner protocol export or signed attestation (ReconstructionAttestation,
           evidence/attestation.py; the only RULE use is QIBA, via rules/qiba_identity.py)
  LEVEL_D  vendor free text (SeriesDescription, ProtocolName, ImageComments, ...)
  LEVEL_E  image-derived corroboration (noise, texture, sharpness)
  LEVEL_U  unknown / undocumented private tag

Policy (per required parameter, baseline vs follow-up):
  A/A, B/B          can establish identity
  A/B               establishes identity with a warning (mixed sources)
  C on either side  establishes identity WITH WARNING, only if the attestation declares the
                    rule set in rule_scope; otherwise not establishing
  D, E, U alone     never establish identity
Classification: ESTABLISHED / ESTABLISHED_WITH_WARNING / NOT_ESTABLISHED / CONTRADICTED
(establishing evidence shows a different value, or establishing sources disagree).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from voxeltrace.evidence.attestation import ReconstructionAttestation

TrustLevel = Literal["LEVEL_A", "LEVEL_B", "LEVEL_C", "LEVEL_D", "LEVEL_E", "LEVEL_U"]
RANK = {"LEVEL_A": 0, "LEVEL_B": 1, "LEVEL_C": 2, "LEVEL_D": 3, "LEVEL_E": 4, "LEVEL_U": 5}
ESTABLISHING = ("LEVEL_A", "LEVEL_B", "LEVEL_C")
Identity = Literal["ESTABLISHED", "ESTABLISHED_WITH_WARNING", "NOT_ESTABLISHED", "CONTRADICTED"]

REQUIRED_PARAMETERS = (
    "reconstruction_method",
    "iterations",
    "subsets",
    "post_filter",
    "time_of_flight",
    "psf_resolution_modelling",
)

# Standard DICOM attributes -> parameter (LEVEL_A).
STANDARD_FIELDS = {
    "ReconstructionMethod": "reconstruction_method",
    "NumberOfIterations": "iterations",
    "NumberOfSubsets": "subsets",
    "ConvolutionKernel": "post_filter",
}
# Free text (LEVEL_D): recorded verbatim, never parsed into parameters.
FREE_TEXT_FIELDS = ("SeriesDescription", "ProtocolName", "ImageComments", "StudyDescription")

# Documented vendor private tags -> parameter (LEVEL_B). Each entry needs a cited document.
# EMPTY: no documented reconstruction private tag was found for GE Discovery LS
# (docs/reconstruction_audit_168.md). Undocumented private tags are LEVEL_U.
DOCUMENTED_PRIVATE_TAGS: dict[tuple[str, int, int], tuple[str, str]] = {}


class EvidenceItem(BaseModel):
    parameter: str
    timepoint: str
    value: Any = None
    trust_level: TrustLevel
    source: str = Field(description="DICOM keyword, private tag + document, attestation id...")


def attestation_evidence_items(att: ReconstructionAttestation) -> list[EvidenceItem]:
    """LEVEL_C items of ONE attestation (schema voxeltrace.recon-attestation/2). Callers pass
    only attestations that ``evidence.attestation.validate_attestation`` found VALID."""
    src = f"attestation:{att.attestation_id}:{att.source.source_type}:{att.source.sha256[:12]}"
    if att.confidence != "CONFIRMED":
        src += ":BELIEVED"
    return [
        EvidenceItem(
            parameter=p,
            timepoint=att.timepoint,
            value=getattr(att, p),
            trust_level="LEVEL_C",
            source=src,
        )
        for p in REQUIRED_PARAMETERS
        if getattr(att, p) is not None
    ]


FINDING_STATUSES = ("SAME", "SAME_WITH_WARNING", "DIFFERENT", "CONFLICT", "NOT_ESTABLISHED")


class ParameterFinding(BaseModel):
    parameter: str
    status: Literal["SAME", "SAME_WITH_WARNING", "DIFFERENT", "CONFLICT", "NOT_ESTABLISHED"]
    baseline_level: TrustLevel | None = None
    followup_level: TrustLevel | None = None
    baseline_value: Any = None
    followup_value: Any = None
    reasons: list[str] = []


class IdentityAssessment(BaseModel):
    classification: Identity
    highest_trust_level: TrustLevel | None
    parameters: list[ParameterFinding]
    unresolved: list[str]
    reasons: list[str]
    remediation: list[str]
    note: str = "Reporting only. Rule verdicts (VT-PROTOCOL-IDENTITY) are unchanged."


# ------------------------------------------------------------------ evidence collection


def dicom_evidence(headers: list[Any], timepoint: str) -> list[EvidenceItem]:
    """LEVEL_A / LEVEL_D / LEVEL_B / LEVEL_U items from pydicom datasets of ONE series.

    A standard field contributes only if it is present with ONE value on every slice."""
    items: list[EvidenceItem] = []
    for kw, param in STANDARD_FIELDS.items():
        vals = {str(h[kw].value) for h in headers if kw in h and str(h[kw].value).strip()}
        present = sum(1 for h in headers if kw in h and str(h[kw].value).strip())
        if len(vals) == 1 and present == len(headers):
            items.append(
                EvidenceItem(
                    parameter=param,
                    timepoint=timepoint,
                    value=vals.pop(),
                    trust_level="LEVEL_A",
                    source=kw,
                )
            )
    for kw in FREE_TEXT_FIELDS:
        vals = sorted({str(h[kw].value) for h in headers if kw in h})
        if vals:
            items.append(
                EvidenceItem(
                    parameter=f"free_text:{kw}",
                    timepoint=timepoint,
                    value=vals if len(vals) > 1 else vals[0],
                    trust_level="LEVEL_D",
                    source=kw,
                )
            )
    seen: set[str] = set()
    for h in headers:
        creators = {
            (e.tag.group, e.tag.element): str(e.value)
            for e in h
            if e.tag.is_private and e.tag.element < 0x100
        }
        for e in h:
            if not e.tag.is_private or e.tag.element < 0x100:
                continue
            creator = creators.get((e.tag.group, e.tag.element >> 8), "UNKNOWN_CREATOR")
            key = (creator, e.tag.group, e.tag.element & 0xFF)
            label = f"({e.tag.group:04X},xx{e.tag.element & 0xFF:02X}) {creator}"
            if label in seen:
                continue
            seen.add(label)
            doc = DOCUMENTED_PRIVATE_TAGS.get(key)
            if doc:
                items.append(
                    EvidenceItem(
                        parameter=doc[0],
                        timepoint=timepoint,
                        value=str(e.value),
                        trust_level="LEVEL_B",
                        source=f"{label} [{doc[1]}]",
                    )
                )
            else:
                items.append(
                    EvidenceItem(
                        parameter="private:UNSUPPORTED_PRIVATE_TAG",
                        timepoint=timepoint,
                        trust_level="LEVEL_U",
                        source=label,
                    )
                )
    return items


# ------------------------------------------------------------------ classification


def _norm(v: Any) -> Any:
    return " ".join(v.lower().split()) if isinstance(v, str) else v


def _usable(item: EvidenceItem, ruleset: str | None, attestations: dict[str, list[str]]) -> bool:
    if item.trust_level in ("LEVEL_A", "LEVEL_B"):
        return True
    if item.trust_level == "LEVEL_C":
        allowed = attestations.get(item.source, [])
        return ruleset is not None and ruleset in allowed
    return False


def _parameter(
    param: str,
    base: list[EvidenceItem],
    fu: list[EvidenceItem],
    ruleset: str | None,
    att_rules: dict[str, list[str]],
) -> ParameterFinding:
    reasons: list[str] = []
    sides = {}
    for name, items in (("baseline", base), ("followup", fu)):
        mine = sorted((i for i in items if i.parameter == param), key=lambda i: RANK[i.trust_level])
        est = [i for i in mine if i.trust_level in ESTABLISHING]
        if len({repr(_norm(i.value)) for i in est}) > 1:
            return ParameterFinding(
                parameter=param,
                status="CONFLICT",
                reasons=[f"EVIDENCE_CONFLICT_{name.upper()}"]
                + [f"{i.trust_level} {i.source} = {i.value!r}" for i in est],
            )
        if any(i.trust_level == "LEVEL_C" for i in est) and not any(
            _usable(i, ruleset, att_rules) for i in est
        ):
            reasons.append(f"ATTESTATION_NOT_APPLICABLE_TO_RULESET_{name.upper()}")
        usable = [i for i in est if _usable(i, ruleset, att_rules)]
        sides[name] = usable[0] if usable else (mine[0] if mine else None)
    b, f = sides["baseline"], sides["followup"]
    finding = ParameterFinding(
        parameter=param,
        status="NOT_ESTABLISHED",
        baseline_level=b.trust_level if b else None,
        followup_level=f.trust_level if f else None,
        baseline_value=b.value if b else None,
        followup_value=f.value if f else None,
        reasons=reasons,
    )
    if not (b and f and _usable(b, ruleset, att_rules) and _usable(f, ruleset, att_rules)):
        for name, s in (("BASELINE", b), ("FOLLOWUP", f)):
            if s is None:
                finding.reasons.append(f"MISSING_{name}")
            elif not _usable(s, ruleset, att_rules):
                finding.reasons.append(f"ONLY_{s.trust_level}_{name}")
        return finding
    if _norm(b.value) != _norm(f.value):
        finding.status = "DIFFERENT"
        finding.reasons.append("RECONSTRUCTION_DIFFERENT")
        return finding
    levels = {b.trust_level, f.trust_level}
    if levels in ({"LEVEL_A"}, {"LEVEL_B"}):
        finding.status = "SAME"
    else:
        finding.status = "SAME_WITH_WARNING"
        finding.reasons.append(
            "ATTESTATION_SOURCE" if "LEVEL_C" in levels else "MIXED_TRUST_LEVELS_A_B"
        )
    return finding


def classify_identity(
    baseline: list[EvidenceItem],
    followup: list[EvidenceItem],
    *,
    ruleset: str | None = None,
    attestations: tuple[ReconstructionAttestation, ...] = (),
) -> IdentityAssessment:
    """Classify reconstruction identity from typed evidence. Pure; no side effects."""
    baseline, followup = list(baseline), list(followup)
    att_rules: dict[str, list[str]] = {}
    for a in attestations:
        if a.simulated:
            raise ValueError("simulated attestations are confined to tests")
        for it in attestation_evidence_items(a):
            att_rules[it.source] = list(a.rule_scope)
            (baseline if a.timepoint == "baseline" else followup).append(it)
    params = [_parameter(p, baseline, followup, ruleset, att_rules) for p in REQUIRED_PARAMETERS]
    by = {s: [p.parameter for p in params if p.status == s] for s in FINDING_STATUSES}
    reasons: list[str] = []
    lower = [
        i
        for i in baseline + followup
        if i.trust_level in ("LEVEL_D", "LEVEL_E") and i.parameter in REQUIRED_PARAMETERS
    ]
    if by["CONFLICT"] or by["DIFFERENT"]:
        cls: Identity = "CONTRADICTED"
        reasons += [f"{p}: CONFLICT" for p in by["CONFLICT"]]
        reasons += [f"{p}: DIFFERENT" for p in by["DIFFERENT"]]
    elif by["NOT_ESTABLISHED"]:
        cls = "NOT_ESTABLISHED"
        reasons.append(
            "no LEVEL_A/B (or applicable LEVEL_C) evidence at both timepoints for: "
            + ", ".join(by["NOT_ESTABLISHED"])
        )
    elif by["SAME_WITH_WARNING"]:
        cls = "ESTABLISHED_WITH_WARNING"
        reasons += [
            f"{x.parameter}: {', '.join(x.reasons)}"
            for x in params
            if x.status == "SAME_WITH_WARNING"
        ]
    else:
        cls = "ESTABLISHED"
    if cls.startswith("ESTABLISHED"):
        for p in params:
            hints = {
                repr(_norm(i.value))
                for i in lower
                if i.parameter == p.parameter and i.value is not None
            }
            if len(hints) > 1 or (hints and repr(_norm(p.baseline_value)) not in hints):
                cls = "ESTABLISHED_WITH_WARNING"
                reasons.append(f"{p.parameter}: LOWER_TRUST_EVIDENCE_DISAGREES")
    present = [p.baseline_level for p in params] + [p.followup_level for p in params]
    present += [i.trust_level for i in baseline + followup]
    levels = [lv for lv in present if lv]
    unresolved = [p.parameter for p in params if p.status not in ("SAME", "SAME_WITH_WARNING")]
    return IdentityAssessment(
        classification=cls,
        highest_trust_level=min(levels, key=RANK.__getitem__) if levels else None,
        parameters=params,
        unresolved=unresolved,
        reasons=reasons,
        remediation=remediation(unresolved) if cls == "NOT_ESTABLISHED" else [],
    )


def remediation(unresolved: list[str]) -> list[str]:
    if not unresolved:
        return []
    return [
        "Provide, for BOTH timepoints, a scanner reconstruction-protocol export or a signed "
        "site/physicist reconstruction attestation (ReconstructionAttestation) stating: "
        + ", ".join(unresolved)
        + ", with the source document attached (its sha256 is recorded).",
        "Or re-export the series with the standard attributes ReconstructionMethod "
        "(0054,1103), NumberOfIterations (0018,9739), NumberOfSubsets (0018,9740) and "
        "ConvolutionKernel (0018,1210) populated.",
        "Or cite vendor documentation (conformance statement) that defines a private tag "
        "carrying these parameters (would become LEVEL_B).",
        "Same scanner/software, similar free text or similar image noise are NOT accepted.",
    ]


# ------------------------------------------------------------------ user-facing report


def provenance_report_md(
    subject: str,
    assessment: IdentityAssessment,
    evidence: dict[str, list[EvidenceItem]],
    *,
    corroboration: dict[str, Any] | None = None,
    ruleset: str | None = None,
) -> str:
    a = assessment
    lines = [
        f"# Reconstruction provenance report: {subject}",
        "",
        "RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS. Reporting only; rule verdicts are "
        "unchanged.",
        "",
        f"- **Reconstruction identity:** **{a.classification}**"
        + (f" (rule set {ruleset})" if ruleset else ""),
        f"- **Highest trust level present:** {a.highest_trust_level}",
        f"- **Establishable from current evidence:** "
        f"{'yes' if a.classification.startswith('ESTABLISHED') else 'no'}",
        "",
        "## Required parameters",
        "",
        "| Parameter | Status | Baseline | Follow-up | Reasons |",
        "|---|---|---|---|---|",
    ]
    for p in a.parameters:
        bv = f"{p.baseline_value!r} ({p.baseline_level})" if p.baseline_level else "missing"
        fv = f"{p.followup_value!r} ({p.followup_level})" if p.followup_level else "missing"
        lines.append(f"| {p.parameter} | {p.status} | {bv} | {fv} | {'; '.join(p.reasons)} |")
    lines += ["", "## Evidence found", "", "| Timepoint | Level | Item | Source | Value |"]
    lines.append("|---|---|---|---|---|")
    for tp, items in evidence.items():
        for i in sorted(items, key=lambda i: (RANK[i.trust_level], i.parameter, i.source)):
            v = "" if i.value is None else str(i.value)[:60]
            lines.append(f"| {tp} | {i.trust_level} | {i.parameter} | {i.source} | {v} |")
    if corroboration:
        lines += [
            "",
            "## Image-derived corroboration (LEVEL_E; cannot establish identity)",
            "",
            f"Overall: **{corroboration.get('overall')}**",
            "",
        ]
        for k, v in corroboration.get("comparison", {}).items():
            if isinstance(v, dict):
                lines.append(
                    f"- {k}: {v['baseline']:.4g} vs {v['followup']:.4g} "
                    f"(rel. diff {v['relative_difference']:.1%}, heuristic tol "
                    f"{v['heuristic_tolerance']:.0%}) -> {v['class']}"
                )
            else:
                lines.append(f"- {k}: {v}")
    lines += ["", "## Why", ""] + [f"- {r}" for r in a.reasons]
    if a.remediation:
        lines += ["", "## What the site should provide", ""]
        lines += [f"{n}. {r}" for n, r in enumerate(a.remediation, 1)]
    return "\n".join(lines) + "\n"
