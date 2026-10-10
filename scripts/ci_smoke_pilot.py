#!/usr/bin/env python3
"""Fresh-install smoke test (CI): build a tiny SYNTHETIC two-visit trial, run the installed
`voxeltrace` CLI end to end (run-pilot -> verify-delivery) and fail on any non-OK result.

  ci_smoke_pilot.py <work_dir>

Synthetic data only (tests/dicom_factory.py); no real DICOM, no network, no model.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from pydicom.uid import generate_uid  # noqa: E402

from dicom_factory import write_image_series  # noqa: E402


def main(argv: list[str]) -> int:
    work = Path(argv[1])
    trial = work / "trial"
    for i, (tp, date) in enumerate((("baseline", "20200101"), ("followup", "20200301"))):
        write_image_series(trial / "SUBJ-001" / tp, modality="PT", study_uid=generate_uid(), slope=1.5 + i / 10,
                           pet_overrides={"PatientSize": "1.75", "PatientSex": "M", "PatientID": "SUBJ-001",
                                          "Manufacturer": "SIEMENS", "ManufacturerModelName": "Biograph128_mCT",
                                          "SoftwareVersions": "VG60A", "ReconstructionMethod": "PSF+TOF 2i21s",
                                          "ConvolutionKernel": "XYZ Gauss2.00", "FrameReferenceTime": "0",
                                          "DecayFactor": "1.0", "AcquisitionDate": date, "SeriesDate": date},
                           rp_overrides={"RadiopharmaceuticalStartDateTime": f"{date}091500"})  # fmt: skip
    run = subprocess.run(["voxeltrace", "run-pilot", "--input", str(trial), "--output", str(work / "out"),
                          "--trial-id", "CI-SMOKE", "--timepoints", "baseline", "followup", "--format", "json"],
                         capture_output=True, text=True)  # fmt: skip
    print(run.stdout[-2000:], run.stderr[-2000:])
    if run.returncode != 0:
        print(f"run-pilot exit {run.returncode}")
        return 1
    acc = json.loads(run.stdout)["acceptance"]
    ver = subprocess.run(["voxeltrace", "verify-delivery", str(work / "out" / "delivery_package")],
                         capture_output=True, text=True)  # fmt: skip
    print(ver.stdout)
    ok = acc["status"].startswith("AUDIT_COMPLETE") and ver.returncode == 0
    print("SMOKE", "OK" if ok else "FAILED", acc["status"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
