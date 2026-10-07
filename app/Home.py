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
st.subheader("Local AI for Quantitative PET Intelligence")
st.error(f"**{voxeltrace.DISCLAIMER}**  \nResearch software only. Not a medical device.")

st.markdown(
    "**Design principle:** deterministic quantitative imaging + structured evidence + "
    "local AI reasoning. Python computes the numbers; the local model only interprets them."
)

col1, col2 = st.columns(2)
with col1:
    st.markdown("#### Runtime")
    st.table(
        {
            "Item": ["VoxelTrace", "Python", "NumPy", "Platform", "Machine", "GPU (name, driver)"],
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
    st.markdown("#### Local AI server")
    settings = get_settings()
    with LocalAIClient(settings=settings) as client:
        status = client.health()
    st.caption(f"Endpoint: `{status.base_url}` (local only, no cloud fallback)")
    if status.reachable:
        st.success(f"Reachable. Models: {', '.join(status.models) or 'none listed'}")
    else:
        st.warning("No local model server reachable. This is expected until one is started.")
        with st.expander("Details"):
            st.code(status.error or "", language=None)

st.divider()
st.markdown("#### Deterministic image-statistics smoke test")
st.info(
    "**SYNTHETIC DATA.** An 8×16×16 float32 Gaussian blob generated in code, with a few "
    "zeros, one NaN and one +inf injected to exercise the edge-case handling. "
    "This is **not** a PET case and has no clinical meaning."
)
arr = synthetic_array()
stats = compute_image_stats(arr)

c1, c2 = st.columns([1, 1])
with c1:
    st.json(stats.model_dump(), expanded=True)
with c2:
    mid = arr[arr.shape[0] // 2]
    fig = go.Figure(go.Heatmap(z=mid, colorscale="Inferno", colorbar={"title": "a.u."}))
    fig.update_layout(
        title=f"Synthetic array, slice z={arr.shape[0] // 2} (arbitrary units)",
        yaxis={"scaleanchor": "x", "autorange": "reversed"},
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        height=420,
    )
    st.plotly_chart(fig, width="stretch")
