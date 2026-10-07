"""Explicit trial overrides from YAML/JSON (never parsed from free text by an LLM).

Example (YAML):
  trial_id: DEMO-001
  ruleset: qiba-fdg-1.14
  parameter_overrides:
    QIBA-UPTAKE-DIFF: {max_diff_min: 5.0}
  disabled_rules:
    - {rule_id: QIBA-SAME-SYSTEM, justification: "multi-scanner trial, harmonised by EARL"}
  site_flags:
    SITE-A: {earl_approved_reconstruction: true}
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from voxeltrace.rules.registry import RuleSet, get_ruleset


class DisabledRule(BaseModel):
    rule_id: str
    justification: str

    @field_validator("justification")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("disabling a rule requires a written justification")
        return v


class TrialConfig(BaseModel):
    trial_id: str
    ruleset: str
    parameter_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    disabled_rules: list[DisabledRule] = Field(default_factory=list)
    site_flags: dict[str, dict[str, Any]] = Field(default_factory=dict)


def load_trial_config(path: str | Path) -> TrialConfig:
    text = Path(path).read_text()
    data = (
        yaml.safe_load(text)
        if str(path).endswith((".yml", ".yaml"))
        else __import__("json").loads(text)
    )
    return TrialConfig.model_validate(data)


def effective_ruleset(cfg: TrialConfig) -> RuleSet:
    rs = get_ruleset(cfg.ruleset)
    ids = {r.rule_id for r, _ in rs.rules}
    for rid, params in cfg.parameter_overrides.items():
        if rid not in ids:
            raise KeyError(f"override for unknown rule {rid}")
        rule, fn = rs.rule(rid)
        unknown = set(params) - set(rule.parameters)
        if unknown:
            raise KeyError(f"{rid}: unknown parameters {sorted(unknown)}")
        new = rule.model_copy(
            update={
                "parameters": {**rule.parameters, **params},
                "overridden_by": f"TRIAL_OVERRIDE:{cfg.trial_id}",
                "version": f"{rule.version}+{cfg.trial_id}",
            }
        )
        rs.rules = [(new, fn) if r.rule_id == rid else (r, f) for r, f in rs.rules]
        rs.overrides.append(f"{rid} parameters {params}")
    for d in cfg.disabled_rules:
        if d.rule_id not in ids:
            raise KeyError(f"cannot disable unknown rule {d.rule_id}")
        rs.rules = [(r, f) for r, f in rs.rules if r.rule_id != d.rule_id]
        rs.overrides.append(f"{d.rule_id} DISABLED: {d.justification}")
    rs.version = f"{rs.version}+{cfg.trial_id}" if rs.overrides else rs.version
    return rs
