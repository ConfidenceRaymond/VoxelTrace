"""Filesystem listing order must not change any result (the migration exposed glob-order
nondeterminism). Each entry point runs twice: with the native order and with every directory
listing reversed; the outputs must be identical."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydicom.uid import generate_uid

from dicom_factory import write_image_series

GOOD = {"PatientSize": "1.75", "PatientSex": "M", "Manufacturer": "SIEMENS", "PatientID": "P1",
        "ManufacturerModelName": "Biograph128_mCT", "SoftwareVersions": "VG60A"}  # fmt: skip


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "trial"
    slope = iter((1.5, 1.6, 1.7, 1.8))
    for s in ("S2", "S1"):
        for tp, date in (("followup", "20200301"), ("baseline", "20200101")):
            write_image_series(root / s / tp / "PET", modality="PT", study_uid=generate_uid(), slope=next(slope),
                               pet_overrides={**GOOD, "AcquisitionDate": date, "SeriesDate": date},
                               rp_overrides={"RadiopharmaceuticalStartDateTime": f"{date}091500"})  # fmt: skip
    (root / "trial.yaml").write_text("trial_id: T\nruleset: qiba-fdg-1.14\ntimepoint_order: [baseline, followup]\n"
                                     "reference_proposals: 'off'\n")  # fmt: skip
    return root


def _reversed_listing(monkeypatch):
    orig_iterdir, orig_glob, orig_rglob, orig_walk, orig_listdir = (
        Path.iterdir, Path.glob, Path.rglob, os.walk, os.listdir)  # fmt: skip
    monkeypatch.setattr(
        Path, "iterdir", lambda self: iter(sorted(orig_iterdir(self), reverse=True))
    )
    monkeypatch.setattr(
        Path, "glob", lambda self, pat, **k: iter(sorted(orig_glob(self, pat, **k), reverse=True))
    )
    monkeypatch.setattr(
        Path, "rglob", lambda self, pat, **k: iter(sorted(orig_rglob(self, pat, **k), reverse=True))
    )
    monkeypatch.setattr(os, "listdir", lambda p=".": sorted(orig_listdir(p), reverse=True))

    def walk(top, *a, **k):
        for d, dirs, files in orig_walk(top, *a, **k):
            dirs.sort(reverse=True)
            yield d, dirs, sorted(files, reverse=True)

    monkeypatch.setattr(os, "walk", walk)


def _run(root):
    from voxeltrace.bundle import inputs_manifest
    from voxeltrace.ingest import discover_dicom
    from voxeltrace.intake import map_intake
    from voxeltrace.preflight import preflight_batch
    from voxeltrace.trial.discovery import discover_trial
    from voxeltrace.validate_input import validate_input

    disc = discover_dicom(root / "S1" / "baseline")
    return json.dumps({
        "preflight": preflight_batch(root).model_dump(mode="json"),
        "discovery": discover_trial(root).model_dump(mode="json"),
        "intake": map_intake(root, levels=("subject", "timepoint")),
        "inputs": inputs_manifest(root),
        "validate": validate_input(root),
        "dicom": [[i.path for i in s.instances] for s in disc.series],
    }, sort_keys=True, default=str)  # fmt: skip


def test_results_do_not_depend_on_listing_order(tree, monkeypatch):
    native = _run(tree)
    _reversed_listing(monkeypatch)
    assert _run(tree) == native


def test_bundle_checksums_do_not_depend_on_listing_order(tree, tmp_path, monkeypatch):
    from voxeltrace.pilot import run_audit

    def checks(out):
        run_audit(tree, out, hash_inputs=True)
        b = out / "audit_bundle"
        return {p.relative_to(b).as_posix(): p.read_bytes() for p in sorted(b.rglob("*")) if p.is_file()
                and p.name != "manifest.json"}  # fmt: skip

    a = checks(tmp_path / "a")
    _reversed_listing(monkeypatch)
    b = checks(tmp_path / "b")
    assert a.keys() == b.keys()
    diff = [k for k in a if a[k] != b[k]]
    assert diff == [], diff


_SEED_SCRIPT = r"""
import sys, json, pathlib
sys.path.insert(0, sys.argv[3])
from pydicom.uid import UID
from dicom_factory import write_image_series
from voxeltrace.pilot import run_audit
root, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
if not root.exists():
    for i, (tp, date) in enumerate((("baseline", "20200101"), ("followup", "20200301"))):
        # no PatientSize/PatientSex and no reference regions: several reason codes per pair
        write_image_series(root / "S1" / tp, modality="PT", study_uid=UID(f"1.2.3.4.{i}"), series_uid=UID(f"1.2.3.5.{i}"),
                           for_uid=UID(f"1.2.3.6.{i}"), slope=1.5 + i / 10,
                           pet_overrides={"AcquisitionDate": date, "SeriesDate": date},
                           rp_overrides={"RadiopharmaceuticalStartDateTime": f"{date}091500"})
    (root / "trial.yaml").write_text("trial_id: T\nruleset: percist-1.0\ntimepoint_order: [baseline, followup]\nreference_proposals: 'off'\n")
run_audit(root, out)
b = out / "audit_bundle"
print(json.dumps({p.relative_to(b).as_posix(): p.read_text(errors="replace") for p in sorted(b.rglob("*"))
                  if p.is_file() and p.name != "manifest.json" and p.suffix != ".pdf"}))
"""


def test_outputs_do_not_depend_on_python_hash_seed(tmp_path):
    """Set iteration order depends on PYTHONHASHSEED; it once leaked into site_summary.json."""
    import subprocess
    import sys

    tests_dir = str(Path(__file__).parent)
    runs = []
    for seed in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        r = subprocess.run([sys.executable, "-c", _SEED_SCRIPT, str(tmp_path / "trial"), str(tmp_path / f"o{seed}"),
                            tests_dir], env=env, capture_output=True, text=True, check=True)  # fmt: skip
        runs.append(json.loads(r.stdout))
    diff = [k for k in runs[0] if runs[0][k] != runs[1].get(k)]
    assert runs[0].keys() == runs[1].keys() and diff == [], diff
