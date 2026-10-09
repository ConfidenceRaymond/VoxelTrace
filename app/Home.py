"""VoxelTrace landing page / smoke test.

Run with: scripts/run_app.sh
"""

from __future__ import annotations

import platform
import shutil
import subprocess

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import voxeltrace
from voxeltrace.ai import LocalAIClient
from voxeltrace.config import get_settings
from voxeltrace.quant import compute_image_stats

st.set_page_config(page_title="VoxelTrace", page_icon="🔬", layout="wide")


@st.cache_data(ttl=60)
def gpu_info() -> str:
    if not shutil.which("nvidia-smi"):
        return "nvidia-smi not found"
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return f"unavailable ({exc.__class__.__name__})"
    return out.stdout.strip() or "no GPU reported"


def synthetic_array() -> np.ndarray:
    """Tiny deterministic SYNTHETIC array with deliberate edge cases. Not PET data."""
    z, y, x = np.mgrid[0:8, 0:16, 0:16]
    a = np.exp(-(((x - 7.5) ** 2 + (y - 7.5) ** 2) / 18.0 + ((z - 3.5) ** 2) / 6.0)) * 10.0
    a = a.astype(np.float32)
    a[0, 0, :4] = 0.0
    a[0, 1, 0] = np.nan
    a[0, 1, 1] = np.inf
    return a


st.title("VoxelTrace")
st.subheader("Quantitative trust for PET imaging")
st.error(f"**{voxeltrace.DISCLAIMER}**  \nResearch software only. Not a medical device.")
st.markdown(
    "VoxelTrace checks whether quantitative FDG PET/CT scans across timepoints, sites, scanners "
    "and reconstruction protocols are comparable **before** SUV changes are interpreted, under "
    "QIBA FDG-PET/CT 1.14, EANM FDG 2.0 or PERCIST 1.0. Every result is deterministic, explained "
    "by reason codes and delivered as a checksum-verified evidence bundle. It does not diagnose, "
    "classify response or harmonize images."
)
st.markdown(
    """
#### Workflow
1. **Intake and audit**: check the data (`validate-input`), create `trial.yaml`, run the audit, download reports.
2. **Reference Review**: accept, adjust or reject liver / blood-pool proposals (human decision, hash-bound).
3. **Lesion Review**: accept or reject supplied lesion segmentations for PERCIST targets.
4. **Reconstruction Evidence**: reconstruction identity and site attestations behind each pair.
5. **Ingestion / Quantitative PET / Protocol and Claims**: single-scan provenance detail.

Adjudication of disputed pairs is recorded with `voxeltrace adjudicate` (hash-chained log).
"""
)
st.caption(
    "External expert validation is pending: no agreement figure exists yet "
    "(docs/external_validation_pending.md)."
)

with st.expander("System status and developer smoke test"):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Runtime")
        st.table(
            {
                "Item": [
                    "VoxelTrace",
                    "Python",
                    "NumPy",
                    "Platform",
                    "Machine",
                    "GPU (name, driver)",
                ],
                "Value": [
                    voxeltrace.__version__,
                    platform.python_version(),
                    np.__version__,
                    platform.platform(),
                    platform.machine(),
                    gpu_info(),
                ],
            }
        )
    with col2:
        st.markdown("#### Optional local explanation model")
        settings = get_settings()
        with LocalAIClient(settings=settings) as client:
            status = client.health()
        st.caption(
            f"Endpoint: `{status.base_url}` (local only, no cloud fallback). Never used by the audit."
        )
        if status.reachable:
            st.success(f"Reachable. Models: {', '.join(status.models) or 'none listed'}")
        else:
            st.info("No local model server reachable. Not needed for any audit function.")
    st.markdown("#### Deterministic image-statistics smoke test (SYNTHETIC DATA, not PET)")
    arr = synthetic_array()
    stats = compute_image_stats(arr)
    c1, c2 = st.columns([1, 1])
    with c1:
        st.json(stats.model_dump(), expanded=False)
    with c2:
        mid = arr[arr.shape[0] // 2]
        fig = go.Figure(go.Heatmap(z=mid, colorscale="Inferno", colorbar={"title": "a.u."}))
        fig.update_layout(
            title=f"Synthetic array, slice z={arr.shape[0] // 2} (arbitrary units)",
            yaxis={"scaleanchor": "x", "autorange": "reversed"},
            margin={"l": 10, "r": 10, "t": 40, "b": 10},
            height=360,
        )
        st.plotly_chart(fig, width="stretch")
