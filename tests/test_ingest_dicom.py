import json

import numpy as np
import pytest
import SimpleITK as sitk
from pydicom.uid import generate_uid

from dicom_factory import build_pet_ct_seg_case, write_image_series
from voxeltrace.ingest import (
    IngestError,
    build_case,
    discover_dicom,
    extract_pet_metadata,
    load_series_volume,
    series_geometry,
)


@pytest.fixture
def case_dir(tmp_path):
    info = build_pet_ct_seg_case(tmp_path / "case")
    return tmp_path / "case", info


def test_non_dicom_ignored_and_grouping(case_dir):
    root, info = case_dir
    (root / "fake.dcm").write_bytes(b"not really dicom at all")  # name must not matter
    d = discover_dicom(root)
    assert d.non_dicom_ignored == 3
    assert d.dicom_files == 3 + 4 + 1
    assert len(d.series) == 3
    assert {info["pet"], info["ct"]} <= {s.series_uid for s in d.series}
    assert {s.study_uid for s in d.series} == {info["study"]}
    cats = {s.series_uid: s.category for s in d.series}
    assert cats[info["pet"]] == "PET" and cats[info["ct"]] == "CT"
    assert sorted(cats.values()) == ["CT", "PET", "SEG"]


def test_modality_from_header_not_path(tmp_path):
    # A CT series stored in a directory called "PET" must still be CT.
    write_image_series(tmp_path / "PET", modality="CT", study_uid=generate_uid())
    (s,) = discover_dicom(tmp_path).series
    assert s.category == "CT" and s.modality == "CT"


@pytest.mark.filterwarnings("ignore::UserWarning")  # pydicom warns on the junk file
def test_malformed_dicom_warns_not_crash(tmp_path):
    write_image_series(tmp_path / "ok", modality="PT", study_uid=generate_uid())
    bad = tmp_path / "bad.dcm"
    bad.write_bytes(b"\0" * 128 + b"DICM" + b"\x02\x00\x10\x00garbage")
    d = discover_dicom(tmp_path)
    assert len(d.series) == 1
    assert d.unreadable == 1
    assert any(w.code in ("DICOM_UNREADABLE", "DICOM_MISSING_UID") for w in d.warnings)


def test_geometry_sorted_by_position_not_filename(case_dir):
    root, info = case_dir
    pet = next(s for s in discover_dicom(root).series if s.series_uid == info["pet"])
    vol = load_series_volume(pet)
    assert vol.array.shape == (3, 4, 5)
    # stored value at slice k, row 0, col 0 is k*10; rescale 2x-1
    assert vol.array[:, 0, 0].tolist() == [-1.0, 19.0, 39.0]
    g = vol.geometry
    assert g.shape_ijk == (5, 4, 3)
    assert g.spacing_ijk == (3.0, 2.0, 4.0)  # (col, row, slice)
    assert g.origin == (0.0, 0.0, -10.0)
    assert g.slice_positions_mm == [-10.0, -6.0, -2.0]
    assert g.uniform_slice_spacing is True
    assert g.extent_mm == (15.0, 8.0, 12.0)
    assert np.allclose(np.array(g.affine) @ [1, 2, 2, 1], [3.0, 4.0, -2.0, 1])


def test_loader_matches_simpleitk(case_dir):
    root, info = case_dir
    pet = next(s for s in discover_dicom(root).series if s.series_uid == info["pet"])
    vol = load_series_volume(pet)
    reader = sitk.ImageSeriesReader()
    reader.SetFileNames(reader.GetGDCMSeriesFileNames(str(root / "a_pet")))
    img = reader.Execute()
    assert img.GetSize() == vol.geometry.shape_ijk
    assert np.allclose(img.GetSpacing(), vol.geometry.spacing_ijk)
    assert np.allclose(img.GetOrigin(), vol.geometry.origin)
    assert np.allclose(sitk.GetArrayFromImage(img), vol.array)


def test_duplicate_positions_refused(tmp_path):
    uid, _ = write_image_series(
        tmp_path, modality="CT", study_uid=generate_uid(), z_positions=[0.0, 4.0, 4.0]
    )
    (s,) = discover_dicom(tmp_path).series
    geom, warns = series_geometry(s)
    assert geom is None
    assert any(w.code == "DUPLICATE_SLICE_POSITION" for w in warns)
    with pytest.raises(IngestError):
        load_series_volume(s)


def test_nonuniform_spacing_warned(tmp_path):
    write_image_series(
        tmp_path, modality="CT", study_uid=generate_uid(), z_positions=[0.0, 4.0, 10.0]
    )
    (s,) = discover_dicom(tmp_path).series
    geom, warns = series_geometry(s)
    assert geom is not None and geom.uniform_slice_spacing is False
    assert geom.spacing_ijk[2] is None
    assert any(w.code == "NONUNIFORM_SLICE_SPACING" for w in warns)


def test_inconsistent_orientation_refused(tmp_path):
    study, series, for_uid = generate_uid(), generate_uid(), generate_uid()
    write_image_series(
        tmp_path / "a",
        modality="CT",
        study_uid=study,
        series_uid=series,
        for_uid=for_uid,
        z_positions=[0.0, 4.0],
    )
    write_image_series(
        tmp_path / "b",
        modality="CT",
        study_uid=study,
        series_uid=series,
        for_uid=for_uid,
        z_positions=[8.0],
        orientation=(0.0, 1.0, 0.0, 1.0, 0.0, 0.0),
    )
    (s,) = discover_dicom(tmp_path).series
    geom, warns = series_geometry(s)
    assert geom is None
    assert any(w.code == "INCONSISTENT_ORIENTATION" for w in warns)


def test_missing_geometry_refused(tmp_path):
    write_image_series(
        tmp_path, modality="CT", study_uid=generate_uid(), drop=["ImagePositionPatient"]
    )
    (s,) = discover_dicom(tmp_path).series
    geom, warns = series_geometry(s)
    assert geom is None and warns[0].code == "GEOMETRY_MISSING"


def test_mixed_series_flagged(tmp_path):
    study, series = generate_uid(), generate_uid()
    write_image_series(tmp_path / "a", modality="CT", study_uid=study, series_uid=series)
    write_image_series(
        tmp_path / "b", modality="PT", study_uid=study, series_uid=series, z_positions=[20.0]
    )
    d = discover_dicom(tmp_path)
    codes = {w.code for w in d.warnings}
    assert "MIXED_SERIES_MODALITY" in codes and "MIXED_FRAME_OF_REFERENCE" in codes
    assert d.series[0].category == "OTHER"


def test_pet_metadata_complete(case_dir):
    root, info = case_dir
    pet = next(s for s in discover_dicom(root).series if s.series_uid == info["pet"])
    meta, warns = extract_pet_metadata(pet)
    assert meta.units == "BQML"
    assert meta.decay_correction == "START"
    assert meta.corrected_image == ["ATTN", "DECY"]
    assert meta.patient_weight == 70.5
    assert meta.radionuclide_total_dose == 3e8
    assert meta.radionuclide_half_life == 6586.2
    assert meta.radiopharmaceutical_start_time == "091500"
    assert meta.radiopharmaceutical == "Fluorodeoxyglucose"
    assert meta.rescale_slopes == [2.0] and meta.rescale_intercepts == [-1.0]
    assert meta.reconstruction_diameter == 600.0
    assert meta.missing == []


def test_pet_missing_fields_reported_not_defaulted(tmp_path):
    write_image_series(
        tmp_path,
        modality="PT",
        study_uid=generate_uid(),
        drop=["PatientWeight", "Units", "RadionuclideTotalDose", "RadiopharmaceuticalStartTime"],
    )
    (s,) = discover_dicom(tmp_path).series
    meta, _ = extract_pet_metadata(s)
    assert meta.patient_weight is None and meta.units is None
    assert meta.radionuclide_total_dose is None
    assert meta.radiopharmaceutical_start_time is None
    missing = {m.field: m for m in meta.missing}
    for f in ("PatientWeight", "Units", "RadionuclideTotalDose", "RadiopharmaceuticalStartTime"):
        assert missing[f].status == "absent" and missing[f].required


@pytest.mark.parametrize("raw", [b"NaN ", b"abc ", b"0   ", b"-70 ", b"inf "])
def test_pet_invalid_weight(tmp_path, raw):
    write_image_series(
        tmp_path, modality="PT", study_uid=generate_uid(), pet_overrides={0x00101030: raw}
    )
    (s,) = discover_dicom(tmp_path).series
    meta, _ = extract_pet_metadata(s)
    assert meta.patient_weight is None
    (m,) = [m for m in meta.missing if m.field == "PatientWeight"]
    assert m.status == "invalid" and m.raw_value == raw.decode().strip()


def test_pet_missing_radiopharm_sequence(tmp_path):
    write_image_series(
        tmp_path,
        modality="PT",
        study_uid=generate_uid(),
        drop=["RadiopharmaceuticalInformationSequence"],
    )
    (s,) = discover_dicom(tmp_path).series
    meta, _ = extract_pet_metadata(s)
    assert any(m.field == "RadiopharmaceuticalInformationSequence" for m in meta.missing)
    assert meta.radionuclide_half_life is None


def test_build_case_serialises(case_dir):
    root, info = case_dir
    case = build_case(root, dataset="synthetic")
    assert len(case.studies) == 1 and len(case.series) == 3
    assert set(case.geometries) == {info["pet"], info["ct"]}
    assert info["pet"] in case.pet_metadata
    (seg,) = case.segmentations
    assert seg.referenced_series_uids == [info["pet"]]
    assert case.provenance.non_dicom_files_ignored == 2
    assert "SYNTHETIC" not in json.dumps(case.provenance.model_dump())  # no PatientID copied
    json.loads(case.model_dump_json())
