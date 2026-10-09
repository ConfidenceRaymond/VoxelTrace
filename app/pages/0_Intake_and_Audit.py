"""Data intake -> trial audit -> reports, without the command line.

Same functions as `voxeltrace validate-input`, `voxeltrace init-trial`, `voxeltrace audit`
and `voxeltrace verify-bundle`. Nothing here records a review decision: reference regions,
lesion targets and adjudications are reviewed on their own pages.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

import voxeltrace
from voxeltrace.config import workspace_root

st.set_page_config(page_title="VoxelTrace · Intake and audit", page_icon="🔬", layout="wide")
st.title("Data intake, trial audit and reports")
st.error(f"**{voxeltrace.DISCLAIMER}**")

ws = workspace_root()
trial = Path(st.text_input("Trial folder (<subject>/<timepoint>/<DICOM>)", str(ws / "data")))
if not trial.is_dir():
    st.warning("Choose an existing folder.")
    st.stop()

# ---- 1. intake
st.header("1. Data intake")
if st.button("Check input (validate-input)"):
    from voxeltrace.validate_input import validate_input

    with st.spinner("Reading headers (no SUV is computed)..."):
        st.session_state["intake"] = validate_input(trial)
r = st.session_state.get("intake")
if r:
    st.subheader(f"Decision: {r['decision']}")
    for x in r["layout"]:
        st.warning(f"{x['code']}: {x['detail']}")
    st.dataframe(pd.DataFrame([{"subject": s["subject"], "scan": s["scan"], "decision": s["decision"],
                                "blocking": "; ".join(x["code"] for x in s["reasons"] if x["severity"] in ("BLOCKING", "NEEDS_REVIEW", "UNSUPPORTED")),
                                "warnings": "; ".join(sorted({x["code"] for x in s["reasons"] if x["severity"] == "WARNING"}))}
                               for s in r["scans"]]), use_container_width=True)  # fmt: skip

# ---- 2. configuration
st.header("2. Trial configuration")
cfg = trial / "trial.yaml"
if cfg.exists():
    st.code(cfg.read_text(), language="yaml")
else:
    st.info(
        "No trial.yaml yet. Create a starter file from the folder layout (safe defaults; sites are not guessed)."
    )
    tid = st.text_input("Trial identifier", "")
    rs = st.selectbox("Rule set", ["qiba-fdg-1.14", "eanm-fdg-2.0", "percist-1.0"])
    if st.button("Create trial.yaml", disabled=not tid.strip()):
        from voxeltrace.trial.init_trial import write_trial_yaml

        try:
            write_trial_yaml(trial, trial_id=tid.strip(), ruleset=rs)
            st.rerun()
        except (FileExistsError, ValueError) as exc:
            st.error(str(exc))
    st.stop()

# ---- 3. audit
st.header("3. Run the audit (all three rule sets)")
default_out = ws / "outputs" / f"audit_{trial.name}_{datetime.now(UTC):%Y%m%dT%H%M%S}"
out = Path(st.text_input("New output folder (never overwritten)", str(default_out)))
if st.button("Run audit"):
    from voxeltrace.pilot import run_audit

    try:
        with st.spinner("Auditing (deterministic; may take minutes per subject)..."):
            run_audit(trial, out)
        st.session_state["bundle"] = str(out / "audit_bundle")
    except (FileExistsError, ValueError) as exc:
        st.error(str(exc))
bundle_txt = st.text_input("Or open an existing bundle", st.session_state.get("bundle", ""))

# ---- 4. reports
st.header("4. Reports and evidence bundle")
bundle = Path(bundle_txt) if bundle_txt else None
if not bundle or not (bundle / "manifest.json").exists():
    st.info("Run an audit or enter an audit_bundle folder.")
    st.stop()
from voxeltrace.bundle import verify_bundle  # noqa: E402

v = verify_bundle(bundle)
(st.success if v.get("status") == "OK" else st.error)(
    f"Bundle integrity: {v.get('status')} ({v.get('files_checked')} files checked)"
)
rep = bundle / "reports"
if (rep / "EXECUTIVE_SUMMARY.md").exists():
    st.markdown((rep / "EXECUTIVE_SUMMARY.md").read_text())
for rs_csv in sorted((bundle / "pair_verdicts").glob("*.csv")):
    with st.expander(f"Pair verdicts: {rs_csv.stem}"):
        st.dataframe(pd.read_csv(rs_csv), use_container_width=True)
c1, c2, c3 = st.columns(3)
if (rep / "AUDIT_PACKAGE_REPORT.pdf").exists():
    c1.download_button(
        "PDF report", (rep / "AUDIT_PACKAGE_REPORT.pdf").read_bytes(), "AUDIT_PACKAGE_REPORT.pdf"
    )
if (rep / "executive_summary.json").exists():
    c2.download_button(
        "Summary JSON", (rep / "executive_summary.json").read_text(), "executive_summary.json"
    )
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(bundle.rglob("*")):
        if f.is_file():
            z.write(f, f.relative_to(bundle.parent))
c3.download_button(
    "Evidence bundle (.zip)", buf.getvalue(), f"{bundle.parent.name}_audit_bundle.zip"
)
st.caption("Pending human reviews: use the Reference Review and Lesion Review pages, then re-run the audit "
           "into a new folder. Manifest: " + json.dumps(json.loads((bundle / "manifest.json").read_text()).get("voxeltrace_version")))  # fmt: skip
