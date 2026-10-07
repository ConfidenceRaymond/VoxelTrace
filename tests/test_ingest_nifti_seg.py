import nibabel as nib
import numpy as np
import pytest

from dicom_factory import build_pet_ct_seg_case, write_seg
from voxeltrace.ingest import (
    IngestError,
    compare_geometry,
    decode_dicom_seg,
    discover_dicom,
    load_nifti,
    load_nifti_mask,
    load_series_volume,
    parse_dicom_seg,
)


def _save(path, data, affine=None):
    nib.save(
        nib.Nifti1Image(data, np.diag([2.0, 3.0, 4.0, 1.0]) if affine is None else affine),
        str(path),
    )
    return path


def test_nifti_load(tmp_path):
    data = np.arange(24, dtype=np.float32).reshape(2, 3, 4)
    data[0, 0, 0] = np.nan
    vol = load_nifti(_save(tmp_path / "img.nii.gz", data))
    assert vol.array.shape == (2, 3, 4)
    assert vol.geometry.shape_ijk == (2, 3, 4)
    assert vol.geometry.spacing_ijk == (2.0, 3.0, 4.0)
    assert vol.geometry.coordinate_system == "RAS"
    assert vol.on_disk_dtype == "float32"
    assert vol.stats.nan_count == 1
    assert any(w.code == "NONFINITE_VOXELS" for w in vol.warnings)


def test_nifti_mask_labels_and_geometry(tmp_path):
    img = _save(tmp_path / "img.nii.gz", np.zeros((2, 3, 4), np.float32))
    ref = load_nifti(img).geometry
    m = np.zeros((2, 3, 4), np.uint8)
    m[0, 0, :2] = 1
    m[1, 2, 3] = 3
    mask = load_nifti_mask(_save(tmp_path / "m.nii.gz", m), reference=ref)
    assert mask.metadata.label_values == [0, 1, 3]
    assert mask.metadata.label_voxel_counts == {0: 21, 1: 2, 3: 1}
    assert mask.metadata.segmentation_type == "LABELMAP"
    assert mask.metadata.geometry_matches_reference is True


def test_nifti_mask_geometry_mismatch(tmp_path):
    ref = load_nifti(_save(tmp_path / "img.nii.gz", np.zeros((2, 3, 4), np.float32))).geometry
    shifted = np.diag([2.0, 3.0, 4.0, 1.0])
    shifted[0, 3] = 5.0
    mask = load_nifti_mask(
        _save(tmp_path / "m.nii.gz", np.zeros((2, 3, 4), np.uint8), shifted), reference=ref
    )
    assert mask.metadata.geometry_matches_reference is False
    assert any(w.code == "MASK_GEOMETRY_MISMATCH" for w in mask.warnings)
    bad_shape = load_nifti_mask(
        _save(tmp_path / "m2.nii.gz", np.zeros((2, 3, 5), np.uint8)), reference=ref
    )
    assert bad_shape.metadata.geometry_matches_reference is False


def test_nifti_mask_rejects_non_label(tmp_path):
    with pytest.raises(ValueError, match="non-integer"):
        load_nifti_mask(_save(tmp_path / "m.nii.gz", np.full((2, 2, 2), 0.5, np.float32)))


def test_dicom_vs_nifti_grid_comparison(tmp_path):
    info = build_pet_ct_seg_case(tmp_path / "case")
    pet = next(s for s in discover_dicom(tmp_path / "case").series if s.series_uid == info["pet"])
    g = load_series_volume(pet).geometry
    ras = np.array(g.affine_ras())
    nifti = load_nifti(_save(tmp_path / "pet.nii.gz", np.zeros(g.shape_ijk, np.float32), ras))
    assert compare_geometry(g, nifti.geometry) == (True, "same grid")


def test_seg_metadata(tmp_path):
    info = build_pet_ct_seg_case(tmp_path / "case")
    meta, warns = parse_dicom_seg(info["seg"])
    assert meta.source == "DICOM_SEG" and meta.segmentation_type == "BINARY"
    assert meta.referenced_series_uids == [info["pet"]]
    assert meta.frame_of_reference_uid == info["for"]
    (seg,) = meta.segments
    assert (seg.number, seg.label, seg.algorithm_type, seg.type) == (1, "Lesion", "MANUAL", "Mass")
    assert seg.category == "Morphologically Altered Structure"
    assert warns == []


def test_seg_decode_onto_pet_grid(tmp_path):
    info = build_pet_ct_seg_case(tmp_path / "case")
    pet = next(s for s in discover_dicom(tmp_path / "case").series if s.series_uid == info["pet"])
    dec = decode_dicom_seg(info["seg"], pet)
    assert dec.metadata.pixel_decoding == "DECODED"
    m = dec.masks[1]
    assert m.shape == (3, 4, 5)
    assert m[1].astype(np.uint8).tolist() == info["mask"].tolist()  # z=-6 is slice 1
    assert not m[0].any() and not m[2].any()


def test_seg_decode_refuses_wrong_reference_and_fractional(tmp_path):
    info = build_pet_ct_seg_case(tmp_path / "case")
    series = {s.series_uid: s for s in discover_dicom(tmp_path / "case").series}
    with pytest.raises(IngestError, match="not referenced"):
        decode_dicom_seg(info["seg"], series[info["ct"]])
    frac = write_seg(
        tmp_path / "frac.dcm",
        study_uid=info["study"],
        for_uid=info["for"],
        referenced_series_uid=info["pet"],
        rows=4,
        cols=5,
        pixel_spacing=(2.0, 3.0),
        frames=[(1, -6.0, info["mask"])],
        segmentation_type="FRACTIONAL",
    )
    with pytest.raises(IngestError, match="FRACTIONAL"):
        decode_dicom_seg(frac, series[info["pet"]])
    off = write_seg(
        tmp_path / "off.dcm",
        study_uid=info["study"],
        for_uid=info["for"],
        referenced_series_uid=info["pet"],
        rows=4,
        cols=5,
        pixel_spacing=(2.0, 3.0),
        frames=[(1, -5.0, info["mask"])],
    )
    with pytest.raises(IngestError, match="does not match any reference slice"):
        decode_dicom_seg(off, series[info["pet"]])
