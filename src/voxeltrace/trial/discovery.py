"""Discover a trial directory: <root>/<subject>/<timepoint>/<DICOM...> + trial.yaml.

Reference-region keys in trial.yaml:
  reference_regions:          # supplied regions; one spec or a list of specs per scan
    SUBJ/BASELINE: {region: LIVER, method: SPHERE_AT_SUPPLIED_CENTRE, ...}
  reference_proposals: auto   # auto (default) | off
  reference_review_file: reference_review.yaml   # default; relative to the trial root
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from voxeltrace.preflight.batch import is_ignored_dir
from voxeltrace.quant.reference_region import ReferenceRegionSpec
from voxeltrace.rules.trial_overrides import TrialConfig


class TrialLayout(BaseModel):
    root: str
    config: TrialConfig
    timepoint_order: list[str] = Field(default_factory=list)
    sites: dict[str, str] = Field(default_factory=dict, description="subject -> site")
    reference_regions: dict[str, dict[str, ReferenceRegionSpec]] = Field(
        default_factory=dict, description="subject/timepoint -> region -> supplied spec"
    )
    reference_proposals: Literal["auto", "off"] = "auto"
    reference_review_file: str | None = None
    lesion_review_file: str | None = None
    lesion_evidence_policy: Literal["REVIEW_REQUIRED", "LEGACY_UNREVIEWED_ALLOWED"] = (
        "REVIEW_REQUIRED"
    )
    recon_attestation_file: str | None = Field(
        default=None,
        description="explicit only (trial.yaml recon_attestation_file); never picked up by default",
    )
    synthetic_reference_inheritance: dict[str, str] = Field(
        default_factory=dict,
        description="synthetic subject/timepoint -> parent subject/timepoint (test fixtures)",
    )
    synthetic: dict[str, str] = Field(default_factory=dict, description="subject/timepoint")
    scans: dict[str, dict[str, str]] = Field(
        default_factory=dict, description="subject -> timepoint -> dir"
    )


def discover_trial(root: str | Path, config_path: str | Path | None = None) -> TrialLayout:
    """``config_path`` (optional) lets the trial configuration live outside the read-only
    input folder; relative file references in it resolve against its own directory."""
    root = Path(root)
    cfg_file = Path(config_path) if config_path else root / "trial.yaml"
    base = cfg_file.parent
    raw: dict[str, Any] = yaml.safe_load(cfg_file.read_text())
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
        reference_regions=_supplied_regions(raw.get("reference_regions") or {}),
        reference_proposals=raw.get("reference_proposals", "auto"),
        reference_review_file=str(base / raw.get("reference_review_file", "reference_review.yaml")),
        lesion_review_file=str(base / raw.get("lesion_review_file", "lesion_review.jsonl")),
        lesion_evidence_policy=raw.get("lesion_evidence_policy", "REVIEW_REQUIRED"),
        recon_attestation_file=(
            str(base / raw["recon_attestation_file"]) if raw.get("recon_attestation_file") else None
        ),
        synthetic=raw.get("synthetic_perturbations", {}) or {},
        synthetic_reference_inheritance={
            k: v["parent"] for k, v in (raw.get("synthetic_reference_inheritance") or {}).items()
        },
    )
    if layout.lesion_evidence_policy == "LEGACY_UNREVIEWED_ALLOWED" and not layout.synthetic:
        raise ValueError(
            "lesion_evidence_policy LEGACY_UNREVIEWED_ALLOWED is only allowed for trials that "
            "declare synthetic_perturbations (test fixtures); real data requires REVIEW_REQUIRED"
        )
    # hidden folders and __MACOSX are never subjects or timepoints (as in preflight)
    for subj in sorted(p for p in root.iterdir() if p.is_dir() and not is_ignored_dir(p.name)):
        tps = {
            tp.name: str(tp)
            for tp in sorted(subj.iterdir())
            if tp.is_dir() and not is_ignored_dir(tp.name)
        }
        if tps:
            layout.scans[subj.name] = tps
    return layout


def _supplied_regions(raw: dict[str, Any]) -> dict[str, dict[str, ReferenceRegionSpec]]:
    out: dict[str, dict[str, ReferenceRegionSpec]] = {}
    for key, v in raw.items():
        for item in v if isinstance(v, list) else [v]:
            spec = ReferenceRegionSpec.model_validate(item)
            if spec.region in out.setdefault(key, {}):
                raise ValueError(f"{key}: {spec.region} supplied twice")
            out[key][spec.region] = spec
    return out
