"""Scanner / acquisition / reconstruction / correction evidence and deterministic claims."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

import voxeltrace
from voxeltrace.config import REPO_ROOT
from voxeltrace.evidence.claims import default_case_claims
from voxeltrace.evidence.outputs import gate_demonstrations, protocol_for_run
from voxeltrace.ingest import build_case
from voxeltrace.quant.evidence import quantify_case

st.set_page_config(page_title="VoxelTrace · Protocol & Claims", page_icon="🔬", layout="wide")

DEFAULT_DIR = str(REPO_ROOT.parent / "data" / "fdg_pet_ct_lesions" / "PETCT_0011f3deaf")
BADGE = {
    "SUPPORTED": "🟢 SUPPORTED",
    "PARTIALLY_SUPPORTED": "🟡 PARTIALLY_SUPPORTED",
    "NOT_ESTABLISHED": "⚪ NOT_ESTABLISHED",
    "CONTRADICTED": "🔴 CONTRADICTED",
}
STATUS_ICON = {"PRESENT": "✅", "PRESENT_BUT_AMBIGUOUS": "⚠️", "MISSING": "—", "UNSUPPORTED": "⛔"}

st.title("Protocol, reconstruction and claims")
st.error(f"**{voxeltrace.DISCLAIMER}**")
st.caption(
    "Standard DICOM attributes only. Vendor-private tags are not parsed. Site and "
    "device identifiers are never shown. Claims are produced by deterministic rules, not "
    "an LLM."
)


@st.cache_resource(show_spinner="Reading headers, quantifying, assessing protocol…", max_entries=2)
def load(path: str, subject: str | None):
    run = quantify_case(build_case(path, subject_id=subject), subject=subject)
    p, qc = protocol_for_run(run)
    return run, p, qc, default_case_claims(run.evidence, p), gate_demonstrations(run)


def table(obj) -> list[dict]:
    rows = []
    for name in type(obj).model_fields:
        f = getattr(obj, name)
        fields = f.values() if isinstance(f, dict) else [f]
        for x in fields:
            if hasattr(x, "status"):
                v = x.value
                rows.append(
                    {
                        "": STATUS_ICON.get(x.status, ""),
                        "field": x.name,
                        "value": ", ".join(map(str, v))
                        if isinstance(v, list)
                        else ("—" if v is None else str(v)),
                        "unit": x.unit or "",
                        "status": x.status,
                        "source": x.source or "",
                        "note": x.note or "",
                    }
                )
    return rows


root = st.text_input("Local case directory", value=DEFAULT_DIR)
if not root or not Path(root).expanduser().is_dir():
    st.info("Enter an existing local directory.")
    st.stop()
try:
    run, p, qc, claims, demos = load(str(Path(root).expanduser().resolve()), Path(root).name)
except ValueError as exc:
    st.error(f"Cannot assess: {exc}")
    st.stop()

s, a, r, c = p.scanner, p.acquisition, p.reconstruction, p.corrections
m = st.columns(4)
m[0].metric("Scanner", f"{s.manufacturer.value or '—'} {s.manufacturer_model_name.value or ''}")
m[1].metric("Software", ", ".join(s.software_versions.value or []) or "—")
m[2].metric("Reconstruction", r.reconstruction_method.value or "—")
up = a.uptake_interval_s.value
m[3].metric("Uptake", f"{up / 60:.1f} min" if up is not None else "—")

q = st.columns(4)
for i, k in enumerate(("PRESENT", "PRESENT_BUT_AMBIGUOUS", "MISSING", "UNSUPPORTED")):
    q[i].metric(k.replace("_", " ").title(), qc.status_counts.get(k, 0))
st.caption(
    "Usable for: " + ", ".join(f"{k} {'✅' if v else '⛔'}" for k, v in qc.usable_for.items())
)

tabs = st.tabs(["Scanner", "Acquisition", "Reconstruction", "Corrections", "Protocol QC"])
with tabs[0]:
    st.dataframe(table(s), hide_index=True)
    if s.identifying_attributes_recorded:
        st.caption(
            "Identifying attributes present in headers (values withheld): "
            + ", ".join(s.identifying_attributes_recorded)
        )
with tabs[1]:
    st.dataframe(table(a), hide_index=True)
with tabs[2]:
    st.dataframe(table(r), hide_index=True)
    if r.unsupported_private_metadata:
        st.warning(
            "Unsupported private metadata (not parsed): "
            + ", ".join(r.unsupported_private_metadata)
        )
with tabs[3]:
    st.dataframe(table(c), hide_index=True)
    if c.other_flags or c.unknown_flags:
        st.caption(f"Other flags: {c.other_flags or '—'}; unknown flags: {c.unknown_flags or '—'}")
with tabs[4]:
    if qc.items:
        st.dataframe([i.model_dump() for i in qc.items], hide_index=True)
    st.json(qc.blocked_by)

st.subheader("Claims (deterministic rules, no LLM)")
for cl in claims:
    with st.expander(f"{BADGE[cl.status]} · {cl.statement}"):
        st.caption(f"{cl.claim_type} · rule: {cl.rule}")
        if cl.supporting_measurements:
            st.markdown("**Supporting measurements**")
            st.json([x.model_dump() for x in cl.supporting_measurements])
        if cl.supporting_protocol_evidence:
            st.markdown("**Supporting protocol evidence**")
            st.json([x.model_dump() for x in cl.supporting_protocol_evidence])
        if cl.conflicting_evidence:
            st.markdown("**Conflicting evidence**")
            st.json([x.model_dump() for x in cl.conflicting_evidence])
        if cl.missing_evidence:
            st.markdown("**Missing evidence**: " + "; ".join(cl.missing_evidence))
        st.markdown("**Limitations**: " + " ".join(cl.limitations))
if demos:
    st.markdown("**Gate demonstration** (a deliberately wrong claim):")
    for cl in demos:
        st.write(f"{BADGE[cl.status]} · {cl.statement}")
