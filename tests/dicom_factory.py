"""Tiny synthetic DICOM writers for tests. No real patient data; all values invented."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
from pydicom.dataelem import RawDataElement
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.pixels import pack_bits
from pydicom.sequence import Sequence as DicomSequence
from pydicom.tag import Tag
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

PET_SOP = "1.2.840.10008.5.1.4.1.1.128"
CT_SOP = "1.2.840.10008.5.1.4.1.1.2"
SEG_SOP = "1.2.840.10008.5.1.4.1.1.66.4"
AXIAL = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)


def _base(sop_class: str, modality: str, study_uid: str, series_uid: str, for_uid: str) -> Dataset:
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = sop_class
    meta.MediaStorageSOPInstanceUID = generate_uid()
    ds = Dataset()
    ds.file_meta = meta
    ds.SOPClassUID = sop_class
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.Modality = modality
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.FrameOfReferenceUID = for_uid
    ds.StudyDescription = "SYNTHETIC STUDY"
    ds.PatientID = "SYNTHETIC"
    ds.Manufacturer = "SyntheticCo"
    ds.ManufacturerModelName = "Fixture-1"
    ds.SoftwareVersions = "0.0"
    return ds


def write_image_series(
    out_dir: Path,
    *,
    modality: str,
    study_uid: str,
    series_uid: str | None = None,
    for_uid: str | None = None,
    n_slices: int = 3,
    rows: int = 4,
    cols: int = 5,
    z_positions: Sequence[float] | None = None,
    pixel_spacing: tuple[float, float] = (2.0, 3.0),
    orientation: Sequence[float] = AXIAL,
    file_order: Sequence[int] | None = None,
    pet_overrides: dict | None = None,
    drop: Sequence[str] = (),
    slope: float = 2.0,
    intercept: float = -1.0,
    slopes: Sequence[float] | None = None,
    intercepts: Sequence[float] | None = None,
    stored: np.ndarray | None = None,
    rp_overrides: dict | None = None,
    per_slice: dict[int, dict] | None = None,
) -> tuple[str, list[Path]]:
    """Write a single-frame series. Pixel value at slice k = stored k*10 + row + col.

    ``slopes``/``intercepts``/``stored`` (shape n×rows×cols) override pixel scaling per slice
    (index k is geometric order). ``rp_overrides`` set radiopharmaceutical-item attributes
    (bytes = raw DS). ``per_slice[k]`` sets top-level attributes on slice k only.

    Files are named so that alphabetical order is the REVERSE of geometric order, and
    InstanceNumber is deliberately scrambled, so tests prove geometry-based sorting.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    series_uid = series_uid or generate_uid()
    for_uid = for_uid or generate_uid()
    z_positions = (
        list(z_positions) if z_positions is not None else [-10.0 + 4.0 * k for k in range(n_slices)]
    )
    sop = PET_SOP if modality == "PT" else CT_SOP
    paths = []
    order = list(file_order) if file_order is not None else list(range(len(z_positions)))
    for k, z in enumerate(z_positions):
        ds = _base(sop, modality, study_uid, series_uid, for_uid)
        ds.SeriesDescription = f"SYNTHETIC {modality}"
        ds.SeriesNumber = 1 if modality == "PT" else 2
        ds.InstanceNumber = (k * 7) % len(z_positions) + 1  # scrambled vs geometry
        ds.ImagePositionPatient = [0.0, 0.0, z]
        ds.ImageOrientationPatient = list(orientation)
        ds.PixelSpacing = list(pixel_spacing)
        ds.SliceThickness = 4.0
        ds.Rows, ds.Columns = rows, cols
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 16, 16, 15, 0
        rr, cc = np.mgrid[0:rows, 0:cols]
        pix = stored[k] if stored is not None else k * 10 + rr + cc
        ds.PixelData = np.asarray(pix).astype(np.uint16).tobytes()
        ds.RescaleSlope = slopes[k] if slopes is not None else slope
        ds.RescaleIntercept = intercepts[k] if intercepts is not None else intercept
        if modality == "PT":
            _add_pet_fields(ds)
            for key, val in (pet_overrides or {}).items():
                if isinstance(val, bytes):  # raw (possibly invalid) value
                    tag = Tag(key)
                    ds._dict[tag] = RawDataElement(tag, "DS", len(val), val, 0, False, True)
                else:
                    setattr(ds, key, val)
            rp = ds.RadiopharmaceuticalInformationSequence[0]
            for key, val in (rp_overrides or {}).items():
                if isinstance(val, bytes):
                    tag = Tag(key)
                    rp._dict[tag] = RawDataElement(tag, "DS", len(val), val, 0, False, True)
                else:
                    setattr(rp, key, val)
        for key, val in (per_slice or {}).get(k, {}).items():
            setattr(ds, key, val)
        for kw in drop:
            if kw in ds:
                del ds[kw]
            elif (
                "RadiopharmaceuticalInformationSequence" in ds
                and kw in ds.RadiopharmaceuticalInformationSequence[0]
            ):
                del ds.RadiopharmaceuticalInformationSequence[0][kw]
        path = out_dir / f"img_{len(z_positions) - order[k]:03d}.dcm"
        ds.save_as(path, enforce_file_format=True)
        paths.append(path)
    return series_uid, paths


def _add_pet_fields(ds: Dataset) -> None:
    ds.Units = "BQML"
    ds.DecayCorrection = "START"
    ds.CorrectedImage = ["ATTN", "DECY"]
    ds.PatientWeight = "70.5"
    ds.SeriesDate = "20200101"
    ds.SeriesTime = "101500"
    ds.AcquisitionDate = "20200101"
    ds.AcquisitionTime = "101500"
    rp = Dataset()
    rp.Radiopharmaceutical = "Fluorodeoxyglucose"
    rp.RadionuclideTotalDose = "300000000"
    rp.RadionuclideHalfLife = "6586.2"
    rp.RadiopharmaceuticalStartTime = "091500"
    rp.RadiopharmaceuticalStartDateTime = "20200101091500"
    code = Dataset()
    code.CodeValue, code.CodingSchemeDesignator, code.CodeMeaning = "C-111A1", "SRT", "^18^Fluorine"
    rp.RadionuclideCodeSequence = DicomSequence([code])
    ds.RadiopharmaceuticalInformationSequence = DicomSequence([rp])
    ds.ReconstructionMethod = "SYNTHETIC OSEM"
    ds.ReconstructionDiameter = "600"


def write_seg(
    path: Path,
    *,
    study_uid: str,
    for_uid: str,
    referenced_series_uid: str,
    rows: int,
    cols: int,
    pixel_spacing: tuple[float, float],
    frames: Sequence[tuple[int, float, np.ndarray]],
    segmentation_type: str = "BINARY",
    labels: Sequence[str] = ("Lesion",),
    orientation: Sequence[float] = AXIAL,
    xy0: tuple[float, float] = (0.0, 0.0),
) -> Path:
    """Write a multi-frame DICOM SEG. ``frames`` = (segment number, z position, 2-D 0/1 mask)."""
    ds = _base(SEG_SOP, "SEG", study_uid, generate_uid(), for_uid)
    ds.SeriesDescription = "SYNTHETIC SEG"
    ds.SegmentationType = segmentation_type
    ds.Rows, ds.Columns = rows, cols
    ds.NumberOfFrames = len(frames)
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 1, 1, 0, 0
    segs = []
    for n, label in enumerate(labels, start=1):
        item = Dataset()
        item.SegmentNumber = n
        item.SegmentLabel = label
        item.SegmentDescription = f"synthetic {label.lower()}"
        item.SegmentAlgorithmType = "MANUAL"
        cat = Dataset()
        cat.CodeValue, cat.CodingSchemeDesignator, cat.CodeMeaning = (
            "49755003",
            "SCT",
            "Morphologically Altered Structure",
        )
        item.SegmentedPropertyCategoryCodeSequence = DicomSequence([cat])
        typ = Dataset()
        typ.CodeValue, typ.CodingSchemeDesignator, typ.CodeMeaning = "4147007", "SCT", "Mass"
        item.SegmentedPropertyTypeCodeSequence = DicomSequence([typ])
        segs.append(item)
    ds.SegmentSequence = DicomSequence(segs)
    ref = Dataset()
    ref.SeriesInstanceUID = referenced_series_uid
    ds.ReferencedSeriesSequence = DicomSequence([ref])
    shared = Dataset()
    pms = Dataset()
    pms.PixelSpacing = list(pixel_spacing)
    pms.SliceThickness = 4.0
    shared.PixelMeasuresSequence = DicomSequence([pms])
    pos_ori = Dataset()
    pos_ori.ImageOrientationPatient = list(orientation)
    shared.PlaneOrientationSequence = DicomSequence([pos_ori])
    ds.SharedFunctionalGroupsSequence = DicomSequence([shared])
    per_frame = []
    for seg_num, z, _ in frames:
        fg = Dataset()
        sis = Dataset()
        sis.ReferencedSegmentNumber = seg_num
        fg.SegmentIdentificationSequence = DicomSequence([sis])
        pp = Dataset()
        pp.ImagePositionPatient = [xy0[0], xy0[1], z]
        fg.PlanePositionSequence = DicomSequence([pp])
        per_frame.append(fg)
    ds.PerFrameFunctionalGroupsSequence = DicomSequence(per_frame)
    ds.PixelData = pack_bits(np.stack([m.astype(np.uint8) for _, _, m in frames]))
    path.parent.mkdir(parents=True, exist_ok=True)
    ds.save_as(path, enforce_file_format=True)
    return path


def build_pet_ct_seg_case(root: Path) -> dict:
    """PET (3 slices), CT (4 slices) in one study + a SEG on the PET grid + junk files."""
    study = generate_uid()
    for_uid = generate_uid()
    pet_uid, _ = write_image_series(
        root / "a_pet", modality="PT", study_uid=study, for_uid=for_uid, file_order=[2, 0, 1]
    )
    ct_uid, _ = write_image_series(
        root / "b_ct",
        modality="CT",
        study_uid=study,
        for_uid=for_uid,
        n_slices=4,
        rows=6,
        cols=6,
        pixel_spacing=(1.0, 1.0),
        slope=1.0,
        intercept=-1024.0,
    )
    mask = np.zeros((4, 5), dtype=np.uint8)
    mask[1:3, 2:4] = 1
    seg_path = write_seg(
        root / "c_seg" / "seg.dcm",
        study_uid=study,
        for_uid=for_uid,
        referenced_series_uid=pet_uid,
        rows=4,
        cols=5,
        pixel_spacing=(2.0, 3.0),
        frames=[(1, -6.0, mask)],
    )
    (root / "README.txt").write_text("not dicom")
    (root / "b_ct" / "notes.json").write_text("{}")
    return {
        "study": study,
        "for": for_uid,
        "pet": pet_uid,
        "ct": ct_uid,
        "seg": seg_path,
        "mask": mask,
    }
