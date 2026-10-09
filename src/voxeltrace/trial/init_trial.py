"""Starter trial.yaml from a <subject>/<timepoint>/<DICOM> folder (no hand-written YAML).

Only facts visible in the folder layout are written; everything else is left at the safe
default (lesion review required, automatic reference proposals that need human review).
Sites are not guessed. An existing trial.yaml is never overwritten.
"""

from __future__ import annotations

from pathlib import Path

import yaml

RULESETS = ("qiba-fdg-1.14", "eanm-fdg-2.0", "percist-1.0")
_KNOWN_ORDER = (
    "screening",
    "baseline",
    "bl",
    "interim",
    "followup",
    "follow-up",
    "fu",
    "fu1",
    "fu2",
    "eot",
)


def _order(names: set[str]) -> list[str]:
    known = [n for n in _KNOWN_ORDER if n in {x.lower() for x in names}]
    lower = {x.lower(): x for x in names}
    if len(known) == len(names):
        return [lower[k] for k in known]
    return sorted(names)


def write_trial_yaml(
    folder: str | Path,
    *,
    trial_id: str,
    ruleset: str = "qiba-fdg-1.14",
    timepoint_order: list[str] | None = None,
) -> Path:
    folder = Path(folder)
    out = folder / "trial.yaml"
    if out.exists():
        raise FileExistsError(f"{out} exists (never overwritten)")
    if ruleset not in RULESETS:
        raise ValueError(f"ruleset must be one of {RULESETS}")
    subjects = sorted(p for p in folder.iterdir() if p.is_dir() and not p.name.startswith("."))
    tps = {t.name for s in subjects for t in s.iterdir() if t.is_dir()}
    if not subjects or not tps:
        raise ValueError("expected <subject>/<timepoint>/<DICOM files> folders")
    order = timepoint_order or _order(tps)
    missing = tps - set(order)
    if missing:
        raise ValueError(f"timepoints not in --timepoints: {sorted(missing)}")
    doc = {
        "trial_id": trial_id,
        "ruleset": ruleset,
        "timepoint_order": order,
        "reference_proposals": "auto",
        "reference_review_file": "reference_review.yaml",
        "lesion_review_file": "lesion_review.jsonl",
        "lesion_evidence_policy": "REVIEW_REQUIRED",
    }
    header = (
        "# Starter configuration written by `voxeltrace init-trial`.\n"
        "# Optional: add `sites: {<subject>: <site>}` for site-level rollup; never guessed.\n"
    )
    out.write_text(header + yaml.safe_dump(doc, sort_keys=False))
    from voxeltrace.trial.discovery import discover_trial

    discover_trial(folder)  # fail loudly if the written file is not usable
    return out
