"""Human review of automatic reference-region proposals (liver / blood pool).

HUMAN QC ONLY. This page never chooses a decision: nothing is pre-selected, a decision is
written only after the reviewer enters an identifier, ticks the confirmation and presses the
button, and no model is consulted. Measurements are deterministic (PET grid, same code as the
trial audit). See docs/reference_region_review.md.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import streamlit as st

import voxeltrace
from voxeltrace.config import REPO_ROOT
from voxeltrace.trial.discovery import discover_trial
from voxeltrace.trial.reference import (
    RegionGeometry,
    build_review,
    final_region_sha256,
    load_reviews,
    record_review,
    review_status,
    rule_context_for,
)
from voxeltrace.trial.review import CHECKLIST, load_review_context, measure_candidate
from voxeltrace.visualization.reference_qc import review_panels

st.set_page_config(page_title="VoxelTrace · Reference review", page_icon="🔬", layout="wide")

PROJECT = REPO_ROOT.parent
DEFAULT_TRIAL = PROJECT / "outputs" / "synthetic_comparability" / "trial_demo"
DEFAULT_AUDIT = PROJECT / "outputs" / "reference_audit_percist"
STATUS_ICON = {
    "UNREVIEWED": "⚪ UNREVIEWED",
    "ACCEPTED": "🟢 ACCEPTED",
    "ADJUSTED": "🔵 ADJUSTED",
    "REJECTED": "🔴 REJECTED",
    "OUTDATED": "🟠 OUTDATED",
    "INVALID": "⛔ INVALID",
}
INTENT = {
    "LIVER": "**Intended placement (PERCIST 1.0):** a 3 cm diameter sphere lying entirely in "
    "normal-appearing right-lobe liver tissue, away from the liver boundary and from any "
    "visible focal uptake or supplied lesion.",
    "BLOOD_POOL": "**Intended placement (PERCIST 1.0):** a 1 cm diameter × 2 cm long "
    "cylinder lying entirely within the blood pool of the descending thoracic aorta. It is "
    "measured and reported; no assessability rule uses it.",
}
NOT_CHOSEN = "(not chosen)"

st.title("Reference region review")
st.error(f"**{voxeltrace.DISCLAIMER}**")
st.info(
    "This is a **human quality-control step**. VoxelTrace proposes reference regions "
    "deterministically from the CT; it never accepts them itself. A region counts for "
    "PERCIST assessability only after a reviewer records ACCEPT or ADJUST for the exact "
    "proposal hash. The page makes no diagnostic statement and consults no AI model."
)

with st.sidebar:
    trial_dir = Path(st.text_input("Trial directory", str(DEFAULT_TRIAL)))
    audit_dir = Path(st.text_input("Audit output directory", str(DEFAULT_AUDIT)))
    reviewer = st.text_input(
        "Reviewer name / identifier",
        "",
        help="Entered by you; stored with every decision you record.",
    ).strip()

audit_json = audit_dir / "trial_audit.json"
if not (trial_dir / "trial.yaml").exists() or not audit_json.exists():
    st.warning(
        "Choose a trial directory containing trial.yaml and an audit output directory "
        "containing trial_audit.json (scripts/run_trial_audit.py)."
    )
    st.stop()

layout = discover_trial(trial_dir)
review_file = Path(layout.reference_review_file or trial_dir / "reference_review.yaml")
audit = json.loads(audit_json.read_text())
try:
    reviews = load_reviews(review_file)
except ValueError as exc:
    st.error(f"reference_review.yaml cannot be read: {exc}")
    st.stop()

items = []
for tp in audit["timepoints"]:
    for region, key in (("LIVER", "liver"), ("BLOOD_POOL", "blood_pool")):
        res = tp.get(key) or {}
        if res.get("source") != "AUTO_PROPOSAL" or not res.get("proposal_sha256"):
            continue
        entry = reviews.get(f"{tp['subject_id']}/{tp['timepoint']}", {}).get(region)
        items.append(
            {
                "subject": tp["subject_id"],
                "timepoint": tp["timepoint"],
                "region": region,
                "sha": res["proposal_sha256"],
                "res": res,
                "entry": entry,
                "status": review_status(res["proposal_sha256"], entry),
            }
        )
same_sha: dict[str, list[str]] = defaultdict(list)
for it in items:
    same_sha[it["sha"]].append(f"{it['subject']}/{it['timepoint']}")

st.caption(
    f"Audit: `{audit_json}` · ruleset {audit['ruleset_id']} ({audit['ruleset_version']}) · "
    f"review file: `{review_file}` ({'present' if review_file.exists() else 'not yet created'})"
)
tab_summary, tab_review = st.tabs(["Summary", "Review a proposal"])

# --------------------------------------------------------------------------- summary
with tab_summary:
    counts = Counter(it["status"] for it in items)
    cols = st.columns(6)
    for c, s in zip(cols, STATUS_ICON, strict=True):
        c.metric(s, counts.get(s, 0))

    def fmt(v, nd=3):
        return None if v is None else round(v, nd)

    rows = []
    for it in items:
        r, e = it["res"], it["entry"]
        rows.append(
            {
                "subject": it["subject"],
                "timepoint": it["timepoint"],
                "region": it["region"],
                "proposal": it["sha"][:12],
                "review status": STATUS_ICON[it["status"]],
                "reviewer": getattr(e, "reviewer", None) or "",
                "SUVmean": fmt(r.get("suv_mean")),
                "SULmean": fmt(r.get("sul_mean")),
                "SD": fmt(r.get("suv_sd")),
                "CoV": fmt(r.get("cov")),
                "voxels": r.get("voxel_count"),
                "QC": r.get("refusal") or "PASS",
                "same proposal also at": ", ".join(
                    k for k in same_sha[it["sha"]] if k != f"{it['subject']}/{it['timepoint']}"
                ),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(
        "Measurements in this table come from the last audit run. For UNREVIEWED proposals "
        "they are a preview only and are not used by any rule. Identical proposals on "
        "the same scan (same hash) are still reviewed one by one; nothing is copied."
    )
    pending = [it for it in items if it["status"] in ("UNREVIEWED", "OUTDATED", "INVALID")]
    if pending:
        st.warning(
            f"{len(pending)} proposal(s) still need a human decision. Until both timepoints "
            "of a pair have an ACCEPTED or ADJUSTED liver region, the PERCIST liver rules "
            "stay UNKNOWN and the pair stays INSUFFICIENT_INFORMATION."
        )

# --------------------------------------------------------------------------- review
with tab_review:
    if not items:
        st.info("No automatic proposals in this audit.")
        st.stop()
    labels = [
        f"{it['subject']} / {it['timepoint']} / {it['region']} — {it['status']}" for it in items
    ]
    idx = st.selectbox("Proposal", range(len(items)), format_func=lambda i: labels[i])
    it = items[idx]
    subj, tpn, region = it["subject"], it["timepoint"], it["region"]
    case_dir = layout.scans.get(subj, {}).get(tpn)
    if case_dir is None:
        st.error(f"{subj}/{tpn} not found in the trial directory.")
        st.stop()

    @st.cache_resource(show_spinner="Loading PET/CT and recomputing the proposal…", max_entries=3)
    def context(path: str, s: str, t: str):
        return load_review_context(path, s, t)

    ctx = context(str(case_dir), subj, tpn)
    prop = ctx.proposals.get(region)
    if ctx.problems or prop is None or prop.status != "PROPOSED" or ctx.work is None:
        st.error("Cannot review: " + "; ".join(ctx.problems or ["proposal unavailable"]))
        st.stop()
    if prop.sha256 != it["sha"]:
        st.error(
            "The proposal recomputed now differs from the one in the audit "
            f"({prop.sha256[:12]} vs {it['sha'][:12]}). Re-run the audit before reviewing."
        )
        st.stop()

    st.subheader(f"{subj} · {tpn} · {region}")
    st.markdown(INTENT[region])
    st.markdown("**Reviewer checklist** (look for each item in the images below):")
    st.markdown("\n".join(f"- {c}" for c in CHECKLIST[region]))
    st.markdown(f"Current review status: **{STATUS_ICON[it['status']]}**")
    if it["entry"] is not None:
        st.json(it["entry"].model_dump(), expanded=False)

    decision = st.radio(
        "Decision",
        [NOT_CHOSEN, "ACCEPT", "ADJUST", "REJECT"],
        index=0,
        horizontal=True,
        key=f"decision::{subj}/{tpn}/{region}",
    )
    centre = prop.centre_patient_mm
    if decision == "ADJUST":
        st.markdown(
            "Move the centre only. The region's shape and size are fixed by the rule "
            f"({prop.method}, diameter {prop.diameter_mm:g} mm"
            + (f", length {prop.length_mm:g} mm" if prop.length_mm else "")
            + "). Nothing snaps; the measurements below follow your centre exactly."
        )
        c1, c2, c3 = st.columns(3)
        k = f"{subj}/{tpn}/{region}"
        dz = c1.slider("Slice (z) offset, mm (+ = superior)", -30.0, 30.0, 0.0, 1.0, key=f"dz::{k}")
        dx = c2.slider("x offset, mm (+ = patient left)", -30.0, 30.0, 0.0, 0.5, key=f"dx::{k}")
        dy = c3.slider("y offset, mm (+ = posterior)", -30.0, 30.0, 0.0, 0.5, key=f"dy::{k}")
        centre = tuple(round(c + d, 1) for c, d in zip(centre, (dx, dy, dz), strict=True))
    geometry = prop.to_spec("display", centre=centre)

    try:
        res, qc = measure_candidate(ctx, prop, centre)
        panels = review_panels(ctx.work, geometry)
    except ValueError as exc:
        st.error(f"Region cannot be shown at this centre: {exc}")
        st.stop()

    for group, caption in (
        ("main", "PET, CT and fused PET/CT through the region centre (zoom 120 mm)"),
        ("neighbours", "Neighbouring axial slices (fused)"),
        ("context", "Coronal views"),
    ):
        st.markdown(f"**{caption}**")
        tiles = panels[group]
        for col, (label, rgb) in zip(st.columns(max(len(tiles), 1)), tiles, strict=False):
            col.image(rgb, caption=label, width="stretch")
    st.caption(
        "Outlines are the contour of the region mask itself on a 3 mm display grid. "
        "Measurements are computed on the original PET grid."
    )

    left, right = st.columns(2)
    with left:
        st.markdown("**Geometry and measurements (PET grid)**")
        meas = {
            "method": prop.method,
            "centre (LPS mm)": str(centre),
            "radius (mm)": prop.diameter_mm / 2,
            "cylinder length (mm)": prop.length_mm,
            "voxel count": res.voxel_count,
            "volume (mL)": res.volume_ml,
            "SUVmean": res.suv_mean,
            "SUV SD": res.suv_sd,
            "CoV": res.cov,
            "SUVmax": res.suv_max,
            "SULmean (LBMJAMES128)": res.sul_mean if res.sul_mean is not None else ctx.sul_status,
            "SUL SD": res.sul_sd,
            "CT HU mean": qc.get("ct_hu_mean"),
            "CT HU SD": qc.get("ct_hu_sd"),
            "nearest supplied lesion (mm from centre)": qc.get("nearest_supplied_lesion_mm"),
        }
        st.table(pd.DataFrame({"value": [str(v) for v in meas.values()]}, index=list(meas)))
    with right:
        st.markdown("**QC**")
        if res.status != "COMPUTED":
            st.error(f"Measurement refused: {res.refusal}. This region cannot be accepted.")
        else:
            st.success("Measurement QC passed (inside image, no lesion overlap, no SUV 0).")
        for a in qc["advisory"]:
            st.warning(f"Advisory: {a}")
        if not qc["advisory"] and res.status == "COMPUTED":
            st.caption("No advisory flags. Advisory flags assist looking; they decide nothing.")
        st.markdown("**Proposer QC values**")
        st.json({k: round(v, 3) for k, v in prop.qc.items()}, expanded=False)
        st.markdown("**Hashes**")
        lines = [
            f"proposal_sha256      {prop.sha256}",
            f"pet_series           {prop.pet_series_pseudonym}",
            f"algorithm            {prop.algorithm_version}",
        ]
        if decision in ("ACCEPT", "ADJUST"):
            g = RegionGeometry.of(prop).model_copy(update={"centre_patient_mm": centre})
            lines.append(f"final_region_sha256  {final_region_sha256(prop.sha256, g)}")
        st.code("\n".join(lines))

    st.divider()
    st.markdown("### Record the decision")
    rc = rule_context_for(region)
    st.caption(
        f"Rule context: {rc.ruleset_id} {rc.ruleset_version} · {rc.region_definition} · "
        f"rules: {', '.join(rc.rule_ids) or 'none (reported only)'}"
    )
    note = st.text_area("Note (optional)", key=f"note::{subj}/{tpn}/{region}")
    blockers = []
    if decision == NOT_CHOSEN:
        blockers.append("choose ACCEPT, ADJUST or REJECT")
    if len(reviewer) < 2:
        blockers.append("enter your reviewer name / identifier in the sidebar")
    if decision in ("ACCEPT", "ADJUST") and res.status != "COMPUTED":
        blockers.append("a region that fails measurement QC cannot be accepted")
    if decision == "ADJUST" and centre == prop.centre_patient_mm:
        blockers.append("ADJUST needs a moved centre (otherwise choose ACCEPT)")
    replace = False
    if it["entry"] is not None:
        replace = st.checkbox(
            "Replace the existing decision for this scan and region (the old one is kept "
            "under 'superseded')",
            key=f"replace::{subj}/{tpn}/{region}",
        )
        if not replace:
            blockers.append("tick 'replace' to change an existing decision")
    preview = None
    if not blockers:
        preview = build_review(
            subject=subj,
            timepoint=tpn,
            proposal=prop,
            decision=decision,
            reviewer=reviewer,
            note=note,
            adjusted_centre=centre if decision == "ADJUST" else None,
        )
        st.markdown("Record to be written:")
        st.json(preview.model_dump(), expanded=False)
    confirm = st.checkbox(
        f"I ({reviewer or '—'}) inspected this region myself and confirm the decision "
        f"{decision if decision != NOT_CHOSEN else '—'}.",
        key=f"confirm::{subj}/{tpn}/{region}",
        disabled=bool(blockers),
    )
    if blockers:
        st.info("To record: " + "; ".join(blockers) + ".")
    if st.button("Record decision", type="primary", disabled=bool(blockers) or not confirm):
        # rebuilt at click time so the timestamp is the moment of confirmation
        rec = build_review(
            subject=subj,
            timepoint=tpn,
            proposal=prop,
            decision=decision,
            reviewer=reviewer,
            note=note,
            adjusted_centre=centre if decision == "ADJUST" else None,
        )
        record_review(review_file, rec, confirmed=confirm, replace=replace)
        st.success(
            f"Recorded {rec.decision} for {subj}/{tpn} {region} in {review_file}. "
            "Re-run the audit to apply it."
        )

    with st.expander("Re-run the trial audit with the recorded reviews"):
        st.caption(
            "Runs the deterministic audit (no AI) and rewrites the audit output directory. "
            "This can take a few minutes."
        )
        if st.button("Re-run audit"):
            from voxeltrace.trial.audit import run_trial_audit
            from voxeltrace.trial.export import export_audit
            from voxeltrace.trial.summary import site_summary

            with st.spinner("Running the trial audit…"):
                a = run_trial_audit(
                    trial_dir, ruleset=audit["ruleset_id"], qc_dir=audit_dir / "reference_qc"
                )
                export_audit(a, audit_dir)
            s = site_summary(a)
            st.json(
                {
                    "verdicts": s["verdicts"],
                    "reference_regions": s["reference_regions"],
                    "reference_reviews_applied": a.reference_reviews_applied,
                }
            )
