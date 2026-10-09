"""Human review of supplied lesion / target segmentations (DICOM SEG etc.).

HUMAN QC ONLY. Nothing is pre-selected and no model is consulted. A decision is written only
after the reviewer enters an identifier, picks a decision, ticks the confirmation and presses
the button. Reviews bind to the exact mask hash; a changed mask makes the review OUTDATED.
ADJUST is not offered: no safe voxel-editing workflow exists, so a wrong mask is
REJECT_AND_REPLACE_REQUIRED. See docs/lesion_review.md.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import voxeltrace
from voxeltrace.config import REPO_ROOT
from voxeltrace.trial.discovery import discover_trial
from voxeltrace.trial.lesion_review import append_review, load_reviews, verify_log
from voxeltrace.trial.lesion_review_context import build_review, load_lesion_context

st.set_page_config(page_title="VoxelTrace · Lesion review", page_icon="🔬", layout="wide")
st.title("Lesion / target segmentation review")
st.error(f"**{voxeltrace.DISCLAIMER}**")
st.info(
    "Supplied segmentations (manual, corrected, AI-generated or algorithmic) are never "
    "quantitative ground truth by themselves. A segment becomes the PERCIST baseline target "
    "only after a qualified reviewer ACCEPTS this exact mask. Review status never changes the "
    "recorded source type: an accepted AI segmentation stays AI_GENERATED."
)
NOT_CHOSEN = "(not chosen)"
ROLES = [
    "PET_PHYSICIST",
    "NUCLEAR_MEDICINE_PHYSICIAN",
    "RADIOLOGIST",
    "IMAGING_CORE_LEAD",
    "TRIAL_QC_REVIEWER",
]

with st.sidebar:
    default = REPO_ROOT.parent / "outputs" / "external_longitudinal"
    trial_dir = Path(st.text_input("Trial directory (contains trial.yaml)", str(default)))
    reviewer = st.text_input("Reviewer name / identifier", "").strip()
    role = st.selectbox("Reviewer role", [NOT_CHOSEN, *ROLES])

if not (trial_dir / "trial.yaml").exists():
    st.warning("Choose a trial directory containing trial.yaml.")
    st.stop()
layout = discover_trial(trial_dir)
log_path = Path(layout.lesion_review_file or trial_dir / "lesion_review.jsonl")
chain = verify_log(log_path)
if chain["status"] in ("TAMPERED", "INVALID"):
    st.error(f"Lesion review log is {chain['status']} at line {chain.get('line')}: no review is used and "
             "no new review can be recorded until this is resolved.")  # fmt: skip
reviews = load_reviews(log_path)
st.caption(f"Review log: `{log_path}` · {chain['status']} · {chain.get('records', 0)} record(s) · "
           f"policy {layout.lesion_evidence_policy}")  # fmt: skip

scans = [(s, tp, Path(d)) for s, tps in layout.scans.items() for tp, d in tps.items()]
labels = [f"{s} / {tp}" for s, tp, _ in scans]
choice = st.selectbox("Scan", [NOT_CHOSEN, *labels])
if choice == NOT_CHOSEN:
    st.stop()
subj, tp, scan_dir = scans[labels.index(choice)]


@st.cache_data(show_spinner="Quantifying and rendering (deterministic)...")
def _ctx(scan_dir: str, subj: str, tp: str, log_mtime: float):
    return load_lesion_context(scan_dir, subj, tp, load_reviews(log_path))


ctx = _ctx(str(scan_dir), subj, tp, log_path.stat().st_mtime if log_path.exists() else 0.0)
if not ctx["items"]:
    st.warning("No supplied lesion segmentation was found for this scan.")
    st.stop()
st.write(f"Quantitatively eligible: **{ctx['quant_eligible']}** ({ctx['unit']}) · {ctx['ct_note']}")
table = [
    {"segment": it["evidence"].candidate.segment_number, "label": it["evidence"].candidate.segment_label,
     "source_type": it["evidence"].candidate.source_type, "review_status": it["evidence"].review_status,
     "voxels": it["evidence"].candidate.voxel_count, "volume_ml": it["evidence"].candidate.volume_ml,
     "SUVmax": it["evidence"].candidate.suv_max, "SUVpeak": it["evidence"].candidate.suv_peak}
    for it in ctx["items"]
]  # fmt: skip
st.dataframe(pd.DataFrame(table), use_container_width=True)
seg_choice = st.selectbox("Segment to review", [NOT_CHOSEN] + [str(r["segment"]) for r in table])
if seg_choice == NOT_CHOSEN:
    st.stop()
it = next(x for x in ctx["items"] if str(x["evidence"].candidate.segment_number) == seg_choice)
ev, c = it["evidence"], it["evidence"].candidate
left, right = st.columns([3, 2])
with left:
    if it["png"]:
        st.image(it["png"], caption="Display only. Measurements are on the PET grid.")
with right:
    st.subheader(f"Segment {c.segment_number}: {c.segment_label or '(no label)'}")
    st.write(f"**Source type:** {c.source_type}  ·  **Review status:** {ev.review_status}")
    st.json({"provenance": c.source_provenance, "mask_sha256": c.mask_sha256, "seg_file_sha256": c.seg_file_sha256,
             "voxel_count": c.voxel_count, "volume_ml": c.volume_ml, "bbox_kji": c.bbox_kji, "centroid_kji": c.centroid_kji,
             "SUVmax": c.suv_max, "SUVmean": c.suv_mean, "SUVpeak": c.suv_peak, "MTV_ml": c.mtv_ml, "TLG": c.tlg,
             "SUVmax_kji": it["suvmax_kji"], "SUVpeak_centre_kji": it["suvpeak_kji"]})  # fmt: skip
    for w in it["qc_warnings"]:
        st.warning(w)
    if ev.reasons:
        st.write("Status reasons: " + ", ".join(ev.reasons))

st.divider()
decision = st.radio(
    "Decision",
    [NOT_CHOSEN, "ACCEPT", "REJECT", "REJECT_AND_REPLACE_REQUIRED"],
    index=0,
    horizontal=True,
)
note = st.text_input("Note (optional)", "")
confirm = st.checkbox(
    "I reviewed this exact mask myself and record this decision under my identifier."
)
ready = (
    reviewer
    and role != NOT_CHOSEN
    and decision != NOT_CHOSEN
    and confirm
    and chain["status"] in ("OK", "NO_FILE")
)
if st.button("Record decision", disabled=not ready):
    rec = build_review(ev, reviewer_id=reviewer, reviewer_role=role, decision=decision, note=note)
    append_review(log_path, rec, confirmed=True)
    st.success(f"Recorded {decision} for segment {c.segment_number} (bound to mask {c.mask_sha256[:12]}...). "
               "Re-run the audit to use it.")  # fmt: skip
    st.cache_data.clear()
