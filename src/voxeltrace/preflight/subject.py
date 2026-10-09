"""Preflight of one scan directory (all series found under it): PET series + PET/CT frame."""

from __future__ import annotations

from pathlib import Path

import pydicom

from voxeltrace.ingest import discover_dicom
from voxeltrace.preflight.checks import finding
from voxeltrace.preflight.schema import ScanPreflight, combine, worst_state
from voxeltrace.preflight.series import preflight_series_headers

MIN_CT_INSTANCES = 20


def _headers(series) -> list:
    return [pydicom.dcmread(i.path, stop_before_pixels=True) for i in series.instances]


def preflight_scan_dir(
    path: str | Path, *, subject: str | None = None, scan: str | None = None
) -> ScanPreflight:
    path = Path(path)
    disc = discover_dicom(path)
    pets = [s for s in disc.series if s.category == "PET"]
    cts = [s for s in disc.series if s.category == "CT"]
    label = scan or path.name
    findings = []
    series = [preflight_series_headers(_headers(s), subject=subject, scan=label) for s in pets]
    if not pets:
        findings.append(finding("NO_PET_SERIES", f"{len(disc.series)} series, none PET", "scan"))
    elif len(pets) > 1:
        findings.append(finding("MULTIPLE_PET_SERIES", f"{len(pets)} PET series", "scan"))
    if pets:
        pet_for = set(pets[0].frame_of_reference_uids)
        in_frame = [c for c in cts if pet_for and set(c.frame_of_reference_uids) == pet_for]
        if not in_frame:
            findings.append(
                finding(
                    "CT_NOT_IN_PET_FRAME", f"{len(cts)} CT series, none in the PET frame", "scan"
                )
            )
        elif len(in_frame) > 1:
            findings.append(
                finding("CT_FRAME_AMBIGUOUS", f"{len(in_frame)} CT series in the PET frame", "scan")
            )
        elif len(in_frame[0].instances) < MIN_CT_INSTANCES:
            findings.append(
                finding(
                    "CT_NOT_VOLUMETRIC",
                    f"the CT in the PET frame has {len(in_frame[0].instances)} instance(s)",
                    "scan",
                )
            )
    states = [s.state for s in series] + [worst_state(findings)]
    return ScanPreflight(
        subject=subject,
        scan=label,
        path_label=label,
        state=combine(states),
        series=series,
        findings=findings,
    )
