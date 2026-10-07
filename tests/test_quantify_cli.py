import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from dicom_factory import build_pet_ct_seg_case

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "quantify_case.py"
FILES = ["suv_input_audit.json", "lesion_metrics.json", "evidence.json", "quantitative_summary.txt"]


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True
    )


def test_pass_writes_evidence(tmp_path):
    info = build_pet_ct_seg_case(tmp_path / "case")
    out = tmp_path / "out"
    r = _run(tmp_path / "case", "--out", out, "--subject", "SYNTH-1", "--dataset", "synthetic")
    assert r.returncode == 0, r.stderr + r.stdout
    for f in [*FILES, "suv_result.json"]:
        assert (out / f).exists()
    assert not (out / "suv_refusal.json").exists()
    ev = json.loads((out / "evidence.json").read_text())
    assert ev["measured"]["suv_status"] == "PASS"
    assert ev["provenance"]["pet_series_uid"] == info["pet"]
    assert ev["provenance"]["subject_pseudonym"] == "SYNTH-1"
    assert "diagnosis" in ev["not_established"]
    # Hand calc for the default fixture: W=70.5 kg, D=3e8 Bq, Δt=3600 s, T½=6586.2 s
    # factor = 70500 / (3e8 * 2^(-3600/6586.2)); decay factor 0.68463291957200212 (hand)
    factor = 70500 / (3e8 * 0.68463291957200212)
    assert ev["scale_factors"]["suv_per_bqml"] == pytest.approx(factor, rel=1e-13)
    (les,) = ev["measured"]["lesions"]
    # SEG covers slice k=1, rows 1-2, cols 2-3; stored = 10 + r + c; activity = 2*stored - 1
    act = np.array([2 * (10 + r + c) - 1 for r in (1, 2) for c in (2, 3)], dtype=float)
    assert les["voxel_count"] == 4
    assert les["suv_max"] == pytest.approx(act.max() * factor, rel=1e-12)
    assert les["suv_mean"] == pytest.approx(act.mean() * factor, rel=1e-12)
    assert les["mtv_ml"] == pytest.approx(4 * 3.0 * 2.0 * 4.0 / 1000)
    assert les["tlg"] == pytest.approx(les["mtv_ml"] * les["suv_mean"], rel=1e-12)
    # 3×4×5 synthetic grid is smaller than the 1 cm³ sphere → SUVpeak not available
    assert les["suv_peak"]["status"] == "NOT_AVAILABLE"
    audit = json.loads((out / "suv_input_audit.json").read_text())
    assert audit["eligible"] and len(audit["per_slice"]) == 3
    assert "PatientID" in audit["identifiers_excluded"]
    assert "SYNTHETIC" not in (out / "evidence.json").read_text()  # PatientID never copied
    assert math.isfinite(ev["measured"]["suv_volume_stats"]["finite_max"])


def test_refusal_exit_code_and_stale_result_removed(tmp_path):
    build_pet_ct_seg_case(tmp_path / "case")
    out = tmp_path / "out"
    out.mkdir()
    (out / "suv_result.json").write_text("{}")  # stale file from an earlier run
    import pydicom

    for p in (tmp_path / "case" / "a_pet").glob("*.dcm"):
        ds = pydicom.dcmread(p)
        ds.Units = "CNTS"
        ds.save_as(p)
    r = _run(tmp_path / "case", "--out", out)
    assert r.returncode == 2
    assert "REFUSED UNSUPPORTED_UNITS" in r.stdout
    assert (out / "suv_refusal.json").exists() and not (out / "suv_result.json").exists()
    ev = json.loads((out / "evidence.json").read_text())
    assert ev["measured"]["suv_status"] == "REFUSED" and ev["measured"]["lesions"] == []
    assert ev["refusal_reasons"][0]["code"] == "UNSUPPORTED_UNITS"
    for f in FILES:
        assert (out / f).exists()
    claims = json.loads((out / "claim_evidence.json").read_text())["claims"]
    assert all(
        c["status"] != "SUPPORTED" for c in claims if c["claim_type"] == "QUANTITATIVE_VALUE"
    )
    qc = json.loads((out / "protocol_qc.json").read_text())
    assert qc["usable_for"]["suv"] is False
