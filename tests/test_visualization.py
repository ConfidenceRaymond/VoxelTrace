import io
import json

import numpy as np
import pytest
from PIL import Image

from voxeltrace.schemas import ImageGeometry
from voxeltrace.visualization import (
    PlaneMapping,
    RenderError,
    RenderVerificationError,
    add_footer,
    crop_box,
    fused_axial,
    mask_annotations,
    patient_to_voxel,
    peak_circle,
    pet_axial,
    pet_coronal_mip,
    png_bytes,
    point_annotation,
    resample_ct_to_pet,
    verify_axial_render,
    voxel_to_patient,
)
from voxeltrace.visualization.annotations import displayed_value, draw


def geom(
    shape_kji=(5, 12, 10),
    spacing=(2.0, 3.0, 4.0),
    origin=(10.0, 20.0, 30.0),
    direction=(1, 0, 0, 0, 1, 0, 0, 0, 1),
):
    nk, nj, ni = shape_kji
    d = np.asarray(direction, float).reshape(3, 3)
    aff = np.eye(4)
    aff[:3, :3] = d * np.asarray(spacing)
    aff[:3, 3] = origin
    return ImageGeometry(
        coordinate_system="LPS",
        shape_ijk=(ni, nj, nk),
        spacing_ijk=spacing,
        origin=origin,
        direction=tuple(float(v) for v in d.ravel()),
        affine=aff.tolist(),
        extent_mm=(ni * 2.0, nj * 3.0, nk * 4.0),
        uniform_slice_spacing=True,
    )


def decode(png: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))


# ----------------------------------------------------------------- coordinates


def test_voxel_patient_roundtrip_analytic():
    g = geom()
    # (k, j, i) = (1, 2, 3) -> x = 10 + 3*2, y = 20 + 2*3, z = 30 + 1*4
    assert voxel_to_patient(g, (1, 2, 3)) == (16.0, 26.0, 34.0)
    assert patient_to_voxel(g, (16.0, 26.0, 34.0)) == pytest.approx((1, 2, 3))


@pytest.mark.parametrize("flip", [False, True])
@pytest.mark.parametrize("scale", [1, 2, 3])
def test_plane_mapping_roundtrip_every_voxel(flip, scale):
    m = PlaneMapping(a0=2, b0=1, n_a=5, n_b=4, sx=scale, sy=scale, flip_x=flip)
    seen = set()
    for a in range(2, 7):
        for b in range(1, 5):
            x, y = m.voxel_to_px(a, b)
            assert m.px_to_voxel(x, y) == (a, b)
            x0, y0, x1, y1 = m.voxel_block(a, b)
            assert (x1 - x0 + 1, y1 - y0 + 1) == (scale, scale)
            for xx in range(x0, x1 + 1):
                for yy in range(y0, y1 + 1):
                    assert m.px_to_voxel(xx, yy) == (a, b)
                    seen.add((xx, yy))
    assert len(seen) == m.width * m.height  # blocks tile the image exactly
    with pytest.raises(RenderError):
        m.voxel_to_px(0, 0)


def test_radiological_vs_neurological_flip():
    rad = PlaneMapping(0, 0, 10, 1, 1, 1, flip_x=False)
    neu = PlaneMapping(0, 0, 10, 1, 1, 1, flip_x=True)
    # i = 0 is the patient's RIGHT-most column (smallest LPS x): image left in radiological
    assert rad.voxel_to_px(0, 0) == (0, 0)
    assert neu.voxel_to_px(0, 0) == (9, 0)


# ----------------------------------------------------------------- rendering alignment


@pytest.mark.parametrize("convention", ["radiological", "neurological"])
@pytest.mark.parametrize("crop", [None, [3, 4, 9, 10]])
def test_hot_voxel_point_annotation_matches_png(convention, crop):
    g = geom()
    suv = np.zeros((5, 12, 10))
    suv[2, 5, 7] = 10.0
    rgb, m, params = pet_axial(
        suv, g, 2, window=(0, 8), cmap="gray", scale=3, convention=convention, crop=crop
    )
    img = decode(png_bytes(rgb))
    ann = point_annotation((2, 5, 7), 2, m, "suvmax", "test")
    x, y = ann.value.value
    assert img[y, x].tolist() == [255, 255, 255]  # exactly the hot voxel
    hot = np.argwhere(img[..., 0] == 255)
    assert len(hot) == 9  # one 3×3 block
    assert m.voxel_block(7, 5) == (
        hot[:, 1].min(),
        hot[:, 0].min(),
        hot[:, 1].max(),
        hot[:, 0].max(),
    )
    assert params.mm_per_px_x == pytest.approx(2.0 / 3)


def test_bbox_and_pixel_count_match_rendered_mask():
    g = geom()
    mask = np.zeros((5, 12, 10), bool)
    mask[2, 3:6, 4:8] = True  # 3 rows × 4 columns = 12 voxels
    mask[2, 8, 1] = True  # second island
    suv = np.where(mask, 5.0, 0.0)
    rgb, m, _ = pet_axial(suv, g, 2, scale=2)
    anns = mask_annotations(mask, 2, m, "seg1")
    box = next(a for a in anns if a.kind == "bbox").value.value
    count = next(a for a in anns if a.kind == "mask_pixel_count").value.value
    assert count == 13 * 4
    assert box == [1 * 2, 3 * 2, 8 * 2 - 1, 9 * 2 - 1]
    assert mask_annotations(mask, 0, m, "seg1") == []


def test_rendering_is_deterministic_and_does_not_alter_data():
    g = geom()
    rng = np.random.default_rng(0)
    suv = rng.random((5, 12, 10)) * 10
    before = suv.copy()
    a = png_bytes(pet_axial(suv, g, 1)[0])
    b = png_bytes(pet_axial(suv, g, 1)[0])
    assert a == b
    np.testing.assert_array_equal(suv, before)


def test_nonstandard_orientation_refused():
    g = geom(direction=(0, 1, 0, 1, 0, 0, 0, 0, -1))
    with pytest.raises(RenderError, match="orientation"):
        pet_axial(np.zeros((5, 12, 10)), g, 0)


def test_mip_superior_at_top_and_point_mapping():
    g = geom()
    suv = np.zeros((5, 12, 10))
    suv[1, 3, 4] = 9.0  # k=1 is near the inferior end
    rgb, m, params = pet_coronal_mip(suv, g, window=(0, 8), cmap="gray", scale=1)
    assert params.scale_y == 2  # round(1 * 4 / 2)
    x, y = m.voxel_to_px(4, 1)  # (a=i, b=k)
    assert rgb[y, x].tolist() == [255, 255, 255]
    assert y == (5 - 1 - 1) * 2 + 1  # flipped: superior rows on top


def test_ct_resample_identity_and_frame_of_reference_guard():
    g = geom()
    ct = np.arange(5 * 12 * 10, dtype=float).reshape(5, 12, 10)
    np.testing.assert_allclose(resample_ct_to_pet(ct, g, g, "1.2", "1.2"), ct, atol=1e-3)
    with pytest.raises(RenderError, match="FrameOfReference"):
        resample_ct_to_pet(ct, g, g, "1.2", "1.3")


def test_fusion_shape_and_determinism():
    g = geom()
    suv = np.zeros((5, 12, 10))
    suv[2, 2, 2] = 8.0
    ct = np.full((5, 12, 10), 40.0)
    a, m, p = fused_axial(suv, ct, g, 2, scale=2)
    assert a.shape == (24, 20, 3) and p.pet_alpha == 0.7
    assert png_bytes(a) == png_bytes(fused_axial(suv, ct, g, 2, scale=2)[0])


def test_peak_circle_radius_shrinks_off_centre():
    m = PlaneMapping(0, 0, 10, 10, 1, 1)
    c0 = peak_circle((2, 5, 5), 2, 3.0, m, 1.0, "t")
    c1 = peak_circle((2, 5, 5), 3, 3.0, m, 1.0, "t")
    assert c0.value.value[2] == pytest.approx(6.2035, abs=1e-4)
    assert c1.value.value[2] == pytest.approx((6.2035**2 - 9) ** 0.5, abs=1e-3)
    assert peak_circle((2, 5, 5), 5, 3.0, m, 1.0, "t") is None  # 9 mm > r


def test_crop_box_kept_inside_image():
    g = geom()
    assert crop_box((0, 0), g, size_mm=8) == [0, 0, 3, 2]
    assert crop_box((11, 9), g, size_mm=8) == [6, 9, 9, 11]
    assert crop_box((5, 5), g, size_mm=1000) == [0, 0, 9, 11]


def test_footer_leaves_image_region_untouched():
    rgb = np.full((20, 30, 3), 7, np.uint8)
    out = add_footer(rgb, ["SUV window 0-8"], mm_per_px=1.0, scale_bar_mm=10)
    np.testing.assert_array_equal(out[:20], rgb)
    assert out.shape[0] > 20


# ----------------------------------------------------------------- Part K verification


def _scene():
    g = geom()
    mask = np.zeros((5, 12, 10), bool)
    mask[2, 3:7, 3:7] = True
    suv = np.where(mask, 3.0, 0.5)
    suv[2, 4, 5] = 12.5
    ev = {"measured": {"lesions": [{"segment_number": 1, "suv_max": 12.5}]}}
    rgb, m, _ = pet_axial(suv, g, 2, scale=3)
    anns = mask_annotations(mask, 2, m, "seg1") + [point_annotation((2, 4, 5), 2, m, "suvmax", "t")]
    rgb = draw(rgb, m.expand(mask[2]), anns)
    shown = [displayed_value(ev, "measured.lesions[0].suv_max", "SUVmax", unit="g/mL")]
    return dict(
        rgb=rgb,
        mask=mask,
        suv=suv,
        k=2,
        m=m,
        anns=anns,
        segment_number=1,
        expected_segment=1,
        suvmax_kji=(2, 4, 5),
        suv_max=12.5,
        displayed=shown,
        evidence_json_text=json.dumps(ev),
        outline_drawn=True,
    )


def test_verification_passes_on_consistent_render():
    verify_axial_render(**_scene())


@pytest.mark.parametrize("mutate", ["segment", "marker", "value", "outline", "bbox"])
def test_verification_fails_on_mismatch(mutate):
    s = _scene()
    if mutate == "segment":
        s["expected_segment"] = 2
    elif mutate == "marker":
        s["suvmax_kji"] = (2, 5, 5)
    elif mutate == "value":
        s["evidence_json_text"] = json.dumps(
            {"measured": {"lesions": [{"segment_number": 1, "suv_max": 99.0}]}}
        )
    elif mutate == "outline":
        s["rgb"] = s["rgb"].copy()
        s["rgb"][s["m"].voxel_block(3, 3)[1], s["m"].voxel_block(3, 3)[0]] = 0
    elif mutate == "bbox":
        s["anns"][0].value.value = [0, 0, 1, 1]
    with pytest.raises(RenderVerificationError):
        verify_axial_render(**s)


def test_suvpeak_marker_verified_against_peak_centre():
    s = _scene()
    m = s["m"]
    c = peak_circle((2, 4, 5), 2, 4.0, m, 2.0 / 3, "t")
    s["anns"] = s["anns"] + [c]
    verify_axial_render(**s, suvpeak_kji=(2, 4, 5), slice_spacing_mm=4.0, mm_per_px=2.0 / 3)
    with pytest.raises(RenderVerificationError, match="SUVpeak marker centre"):
        verify_axial_render(**s, suvpeak_kji=(2, 4, 6), slice_spacing_mm=4.0, mm_per_px=2.0 / 3)
    with pytest.raises(RenderVerificationError, match="radius"):
        verify_axial_render(**s, suvpeak_kji=(3, 4, 5), slice_spacing_mm=4.0, mm_per_px=2.0 / 3)
