"""Deterministic SYNTHETIC_PERTURBATION copies of a real PET(+SEG) series, for tests and demos.

Originals are never modified: files are read and NEW files are written under a separate
directory with new Study/Series/SOP/FrameOfReference UIDs, the SEG references remapped, and the
label 'SYNTHETIC_PERTURBATION <kind>' written into SeriesDescription and ImageComments.
These are NOT real follow-up scans. Expected gate results are declared in EXPECTED.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pydicom
import SimpleITK as sitk
from pydicom.uid import generate_uid

from voxeltrace.ingest import build_case, load_series_volume

KINDS = (
    "identity",
    "recon_blur",
    "recon_metadata",
    "uptake_violation",
    "missing_dose",
    "anonymization_loss",
    "correction_mismatch",
)
# Expected verdict under the QIBA FDG v1.14 rule set (baseline = the unmodified real series).
EXPECTED = {
    "identity": ("ASSESSABLE", []),
    "recon_blur": ("NOT_ASSESSABLE", ["VT-PROTOCOL-IDENTITY"]),
    "recon_metadata": ("NOT_ASSESSABLE", ["VT-PROTOCOL-IDENTITY"]),
    "uptake_violation": ("NOT_ASSESSABLE", ["QIBA-UPTAKE-WINDOW", "QIBA-UPTAKE-DIFF"]),
    "missing_dose": ("INSUFFICIENT_INFORMATION", ["VT-SUV-BOTH"]),
    "anonymization_loss": ("INSUFFICIENT_INFORMATION", ["VT-PROTOCOL-IDENTITY"]),
    "correction_mismatch": ("NOT_ASSESSABLE", ["VT-PROTOCOL-IDENTITY"]),
}
BLUR_FWHM_MM = 6.0


def _shift_time(tm: str, minutes: int) -> str:
    t = datetime.strptime(tm[:6], "%H%M%S") - timedelta(minutes=minutes)
    return t.strftime("%H%M%S") + tm[6:]


def _shift_dt(dt: str, minutes: int) -> str:
    t = datetime.strptime(dt[:14], "%Y%m%d%H%M%S") - timedelta(minutes=minutes)
    return t.strftime("%Y%m%d%H%M%S") + dt[14:]


def perturb_case(src_dir: str | Path, dst_dir: str | Path, kind: str) -> Path:
    if kind not in KINDS:
        raise ValueError(kind)
    src_dir, dst_dir = Path(src_dir), Path(dst_dir)
    if dst_dir.exists() and any(dst_dir.iterdir()):
        raise FileExistsError(f"{dst_dir} not empty; refusing to overwrite")
    dst_dir.mkdir(parents=True, exist_ok=True)
    case = build_case(src_dir)
    (pet,) = case.series_by_category("PET")
    segs = case.series_by_category("SEG")
    study, series, for_uid = generate_uid(), generate_uid(), generate_uid()
    label = f"SYNTHETIC_PERTURBATION {kind}"
    sop_map: dict[str, str] = {}

    blurred = None
    if kind == "recon_blur":
        vol = load_series_volume(pet)
        img = sitk.GetImageFromArray(vol.array.astype(np.float64))
        img.SetSpacing([float(v) for v in vol.geometry.spacing_ijk])  # type: ignore[arg-type]
        sigma = BLUR_FWHM_MM / 2.354820045  # mm
        sm = sitk.DiscreteGaussian(
            img, variance=sigma**2, maximumKernelWidth=64, maximumError=0.001, useImageSpacing=True
        )
        arr = sitk.GetArrayFromImage(sm)
        blurred = {p: arr[k] for k, p in enumerate(vol.slice_paths)}

    (dst_dir / "PT").mkdir()
    for inst in pet.instances:
        ds = pydicom.dcmread(inst.path)
        new_sop = generate_uid()
        sop_map[str(ds.SOPInstanceUID)] = new_sop
        ds.StudyInstanceUID, ds.SeriesInstanceUID, ds.FrameOfReferenceUID = study, series, for_uid
        ds.SOPInstanceUID = new_sop
        ds.file_meta.MediaStorageSOPInstanceUID = new_sop
        ds.SeriesDescription = f"{label}: {ds.get('SeriesDescription', '')}"[:64]
        ds.ImageComments = f"{label} - derived from a real series; NOT a real follow-up scan"
        rp = ds.RadiopharmaceuticalInformationSequence[0]
        if kind == "recon_blur":
            act = blurred[inst.path]  # type: ignore[index]
            slope, inter = float(ds.RescaleSlope), float(ds.RescaleIntercept)
            stored = np.clip(np.rint((act - inter) / slope), 0, 65535).astype(np.uint16)
            ds.PixelData = stored.tobytes()
            ds.ConvolutionKernel = f"XYZ Gauss{BLUR_FWHM_MM:.2f}"  # SH <= 16 chars
        elif kind == "recon_metadata":
            ds.ReconstructionMethod = "PSF+TOF 4i21s"
        elif kind == "uptake_violation":
            if "RadiopharmaceuticalStartTime" in rp:
                rp.RadiopharmaceuticalStartTime = _shift_time(
                    str(rp.RadiopharmaceuticalStartTime), 30
                )
            if "RadiopharmaceuticalStartDateTime" in rp:
                rp.RadiopharmaceuticalStartDateTime = _shift_dt(
                    str(rp.RadiopharmaceuticalStartDateTime), 30
                )
        elif kind == "missing_dose":
            del rp.RadionuclideTotalDose
        elif kind == "anonymization_loss":
            for kw in ("ReconstructionMethod", "ConvolutionKernel"):
                if kw in ds:
                    del ds[kw]
            for t in [e.tag for e in ds if e.tag.group == 0x0071]:
                del ds[t]
        elif kind == "correction_mismatch":
            ds.CorrectedImage = [c for c in ds.CorrectedImage if c != "SCAT"]
        ds.save_as(dst_dir / "PT" / f"{new_sop}.dcm", enforce_file_format=True)

    for seg_series in segs:
        (dst_dir / "SEG").mkdir(exist_ok=True)
        for inst in seg_series.instances:
            ds = pydicom.dcmread(inst.path)
            ds.StudyInstanceUID, ds.FrameOfReferenceUID = study, for_uid
            ds.SeriesInstanceUID, ds.SOPInstanceUID = generate_uid(), generate_uid()
            ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
            ds.SeriesDescription = f"{label}: Segmentation"
            for ref in ds.get("ReferencedSeriesSequence", []):
                ref.SeriesInstanceUID = series
                for ri in ref.get("ReferencedInstanceSequence", []):
                    ri.ReferencedSOPInstanceUID = sop_map.get(
                        str(ri.ReferencedSOPInstanceUID), ri.ReferencedSOPInstanceUID
                    )
            for fg in ds.get("PerFrameFunctionalGroupsSequence", []):
                for d in fg.get("DerivationImageSequence", []):
                    for s in d.get("SourceImageSequence", []):
                        s.ReferencedSOPInstanceUID = sop_map.get(
                            str(s.ReferencedSOPInstanceUID), s.ReferencedSOPInstanceUID
                        )
            ds.save_as(dst_dir / "SEG" / f"{ds.SOPInstanceUID}.dcm", enforce_file_format=True)
    (dst_dir / "SYNTHETIC_PERTURBATION.txt").write_text(
        f"{label}\nDerived from a real public series for testing/demo only. NOT a real "
        "follow-up scan of any patient. Original data were not modified.\n"
    )
    return dst_dir
