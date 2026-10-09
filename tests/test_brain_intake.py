"""Brain PET intake inventory (read-only; nothing quantified)."""

from __future__ import annotations

import json

from pydicom.uid import generate_uid

from dicom_factory import write_image_series
from voxeltrace.brain_intake import inspect_brain
from voxeltrace.cli import main as cli


def bids(root):
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "t", "BIDSVersion": "1.8.0", "License": "CC0"})
    )
    for ses, frames in (("ses-1", [60.0] * 20), ("ses-2", [1200.0])):
        pet = root / "sub-01" / ses / "pet"
        pet.mkdir(parents=True)
        (pet / f"sub-01_{ses}_trc-UCBJ_pet.json").write_text(
            json.dumps(
                {
                    "TracerName": "UCB-J",
                    "TracerRadionuclide": "C11",
                    "FrameDuration": frames,
                    "Manufacturer": "Siemens",
                    "ManufacturersModelName": "HRRT",
                    "ReconMethodName": "OSEM",
                    "ReconMethodParameterLabels": ["iterations", "subsets"],
                    "ReconMethodParameterValues": [3, 21],
                    "AttenuationCorrection": "transmission",
                }
            )
        )
        (pet / f"sub-01_{ses}_trc-UCBJ_pet.nii.gz").write_bytes(b"")
    (
        root / "sub-01" / "ses-1" / "pet" / "sub-01_ses-1_trc-UCBJ_recording-manual_blood.tsv"
    ).write_text("time\tvalue\n")
    (root / "sub-01" / "ses-1" / "anat").mkdir()
    (root / "sub-01" / "ses-1" / "anat" / "sub-01_ses-1_T1w.nii.gz").write_bytes(b"")
    (root / "derivatives" / "rois").mkdir(parents=True)
    (root / "derivatives" / "rois" / "sub-01_centrumsemiovale_mask.nii.gz").write_bytes(b"")


def test_bids_inventory(tmp_path):
    bids(tmp_path)
    before = sorted(p.name for p in tmp_path.rglob("*"))
    r = inspect_brain(tmp_path)
    assert r["format"] == "BIDS" and r["read_only"] and "no SUV" in r["not_done"]
    assert r["tracers"] == {"UCB-J": 2} and r["dynamic_scans"] == 1 and r["static_scans"] == 1
    assert r["longitudinal_subjects"] == 1 and r["mri_available"] and r["blood_input_function"]
    assert r["derivatives"] and any("mask" in x for x in r["supplied_rois_or_masks"])
    scan = next(s for s in r["pet_scans"] if s["frames"] == 20)
    assert scan["recon_parameters"] == {"iterations": 3, "subsets": 21}
    assert sorted(p.name for p in tmp_path.rglob("*")) == before  # nothing written
    assert "suvr" not in json.dumps(r).lower().replace("no suv/suvr", "")


def test_dicom_inventory_and_cli(tmp_path, capsys):
    write_image_series(tmp_path / "pet", modality="PT", study_uid=generate_uid())
    r = inspect_brain(tmp_path)
    assert r["format"] == "DICOM" and len(r["pet_series"]) == 1
    assert r["pet_series"][0]["tracer"] == "Fluorodeoxyglucose"
    assert cli(["inspect-brain", str(tmp_path)]) == 0
    assert "VT-BRAIN-INTAKE-1" in capsys.readouterr().out
