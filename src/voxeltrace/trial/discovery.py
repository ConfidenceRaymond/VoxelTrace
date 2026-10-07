"""Discover a trial directory: <root>/<subject>/<timepoint>/<DICOM...> + trial.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from voxeltrace.quant.reference_region import ReferenceRegionSpec
from voxeltrace.rules.trial_overrides import TrialConfig


class TrialLayout(BaseModel):
    root: str
    config: TrialConfig
    timepoint_order: list[str] = Field(default_factory=list)
    sites: dict[str, str] = Field(default_factory=dict, description="subject -> site")
    reference_regions: dict[str, ReferenceRegionSpec] = Field(
        default_factory=dict, description="subject/timepoint"
    )
    synthetic: dict[str, str] = Field(default_factory=dict, description="subject/timepoint")
    scans: dict[str, dict[str, str]] = Field(
        default_factory=dict, description="subject -> timepoint -> dir"
    )


def discover_trial(root: str | Path) -> TrialLayout:
    root = Path(root)
    raw: dict[str, Any] = yaml.safe_load((root / "trial.yaml").read_text())
    cfg = TrialConfig.model_validate(
        {
            k: raw[k]
            for k in ("trial_id", "ruleset", "parameter_overrides", "disabled_rules", "site_flags")
            if k in raw
        }
    )
    layout = TrialLayout(
        root=str(root),
        config=cfg,
        timepoint_order=raw.get("timepoint_order", []),
        sites=raw.get("sites", {}),
        reference_regions={
            k: ReferenceRegionSpec.model_validate(v)
            for k, v in (raw.get("reference_regions") or {}).items()
        },
        synthetic=raw.get("synthetic_perturbations", {}) or {},
    )
    for subj in sorted(p for p in root.iterdir() if p.is_dir()):
        tps = {tp.name: str(tp) for tp in sorted(subj.iterdir()) if tp.is_dir()}
        if tps:
            layout.scans[subj.name] = tps
    return layout
