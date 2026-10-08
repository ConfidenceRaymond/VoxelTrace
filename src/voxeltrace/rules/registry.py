"""Rule-set registry. A rule set = ONE published standard + explicit VoxelTrace prerequisites.
Mixing standards is only possible through an explicit, justified trial override."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from voxeltrace.rules import eanm, percist, qiba
from voxeltrace.rules.qiba_identity import qiba_reconstruction_identity
from voxeltrace.rules.schema import Rule, RuleCheck
from voxeltrace.rules.voxeltrace_rules import VOXELTRACE_RULES, VT_RECON
from voxeltrace.trial.reasons import Reason
from voxeltrace.trial.schema import PairAssessabilityResult, PairContext, Verdict

RuleFn = Callable[[Rule, PairContext], RuleCheck]


@dataclass
class RuleSet:
    ruleset_id: str
    version: str
    standard: str
    rules: list[tuple[Rule, RuleFn]]
    documented_not_implemented: list[str] = field(default_factory=list)
    overrides: list[str] = field(default_factory=list)

    def rule(self, rule_id: str) -> tuple[Rule, RuleFn]:
        return next(r for r in self.rules if r[0].rule_id == rule_id)


def _ruleset(rid: str, standard: str, mod) -> RuleSet:
    vt = list(VOXELTRACE_RULES)
    if rid == "qiba-fdg-1.14":  # LEVEL_C attestation path: QIBA ONLY (qiba_identity.py)
        vt = [(r, qiba_reconstruction_identity if r is VT_RECON else fn) for r, fn in vt]
    return RuleSet(
        ruleset_id=rid,
        version=mod.V,
        standard=standard,
        rules=vt + list(mod.RULES),
        documented_not_implemented=list(mod.DOCUMENTED_NOT_IMPLEMENTED),
    )


REGISTRY: dict[str, Callable[[], RuleSet]] = {
    "qiba-fdg-1.14": lambda: _ruleset("qiba-fdg-1.14", "QIBA_FDG_PETCT_1.14", qiba),
    "eanm-fdg-2.0": lambda: _ruleset("eanm-fdg-2.0", "EANM_FDG_2.0", eanm),
    "percist-1.0": lambda: _ruleset("percist-1.0", "PERCIST_1.0", percist),
}


def get_ruleset(ruleset_id: str) -> RuleSet:
    if ruleset_id not in REGISTRY:
        raise KeyError(f"unknown rule set {ruleset_id!r}; available: {sorted(REGISTRY)}")
    rs = REGISTRY[ruleset_id]()
    standards = {r.standard for r, _ in rs.rules} - {"VOXELTRACE"}
    if len(standards) != 1:  # guard against silent mixing
        raise ValueError(f"rule set {ruleset_id} mixes standards: {standards}")
    return rs


def verdict(checks: list[RuleCheck]) -> Verdict:
    blocking = [c for c in checks if c.impact == "blocking"]
    warning = [c for c in checks if c.impact == "warning"]
    if any(c.status == "FAIL" for c in blocking):
        return "NOT_ASSESSABLE"
    if any(c.status == "UNKNOWN" for c in blocking):
        return "INSUFFICIENT_INFORMATION"
    if any(c.status in ("FAIL", "UNKNOWN") for c in warning) or any(
        c.status == "PASS_WITH_WARNING" for c in checks
    ):
        return "ASSESSABLE_WITH_WARNINGS"
    return "ASSESSABLE"


def assess_pair(
    rs: RuleSet, ctx: PairContext, comparability_category: str | None = None
) -> PairAssessabilityResult:
    checks = [fn(rule, ctx) for rule, fn in rs.rules]
    reasons: list[Reason] = [
        r for c in checks if c.status in ("UNKNOWN", "FAIL") for r in c.reasons
    ]
    return PairAssessabilityResult(
        pair=ctx.pair,
        ruleset_id=rs.ruleset_id,
        ruleset_version=rs.version,
        standard=rs.standard,
        verdict=verdict(checks),
        checks=checks,
        reasons=reasons,
        comparability_category=comparability_category,
        synthetic_perturbation=bool(
            ctx.baseline.synthetic_perturbation or ctx.followup.synthetic_perturbation
        ),
    )
