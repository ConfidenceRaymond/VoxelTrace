"""Path portability: nothing at runtime depends on a developer home directory, and outputs carry
no absolute local paths (the GB10 -> x86 migration broke absolute symlinks and paths)."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from pydicom.uid import generate_uid

from dicom_factory import write_image_series

REPO = Path(__file__).resolve().parents[1]
HOME_PATH = re.compile(r"/home/(dell|mindlab)\b|voxeltrace_hackathon")


def test_runtime_code_has_no_developer_paths():
    files = subprocess.run(["git", "ls-files", "src", "app", "configs", "pyproject.toml", ".env.example",
                            "scripts/check_environment.sh"], cwd=REPO, capture_output=True, text=True,
                           check=True).stdout.split()  # fmt: skip
    hits = []
    for f in files:
        if f.endswith("privacy_scan.py"):  # the scanner's own patterns name these on purpose
            continue
        p = REPO / f
        if p.is_file() and p.suffix in (".py", ".yaml", ".yml", ".toml", ".sh", ".example", ""):
            hits += [f"{f}:{i}" for i, line in enumerate(p.read_text(errors="ignore").splitlines(), 1)
                     if HOME_PATH.search(line)]  # fmt: skip
    assert hits == []


def test_workspace_root_follows_environment(tmp_path, monkeypatch):
    from voxeltrace.config import workspace_root

    monkeypatch.setenv("VOXELTRACE_WORKSPACE", str(tmp_path / "ws"))
    assert workspace_root() == (tmp_path / "ws").resolve()


def test_pilot_runs_from_another_home_without_leaking_paths(tmp_path, monkeypatch):
    from voxeltrace.pilot_run import run_pilot

    home = tmp_path / "home" / "otheruser"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("VOXELTRACE_WORKSPACE", raising=False)
    monkeypatch.chdir(home)
    root = home / "ACME_Hospital_Export" / "trial"
    for i, (tp, date) in enumerate((("baseline", "20200101"), ("followup", "20200301"))):
        write_image_series(root / "S1" / tp, modality="PT", study_uid=generate_uid(), slope=1.5 + i / 10,
                           pet_overrides={"PatientSize": "1.75", "PatientSex": "M", "AcquisitionDate": date,
                                          "SeriesDate": date},
                           rp_overrides={"RadiopharmaceuticalStartDateTime": f"{date}091500"})  # fmt: skip
    res = run_pilot(
        Path("ACME_Hospital_Export/trial"),
        Path("work"),
        trial_id="T",
        timepoints=["baseline", "followup"],
    )
    assert res["delivery"]["status"] == "OK", res["delivery"]
    pkg = home / "work" / "delivery_package"
    text = "\n".join(p.read_text(errors="ignore") for p in pkg.rglob("*") if p.is_file())
    leaks = [
        p.relative_to(pkg).as_posix()
        for p in pkg.rglob("*")
        if p.is_file() and str(tmp_path) in p.read_text(errors="ignore")
    ]
    assert leaks == []
    assert "otheruser" not in text and "ACME_Hospital" not in text
    acc = json.loads((home / "work" / "pilot_acceptance.json").read_text())
    assert not acc["output"]["bundle"].startswith("/")
