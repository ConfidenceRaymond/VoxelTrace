"""Read-only intake inventory of a local brain PET study (BIDS or DICOM). VT-BRAIN-INTAKE-1.

Reports what is present; never quantifies (no SUV/SUVR, no kinetic modelling, no PERCIST, no
reference region). BIDS: dataset_description.json, sub-*/[ses-*/]pet/*_pet.json sidecars,
*_blood.(tsv|json), anat/, derivatives/, ROI/mask files. DICOM: PET series headers (tracer,
frames, scanner, reconstruction, attenuation correction) and MR series presence.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "VT-BRAIN-INTAKE-1"
NOT_DONE = "inventory only: no SUV/SUVR, kinetic modelling, reference region or PERCIST"


def _bids(root: Path) -> dict[str, Any]:
    dd = root / "dataset_description.json"
    desc = json.loads(dd.read_text()) if dd.exists() else {}
    pets = sorted(root.glob("sub-*/**/pet/*_pet.json"))
    subjects = sorted({p.relative_to(root).parts[0] for p in pets})
    sessions = Counter(
        p.relative_to(root).parts[0] for p in pets if "ses-" in str(p.relative_to(root))
    )
    scans = []
    for p in pets:
        sc = json.loads(p.read_text())
        frames = sc.get("FrameDuration")
        n = len(frames) if isinstance(frames, list) else None
        scans.append({
            "file": str(p.relative_to(root)),
            "tracer": sc.get("TracerName"), "radionuclide": sc.get("TracerRadionuclide"),
            "frames": n, "dynamic": (n > 1) if n is not None else None,
            "scanner": " ".join(str(sc.get(k)) for k in ("Manufacturer", "ManufacturersModelName") if sc.get(k)) or None,
            "reconstruction": sc.get("ReconMethodName"),
            "recon_parameters": dict(zip(sc.get("ReconMethodParameterLabels") or [], sc.get("ReconMethodParameterValues") or [], strict=False)) or None,
            "attenuation_correction": sc.get("AttenuationCorrection"),
            "injected_radioactivity": sc.get("InjectedRadioactivity"),
            "image_decay_corrected": sc.get("ImageDecayCorrected"),
            "blood_files": sorted(str(b.relative_to(root)) for b in p.parent.glob(p.name.replace("_pet.json", "") + "*_blood.*")),
        })  # fmt: skip
    rois = sorted(
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and re.search(r"(roi|mask|seg|label|dseg)", p.name, re.I)
    )
    return {
        "format": "BIDS",
        "bids_version": desc.get("BIDSVersion"),
        "dataset_name": desc.get("Name"),
        "license": desc.get("License"),
        "subjects": len(subjects),
        "longitudinal_subjects": sum(1 for s in subjects if sessions.get(s, 0) >= 2),
        "pet_scans": scans,
        "tracers": dict(Counter(str(s["tracer"]) for s in scans)),
        "dynamic_scans": sum(s["dynamic"] is True for s in scans),
        "static_scans": sum(s["dynamic"] is False for s in scans),
        "mri_available": any(root.glob("sub-*/**/anat/*")),
        "blood_input_function": any(s["blood_files"] for s in scans),
        "derivatives": (root / "derivatives").exists(),
        "supplied_rois_or_masks": rois[:50],
    }  # fmt: skip


def _dicom(root: Path) -> dict[str, Any]:
    import pydicom

    from voxeltrace.ingest import discover_dicom

    disc = discover_dicom(root)
    pets, out = [s for s in disc.series if s.category == "PET"], []
    for s in pets:
        h = pydicom.dcmread(s.instances[0].path, stop_before_pixels=True)
        rp = (h.get("RadiopharmaceuticalInformationSequence") or [None])[0]
        n_frames = h.get("NumberOfTimeSlices") or h.get("NumberOfFrames")
        out.append({
            "series_description": str(h.get("SeriesDescription", "")) or None,
            "tracer": str(rp.get("Radiopharmaceutical")) if rp is not None and rp.get("Radiopharmaceutical") else None,
            "frames": int(n_frames) if n_frames else None,
            "dynamic": (int(n_frames) > 1) if n_frames else None,
            "scanner": f"{h.get('Manufacturer', '')} {h.get('ManufacturerModelName', '')}".strip() or None,
            "reconstruction": str(h.get("ReconstructionMethod")) if h.get("ReconstructionMethod") else None,
            "attenuation_correction": str(h.get("AttenuationCorrectionMethod")) if h.get("AttenuationCorrectionMethod") else None,
            "corrected_image": [str(x) for x in (h.get("CorrectedImage") or [])],
            "instances": len(s.instances),
        })  # fmt: skip
    mods = Counter(
        s.category if s.category != "OTHER" else str(getattr(s, "modality", "OTHER"))
        for s in disc.series
    )
    return {
        "format": "DICOM",
        "pet_series": out,
        "tracers": dict(Counter(str(p["tracer"]) for p in out)),
        "dynamic_scans": sum(p["dynamic"] is True for p in out),
        "static_scans": sum(p["dynamic"] is False for p in out),
        "series_categories": dict(mods),
        "mri_available": any(getattr(s, "modality", None) == "MR" for s in disc.series),
        "blood_input_function": None,
        "supplied_rois_or_masks": [s.series_description for s in disc.series if s.category == "SEG"],
    }  # fmt: skip


def inspect_brain(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    is_bids = (root / "dataset_description.json").exists() or any(
        root.glob("sub-*/**/pet/*_pet.json")
    )
    report = _bids(root) if is_bids else _dicom(root)
    return {
        "schema": SCHEMA,
        "path_label": root.name,
        "read_only": True,
        "not_done": NOT_DONE,
        **report,
    }
