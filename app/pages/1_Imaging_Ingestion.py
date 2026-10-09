"""Imaging ingestion inspector. Header-first; pixels only on request. No SUV."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import voxeltrace
from voxeltrace.config import REPO_ROOT
from voxeltrace.ingest import IngestError, build_case, decode_dicom_seg, load_series_volume
from voxeltrace.schemas import VoxelTraceCase

st.set_page_config(page_title="VoxelTrace · Ingestion", page_icon="🔬", layout="wide")

DEFAULT_DIR = str(REPO_ROOT.parent / "data")

st.title("Imaging ingestion")
st.error(f"**{voxeltrace.DISCLAIMER}**")
st.warning(
    "**NO SUV CALCULATION YET.** Values shown are header metadata and modality-LUT "
    "pixel values in their recorded units."
)
st.caption(
    "Patient name, ID, birth date and similar identifiers are never read into or shown "
    "by this page. UIDs are abbreviated."
)


def short(uid: str | None) -> str:
    return f"…{uid[-12:]}" if uid else "—"


def fmt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.6g}"
    if isinstance(v, tuple | list):
        return ", ".join(fmt(x) for x in v) or "—"
    return str(v)


@st.cache_data(show_spinner="Scanning DICOM headers…")
def inspect(path: str) -> dict:
    return build_case(path).model_dump()


@st.cache_data(show_spinner="Loading pixel data…", max_entries=4)
def load_volume(path: str, series_uid: str):
    case = VoxelTraceCase.model_validate(inspect(path))
    vol = load_series_volume(case.get_series(series_uid))
    return vol.array, vol.geometry.model_dump()


@st.cache_data(show_spinner="Decoding DICOM SEG…", max_entries=4)
def load_seg(path: str, seg_path: str, ref_uid: str):
    case = VoxelTraceCase.model_validate(inspect(path))
    dec = decode_dicom_seg(seg_path, case.get_series(ref_uid))
    return {n: m for n, m in dec.masks.items()}


root = st.text_input("Local case directory", value=DEFAULT_DIR)
if not root or not Path(root).expanduser().is_dir():
    st.info("Enter an existing local directory.")
    st.stop()

case = VoxelTraceCase.model_validate(inspect(str(Path(root).expanduser().resolve())))
p = case.provenance
c = st.columns(5)
c[0].metric("Files scanned", p.files_scanned)
c[1].metric("DICOM files", p.dicom_files)
c[2].metric("Non-DICOM ignored", p.non_dicom_files_ignored)
c[3].metric("Unreadable", p.unreadable_files)
c[4].metric("Studies", len(case.studies))

if not case.series:
    st.info("No DICOM series found.")
    st.stop()

st.subheader("Studies")
st.dataframe(
    [
        {
            "study": short(s.study_uid),
            "description": s.study_description,
            "series": len(s.series_uids),
        }
        for s in case.studies
    ],
    hide_index=True,
)

st.subheader("Series")
rows = []
for s in case.series:
    g = case.geometries.get(s.series_uid)
    rows.append(
        {
            "category": s.category,
            "modality": s.modality,
            "description": s.series_description,
            "series": short(s.series_uid),
            "instances": s.instance_count,
            "dimensions (i,j,k)": fmt(g.shape_ijk) if g else f"{fmt(s.columns)}×{fmt(s.rows)}",
            "spacing mm (i,j,k)": fmt(g.spacing_ijk) if g else "—",
            "manufacturer": s.manufacturer,
            "model": s.manufacturer_model_name,
            "software": s.software_versions,
        }
    )
st.dataframe(rows, hide_index=True)

st.subheader("PET metadata (as recorded)")
if not case.pet_metadata:
    st.caption("No PET series.")
for uid, m in case.pet_metadata.items():
    st.markdown(f"Series `{short(uid)}`")
    st.dataframe(
        [
            {"field": k, "value": fmt(v)}
            for k, v in {
                "Units": m.units,
                "DecayCorrection": m.decay_correction,
                "CorrectedImage": m.corrected_image,
                "PatientWeight (kg, as recorded)": m.patient_weight,
                "SeriesDate / Time": f"{fmt(m.series_date)} {fmt(m.series_time)}",
                "AcquisitionDate / Time": f"{fmt(m.acquisition_date)} {fmt(m.acquisition_time)}",
                "Radiopharmaceutical": m.radiopharmaceutical,
                "RadionuclideTotalDose (Bq, as recorded)": m.radionuclide_total_dose,
                "RadionuclideHalfLife (s, as recorded)": m.radionuclide_half_life,
                "RadiopharmaceuticalStartTime": m.radiopharmaceutical_start_time,
                "RadiopharmaceuticalStartDateTime": m.radiopharmaceutical_start_datetime,
                "Distinct RescaleSlope values": len(m.rescale_slopes),
                "ReconstructionMethod": m.reconstruction_method,
                "ReconstructionDiameter": m.reconstruction_diameter,
            }.items()
        ],
        hide_index=True,
    )

st.subheader("Segmentations")
if not case.segmentations:
    st.caption("None found.")
for sg in case.segmentations:
    st.markdown(
        f"**{sg.source}** `{short(sg.series_uid)}` · type `{fmt(sg.segmentation_type)}` · "
        f"frames {fmt(sg.number_of_frames)} · references "
        f"{', '.join(short(u) for u in sg.referenced_series_uids) or '—'}"
    )
    st.dataframe([s.model_dump() for s in sg.segments], hide_index=True)

st.subheader("Missing metadata")
if case.missing:
    st.dataframe(
        [
            {
                "field": m.field,
                "status": m.status,
                "required": m.required,
                "raw value": m.raw_value,
                "series": short(m.scope),
                "note": m.note,
            }
            for m in case.missing
        ],
        hide_index=True,
    )
else:
    st.success("No missing or invalid metadata among the checked fields.")

st.subheader("QC warnings")
if case.warnings:
    st.dataframe(
        [
            {
                "severity": w.severity,
                "code": w.code,
                "message": w.message,
                "series": short(w.series_uid),
            }
            for w in case.warnings
        ],
        hide_index=True,
    )
else:
    st.success("No QC warnings.")

st.divider()
st.subheader("Central slice preview")
loadable = [s for s in case.series if s.series_uid in case.geometries]
if not loadable:
    st.caption("No PET/CT series with valid geometry.")
    st.stop()
labels = {f"{s.category} · {s.series_description} · {short(s.series_uid)}": s for s in loadable}
choice = labels[st.selectbox("Series", list(labels))]
segs = [
    sg
    for sg in case.segmentations
    if sg.source == "DICOM_SEG" and choice.series_uid in sg.referenced_series_uids
]
overlay = st.checkbox(
    "Overlay DICOM SEG (if it references this series)", value=bool(segs), disabled=not segs
)
if st.button("Load pixels"):
    try:
        arr, geom = load_volume(str(Path(root).expanduser().resolve()), choice.series_uid)
    except IngestError as exc:
        st.error(f"Not loaded: {exc}")
        st.stop()
    k = arr.shape[0] // 2
    sl = arr[k]
    unit = case.pet_metadata[choice.series_uid].units if choice.category == "PET" else "HU"
    fig = go.Figure(
        go.Heatmap(
            z=sl,
            colorscale="Gray" if choice.category == "CT" else "Hot",
            colorbar={"title": unit or "?"},
            zmin=float(np.nanpercentile(sl, 1)),
            zmax=float(np.nanpercentile(sl, 99.5)),
        )
    )
    if overlay and segs:
        try:
            masks = load_seg(
                str(Path(root).expanduser().resolve()), segs[0].path, choice.series_uid
            )
            union = np.any(np.stack(list(masks.values())), axis=0)
            nz = np.flatnonzero(union.any(axis=(1, 2)))
            if nz.size:
                k = int(nz[np.argmax(union[nz].sum(axis=(1, 2)))])
                fig.data[0].z = arr[k]
            fig.add_trace(
                go.Contour(
                    z=union[k].astype(float),
                    showscale=False,
                    contours={"start": 0.5, "end": 0.5, "coloring": "lines"},
                    line={"color": "cyan", "width": 2},
                )
            )
            st.caption(f"SEG decoded; showing slice k={k} (largest segmented area).")
        except IngestError as exc:
            st.error(f"SEG not decoded: {exc}")
    fig.update_layout(
        title=f"{choice.category} slice k={k} of {arr.shape[0]}",
        yaxis={"scaleanchor": "x", "autorange": "reversed"},
        height=600,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        f"Array [k, j, i] = {arr.shape}; spacing (i, j, k) mm = "
        f"{fmt(tuple(geom['spacing_ijk']))}. Pixel values after modality LUT, "
        f"source units. NO SUV."
    )
