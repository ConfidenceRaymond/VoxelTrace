import json
import subprocess
import sys
from pathlib import Path

from dicom_factory import build_pet_ct_seg_case

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "inspect_case.py"
SECTIONS = [
    "CASE",
    "STUDIES",
    "SERIES",
    "PET METADATA",
    "GEOMETRY",
    "SEGMENTATIONS",
    "MISSING METADATA",
    "WARNINGS",
]


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, check=True
    ).stdout


def test_text_sections(tmp_path):
    build_pet_ct_seg_case(tmp_path)
    out = _run(tmp_path, "--load-pixels")
    for sec in SECTIONS:
        assert f"\n{sec}" in f"\n{out}"
    assert "pixel_decoding=DECODED" in out
    assert "no SUV calculated" in out


def test_json_mode(tmp_path):
    info = build_pet_ct_seg_case(tmp_path)
    data = json.loads(_run(tmp_path, "--json", "--load-pixels", "--dataset", "synthetic"))
    assert data["provenance"]["dataset"] == "synthetic"
    assert info["pet"] in data["pet_metadata"]
    vols = data["pixels"]["volumes"]
    assert vols[info["pet"]]["array_shape_kji"] == [3, 4, 5]
    (seg,) = data["pixels"]["segmentations"].values()
    assert seg[info["pet"]]["voxels_per_segment"] == {"1": 4}
    assert "instances" not in data["series"][0]
