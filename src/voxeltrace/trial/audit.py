"""Batch trial comparability audit (deterministic; no AI; no response assessment)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from voxeltrace.evidence.attestation import (
    AttestationOutcome,
    ScanFacts,
    load_attestations,
    validate_attestation,
)
from voxeltrace.evidence.comparability import compare_protocols
from voxeltrace.rules.registry import assess_pair
from voxeltrace.rules.trial_overrides import effective_ruleset
from voxeltrace.trial.discovery import discover_trial
from voxeltrace.trial.pairing import make_pairs
from voxeltrace.trial.reference import load_reviews
from voxeltrace.trial.schema import PairAssessabilityResult, PairContext, ScanTimepoint
from voxeltrace.trial.timepoint import build_timepoint


class TrialAudit(BaseModel):
    trial_id: str
    ruleset_id: str
    ruleset_version: str
    standard: str
    overrides: list[str] = Field(default_factory=list)
    documented_not_implemented: list[str] = Field(default_factory=list)
    reference_proposals: str = "auto"
    reference_review_file: str | None = None
    reference_reviews_applied: int = 0
    reference_reviews_unmatched: list[str] = Field(
        default_factory=list, description="review keys with no matching subject/timepoint"
    )
    recon_attestation_file: str | None = None
    recon_attestations: list[AttestationOutcome] = Field(
        default_factory=list, description="validation outcome of every supplied attestation"
    )
    timepoints: list[ScanTimepoint]
    pairs: list[PairAssessabilityResult]
    disclaimer: str = (
        "Comparability/assessability audit only. RESEARCH PROTOTYPE - NOT FOR "
        "CLINICAL DIAGNOSIS. No biological or treatment response is assessed."
    )


def run_trial_audit(
    root: str | Path,
    ruleset: str | None = None,
    *,
    qc_dir: str | Path | None = None,
    reviews_file: str | Path | None = None,
    allow_simulated_reviews: bool = False,
    attestations_file: str | Path | None = None,
    allow_simulated_attestations: bool = False,
    config_path: str | Path | None = None,
) -> TrialAudit:
    """Audit a trial directory. ``ruleset`` overrides trial.yaml (explicit, recorded).
    ``qc_dir`` receives reference-proposal QC renders; ``reviews_file`` overrides the
    trial's reference_review_file. ``allow_simulated_reviews`` exists for tests only;
    production audits ignore SIMULATED review records (they become REVIEW_INVALID).
    Reconstruction attestations (LEVEL_C) are read only from ``attestations_file`` or the
    trial's explicit ``recon_attestation_file``; they are validated here and only the QIBA
    rule set consults them. ``allow_simulated_attestations`` exists for tests only."""
    layout = discover_trial(root, config_path)
    review_path = reviews_file or layout.reference_review_file
    reviews = load_reviews(review_path, allow_simulated=allow_simulated_reviews)
    if ruleset is not None:
        layout.config = layout.config.model_copy(update={"ruleset": ruleset})
    rs = effective_ruleset(layout.config)
    tps: dict[tuple[str, str], ScanTimepoint] = {}
    inheriting = layout.synthetic_reference_inheritance
    order = [
        (subj, tp_name, d) for subj, scans in layout.scans.items() for tp_name, d in scans.items()
    ]
    # parents first: a synthetic fixture can only inherit from an already-audited scan
    order.sort(key=lambda x: f"{x[0]}/{x[1]}" in inheriting)
    for subj, tp_name, d in order:
        key = f"{subj}/{tp_name}"
        inherit = None
        if key in inheriting:
            pkey = inheriting[key]
            psubj, ptp = pkey.split("/", 1)
            parent_reviews = reviews.get(pkey, {})
            inherit = (
                pkey,
                layout.scans.get(psubj, {}).get(ptp, ""),
                tps.get((psubj, ptp)) or ScanTimepoint(subject_id=psubj, timepoint=ptp),
                {r: getattr(v, "review_sha256", None) for r, v in parent_reviews.items()},
            )
        tps[(subj, tp_name)] = build_timepoint(
            d,
            subject=subj,
            timepoint=tp_name,
            site=layout.sites.get(subj),
            synthetic=layout.synthetic.get(key),
            reference_specs=layout.reference_regions.get(key),
            reviews=reviews.get(key),
            auto_reference=layout.reference_proposals == "auto",
            qc_dir=qc_dir,
            inherit_from=inherit,
        )
    tps = {k: tps[k] for k in sorted(tps, key=lambda k: list(layout.scans).index(k[0]))}
    att_path = attestations_file or layout.recon_attestation_file
    atts, att_outcomes = load_attestations(att_path, allow_simulated=allow_simulated_attestations)
    validated: dict[str, list[AttestationOutcome]] = {}
    for key, lst in atts.items():
        subj, tp_name = key.split("/", 1)
        tp = tps.get((subj, tp_name))
        if tp is None:
            att_outcomes += [
                AttestationOutcome(
                    attestation_id=a.attestation_id,
                    subject_id=subj,
                    timepoint=tp_name,
                    status="INVALID",
                    reasons=["NO_MATCHING_SCAN"],
                )
                for a in lst
            ]
            continue
        facts = scan_facts(tp, layout.scans[subj][tp_name])
        validated[key] = [validate_attestation(a, facts, Path(att_path).parent) for a in lst]
        att_outcomes += validated[key]
    pairs = []
    for subj, scans in layout.scans.items():
        for pair in make_pairs(subj, list(scans), layout.timepoint_order):
            b, f = tps[(subj, pair.baseline)], tps[(subj, pair.followup)]
            site = layout.sites.get(subj)
            ctx = PairContext(
                pair=pair,
                baseline=b,
                followup=f,
                site_flags=layout.config.site_flags.get(site or "", {}),
                recon_attestations={
                    name: validated[f"{subj}/{name}"]
                    for name in (pair.baseline, pair.followup)
                    if f"{subj}/{name}" in validated
                },
            )
            cat = (
                compare_protocols(b.protocol, f.protocol).category
                if b.protocol and f.protocol
                else None
            )
            pairs.append(assess_pair(rs, ctx, cat))
    return TrialAudit(
        trial_id=layout.config.trial_id,
        ruleset_id=rs.ruleset_id,
        ruleset_version=rs.version,
        standard=rs.standard,
        overrides=rs.overrides,
        documented_not_implemented=rs.documented_not_implemented,
        reference_proposals=layout.reference_proposals,
        reference_review_file=str(review_path) if review_path else None,
        reference_reviews_applied=sum(
            1
            for t in tps.values()
            for r in (t.liver, t.blood_pool)
            if r is not None
            and r.review_decision
            and r.status not in ("REVIEW_OUTDATED", "REVIEW_INVALID")
        ),
        reference_reviews_unmatched=sorted(k for k in reviews if tuple(k.split("/", 1)) not in tps),
        recon_attestation_file=str(att_path) if att_path else None,
        recon_attestations=att_outcomes,
        timepoints=list(tps.values()),
        pairs=pairs,
    )


def scan_facts(tp: ScanTimepoint, scan_dir: str | Path) -> ScanFacts:
    """Binding facts of the audited PET series, read from its own DICOM headers."""
    import pydicom

    facts = ScanFacts(subject_id=tp.subject_id, timepoint=tp.timepoint)
    if tp.protocol is None:
        return facts
    s = tp.protocol.scanner
    facts.series_instance_uid = tp.protocol.series_uid
    facts.manufacturer = str(s.manufacturer.value) if s.manufacturer.known else None
    facts.manufacturer_model_name = (
        str(s.manufacturer_model_name.value) if s.manufacturer_model_name.known else None
    )
    if s.software_versions.known:
        v = s.software_versions.value
        facts.software_versions = [str(x) for x in (v if isinstance(v, (list, tuple)) else [v])]
    for f in sorted(Path(scan_dir).rglob("*")):
        if not f.is_file():
            continue
        try:
            ds = pydicom.dcmread(
                f, stop_before_pixels=True, specific_tags=["SeriesInstanceUID", "StudyInstanceUID"]
            )
        except Exception:  # noqa: BLE001 - non-DICOM files are skipped
            continue
        if str(ds.get("SeriesInstanceUID")) == facts.series_instance_uid:
            facts.study_instance_uid = str(ds.get("StudyInstanceUID"))
            break
    return facts
