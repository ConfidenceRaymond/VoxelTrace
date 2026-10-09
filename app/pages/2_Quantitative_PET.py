"""Strict SUVbw + lesion metrics on a local case. Deterministic; no AI."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import voxeltrace
from voxeltrace.config import REPO_ROOT
from voxeltrace.ingest import build_case
from voxeltrace.quant.evidence import quantify_case

st.set_page_config(page_title="VoxelTrace · Quantitative PET", page_icon="🔬", layout="wide")

DEFAULT_DIR = str(REPO_ROOT.parent / "data" / "fdg_pet_ct_lesions" / "PETCT_0011f3deaf")

st.title("Quantitative PET")
st.error(f"**{voxeltrace.DISCLAIMER}**  \nResearch software only. Not a medical device.")
st.caption(
    "Strict SUVbw (DICOM BQML / START). Metadata that do not support a defensible SUV "
    "are refused, never assumed. Lesion metrics use the supplied segmentation only."
)


def fmt(v, nd=4):
    if v is None:
        return "—"
    return f"{v:.{nd}g}" if isinstance(v, float) else str(v)


@st.cache_resource(show_spinner="Validating metadata and computing SUV…", max_entries=2)
def run(path: str, subject: str | None):
    case = build_case(path, subject_id=subject)
    return quantify_case(case, subject=subject, dataset=None)


root = st.text_input("Local case directory", value=DEFAULT_DIR)
subject = st.text_input(
    "Subject pseudonym (optional, not read from headers)", value=Path(root).name if root else ""
)
if not root or not Path(root).expanduser().is_dir():
    st.info("Enter an existing local directory.")
    st.stop()
try:
    qr = run(str(Path(root).expanduser().resolve()), subject or None)
except ValueError as exc:
    st.error(f"Cannot quantify: {exc}")
    st.stop()

ev = qr.evidence
q = ev.quantitative_inputs
if ev.measured.suv_status == "PASS":
    st.success("**SUV eligibility: PASS** (supported path: BQML / START / ATTN+DECY)")
else:
    st.error("**SUV eligibility: REFUSED**. No SUV values are produced.")
    st.dataframe([r.model_dump() for r in ev.refusal_reasons], hide_index=True)

st.subheader("Inputs used")
st.dataframe(
    [
        {"input": "Units", "value": q.units, "source": "(0054,1001)"},
        {"input": "DecayCorrection", "value": q.decay_correction, "source": "(0054,1102)"},
        {
            "input": "CorrectedImage",
            "value": ", ".join(q.corrected_image or []),
            "source": "(0028,0051)",
        },
        {
            "input": "Patient weight [kg]",
            "value": fmt(q.patient_weight_kg),
            "source": "(0010,1030)",
        },
        {
            "input": "Injected dose [Bq]",
            "value": fmt(q.radionuclide_total_dose_bq, 6),
            "source": "(0018,1074)",
        },
        {
            "input": "Half-life [s]",
            "value": fmt(q.radionuclide_half_life_s, 6),
            "source": "(0018,1075)",
        },
        {
            "input": "Injection datetime",
            "value": q.injection_datetime,
            "source": q.injection_datetime_source,
        },
        {
            "input": "Scan reference datetime",
            "value": q.scan_reference_datetime,
            "source": q.scan_reference_datetime_source,
        },
        {
            "input": "Decay interval Δt [s]",
            "value": fmt(q.decay_interval_s, 8),
            "source": "derived",
        },
    ],
    hide_index=True,
)

if ev.warnings:
    st.subheader("Warnings")
    st.dataframe(
        [{"severity": w.severity, "code": w.code, "message": w.message} for w in ev.warnings],
        hide_index=True,
    )

with st.expander("How was this calculated?"):
    st.markdown(
        "**SUVbw = C_PET [Bq/mL] × W [g] / (D_inj [Bq] × 2^(−Δt / T½))**\n\n"
        "- C_PET = stored value × RescaleSlope_k + RescaleIntercept_k on each slice k "
        "(Units = BQML).\n"
        "- Δt = scan reference time − injection time. For DecayCorrection = START, the "
        "reference is the PET Series Date/Time. It is accepted only when it agrees with the "
        "earliest acquisition time (≤ 1 s) or when per-slice FrameReferenceTime confirms it.\n"
        "- MTV = volume of the supplied segment mask. TLG = MTV × SUVmean.\n"
        "- SUVpeak = the highest mean over all image voxels whose centres lie within "
        "r = (3/4π)^⅓ cm ≈ 6.20 mm (a 1.0 cm³ sphere, not 1 cm diameter). Candidate centres "
        "are every voxel in the segment; spheres that would leave the image are excluded."
    )
    if ev.scale_factors:
        st.json(ev.scale_factors.model_dump())
    st.json(ev.provenance.model_dump())
    src = qr.outcome.result or qr.outcome.refusal
    st.dataframe([c.model_dump() for c in src.validation.checks], hide_index=True)

if ev.measured.suv_status != "PASS":
    st.stop()

st.subheader("Lesions (supplied segmentation)")
if not ev.measured.lesions:
    st.info("No decoded DICOM SEG referencing this PET series.")
for les in ev.measured.lesions:
    pk = les.suv_peak
    c = st.columns(6)
    c[0].metric(f"Segment {les.segment_number}", les.segment_label or "—")
    c[1].metric("SUVmax", fmt(les.suv_max))
    c[2].metric("SUVmean", fmt(les.suv_mean))
    c[3].metric("SUVpeak", fmt(pk.value) if pk and pk.status == "COMPUTED" else "N/A")
    c[4].metric("MTV [mL]", fmt(les.mtv_ml))
    c[5].metric("TLG [g]", fmt(les.tlg))
    st.caption(
        f"{les.voxel_count} voxels, {les.n_components} connected component(s), "
        f"SUV median {fmt(les.suv_median)}, SD {fmt(les.suv_std)}. "
        + (
            f"SUVpeak sphere: {pk.kernel_voxel_count} voxels = "
            f"{pk.kernel_effective_volume_ml:.3f} mL."
            if pk
            else ""
        )
    )

st.subheader("SUV image")
suv = qr.outcome.suv
masks = qr.seg_masks or {}
union = np.any(np.stack(list(masks.values())), axis=0) if masks else None
default_k = suv.shape[0] // 2
if union is not None and union.any():
    default_k = int(np.argmax(union.sum(axis=(1, 2))))
k = st.slider("Slice k", 0, suv.shape[0] - 1, default_k)
vmax = st.slider("Display max SUV", 1.0, float(max(2.0, np.ceil(suv.max()))), 8.0)
fig = go.Figure(
    go.Heatmap(z=suv[k], colorscale="Hot", zmin=0, zmax=vmax, colorbar={"title": "SUVbw"})
)
if union is not None:
    fig.add_trace(
        go.Contour(
            z=union[k].astype(float),
            showscale=False,
            contours={"start": 0.5, "end": 0.5, "coloring": "lines"},
            line={"color": "cyan", "width": 2},
        )
    )
fig.update_layout(
    yaxis={"scaleanchor": "x", "autorange": "reversed"},
    height=600,
    margin={"l": 10, "r": 10, "t": 30, "b": 10},
    title=f"SUVbw slice k={k} (cyan: supplied segmentation)",
)
st.plotly_chart(fig, width="stretch")
