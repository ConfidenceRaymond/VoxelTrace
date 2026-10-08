"""Reconstruction evidence and external attestations (REPORT ONLY).

Shows, for an exported trial audit, the PROTOCOL_IDENTITY of every pair and every supplied
reconstruction attestation with its validation status. This page cannot create, edit or sign
an attestation; attestations come only from a site-supplied file named in trial.yaml
(recon_attestation_file). Only the QIBA rule set uses them
(docs/reconstruction_attestation_policy.md).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

import voxeltrace
from voxeltrace.config import REPO_ROOT
from voxeltrace.trial.attestation_report import (
    BANNER,
    attestation_table,
    banner_needed,
    identity_rows,
)

st.set_page_config(page_title="VoxelTrace · Reconstruction evidence", page_icon="🔬", layout="wide")
st.title("Reconstruction evidence")
st.error(f"**{voxeltrace.DISCLAIMER}**")
st.info(
    "Report only. DICOM (LEVEL_A) proves reconstruction identity; a validated external "
    "attestation (LEVEL_C) can give at most ESTABLISHED_WITH_WARNING and only under the "
    "QIBA FDG-PET/CT 1.14 rule set. EANM and PERCIST never use attestations."
)
default = REPO_ROOT.parent / "outputs" / "acrin_longitudinal_168" / "audit_qiba-fdg-1.14"
audit_dir = Path(st.sidebar.text_input("Audit output directory", str(default)))
path = audit_dir / "trial_audit.json"
if not path.exists():
    st.warning("Choose an audit output directory containing trial_audit.json.")
    st.stop()
audit = json.loads(path.read_text())
if banner_needed(audit):
    st.warning(
        f"⚠️ **{BANNER}.** Reconstruction identity for at least one pair is externally "
        "attested, NOT DICOM-proven."
    )
st.subheader(f"Protocol identity ({audit.get('ruleset_id')})")
st.dataframe(pd.DataFrame(identity_rows(audit)), use_container_width=True)
st.subheader("Supplied reconstruction attestations")
rows = attestation_table(audit)
if rows:
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
else:
    st.write("No attestation file was supplied for this audit.")
prov = audit_dir.parent / "recon_provenance.md"
if prov.exists():
    with st.expander(
        "Reconstruction provenance report (trust levels, what the site should provide)"
    ):
        st.markdown(prov.read_text())
