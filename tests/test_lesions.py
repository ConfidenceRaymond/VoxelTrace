import itertools
import math

import numpy as np
import pytest

from voxeltrace.quant.lesions import (
    PEAK_RADIUS_MM,
    quantify_segments,
    sphere_offsets,
    summarize,
    suv_peak,
)
from voxeltrace.schemas import ImageGeometry, SegmentInfo


def geom(shape_kji, spacing_ijk=(2.0, 2.0, 2.0)):
    nk, nj, ni = shape_kji
    aff = np.diag([*spacing_ijk, 1.0]).tolist()
    return ImageGeometry(
        coordinate_system="LPS",
        shape_ijk=(ni, nj, nk),
        spacing_ijk=spacing_ijk,
        origin=(0.0, 0.0, 0.0),
        direction=(1, 0, 0, 0, 1, 0, 0, 0, 1),
        affine=aff,
        extent_mm=(ni * spacing_ijk[0], nj * spacing_ijk[1], nk * spacing_ijk[2]),
        uniform_slice_spacing=True,
    )


def brute_kernel_count(spacing_kji, r):
    reach = [int(r // s) + 1 for s in spacing_kji]
    return sum(
        1
        for d in itertools.product(*(range(-n, n + 1) for n in reach))
        if sum((a * s) ** 2 for a, s in zip(d, spacing_kji, strict=True)) <= r * r
    )


def test_radius_is_one_cm3_not_one_cm_diameter():
    assert pytest.approx(6.2035, abs=1e-4) == PEAK_RADIUS_MM  # (3/4π)^(1/3) cm
    assert 4 / 3 * math.pi * (PEAK_RADIUS_MM / 10) ** 3 == pytest.approx(1.0, rel=1e-12)
    assert PEAK_RADIUS_MM != 5.0


@pytest.mark.parametrize(
    "spacing", [(1.0, 1.0, 1.0), (3.0, 2.0, 2.0), (3.0, 2.036, 2.036), (0.5, 0.5, 0.5)]
)
def test_kernel_matches_brute_force(spacing):
    offs = sphere_offsets(spacing)
    assert len(offs) == brute_kernel_count(spacing, PEAK_RADIUS_MM)
    assert (offs == 0).all(axis=1).any()  # centre included
    assert len({tuple(o) for o in offs}) == len({tuple(-o) for o in offs})  # symmetric


def test_kernel_volume_converges_to_1ml():
    n = len(sphere_offsets((0.5, 0.5, 0.5)))
    assert n * 0.125 / 1000 == pytest.approx(1.0, rel=0.02)


def test_basic_metrics_volume_max_mean_tlg():
    suv = np.zeros((6, 6, 6))
    m = np.zeros_like(suv, dtype=bool)
    m[2:4, 2:4, 2:4] = True  # 8 voxels × 8 mm³ = 0.064 mL
    suv[2:4, 2:4, 2:4] = [[[1, 2], [3, 4]], [[5, 6], [7, 8]]]
    (les,) = quantify_segments(
        suv, geom(suv.shape), {1: m}, [SegmentInfo(number=1, label="A")], compute_peak=False
    )
    assert les.voxel_count == 8 and les.segment_label == "A"
    assert les.voxel_volume_ml == pytest.approx(0.008)
    assert les.mtv_ml == pytest.approx(0.064)
    assert (les.suv_min, les.suv_max) == (1.0, 8.0)
    assert les.suv_mean == pytest.approx(4.5) and les.suv_median == pytest.approx(4.5)
    assert les.suv_std == pytest.approx(math.sqrt(5.25))  # population SD of 1..8
    assert les.tlg == pytest.approx(0.064 * 4.5)
    assert les.n_components == 1


def test_anisotropic_voxel_volume():
    suv = np.ones((4, 4, 4))
    m = np.zeros_like(suv, dtype=bool)
    m[1, 1, 1] = True
    (les,) = quantify_segments(suv, geom(suv.shape, (2.0, 2.5, 3.0)), {1: m}, compute_peak=False)
    assert les.mtv_ml == pytest.approx(2.0 * 2.5 * 3.0 / 1000)


def test_multiple_labels_and_components_and_summary():
    suv = np.zeros((10, 10, 10))
    a = np.zeros_like(suv, dtype=bool)
    b = np.zeros_like(suv, dtype=bool)
    a[1, 1, 1] = a[8, 8, 8] = True  # two disconnected parts
    b[5, 5, 5] = True
    suv[1, 1, 1], suv[8, 8, 8], suv[5, 5, 5] = 3.0, 5.0, 7.0
    les = quantify_segments(suv, geom(suv.shape), {2: b, 1: a}, compute_peak=False)
    assert [x.segment_number for x in les] == [1, 2]
    assert les[0].n_components == 2 and les[0].suv_mean == 4.0
    assert any(w.code == "MULTIPLE_COMPONENTS" for w in les[0].warnings)
    s = summarize(les)
    assert s.n_segments == 2 and s.max_suv_max == 7.0 and s.max_suv_max_segment == 2
    assert s.total_mtv_ml == pytest.approx(3 * 0.008)
    assert s.total_tlg == pytest.approx(2 * 0.008 * 4.0 + 0.008 * 7.0)


def test_empty_segment_reported():
    suv = np.ones((3, 3, 3))
    (les,) = quantify_segments(suv, geom(suv.shape), {1: np.zeros_like(suv, dtype=bool)})
    assert les.voxel_count == 0 and les.suv_mean is None and les.tlg is None
    assert les.warnings[0].code == "EMPTY_SEGMENT"


def test_suvpeak_uniform_hot_region_equals_value():
    suv = np.ones((20, 20, 20))
    suv[3:17, 3:17, 3:17] = 10.0  # 14 voxels × 1 mm; kernel reaches ±6 voxels (r≈6.2 mm)
    m = suv == 10.0
    pk = suv_peak(suv, m, (1.0, 1.0, 1.0))
    # centres 9 or 10 keep the whole ±6-voxel sphere inside [3, 17) → fully hot sphere
    assert pk.status == "COMPUTED" and pk.value == pytest.approx(10.0)
    assert pk.fraction_of_sphere_voxels_in_segment == 1.0


def test_suvpeak_single_hot_voxel_is_value_over_kernel_count():
    suv = np.zeros((21, 21, 21))
    suv[10, 10, 10] = 1000.0
    m = np.zeros_like(suv, dtype=bool)
    m[10, 10, 10] = True
    pk = suv_peak(suv, m, (2.0, 2.0, 2.0))
    n = brute_kernel_count((2.0, 2.0, 2.0), PEAK_RADIUS_MM)
    assert pk.kernel_voxel_count == n
    assert pk.value == pytest.approx(1000.0 / n)
    assert pk.fraction_of_sphere_voxels_in_segment == pytest.approx(1 / n)


def test_suvpeak_centre_restricted_to_segment_and_maximises_mean():
    suv = np.zeros((30, 30, 30))
    suv[5:8, 5:8, 5:8] = 4.0  # hot blob A (inside segment)
    suv[20:25, 20:25, 20:25] = 50.0  # hotter blob B (outside segment)
    m = np.zeros_like(suv, dtype=bool)
    m[4:9, 4:9, 4:9] = True
    pk = suv_peak(suv, m, (1.0, 1.0, 1.0))
    assert pk.center_kji == (6, 6, 6)  # centre of blob A, not blob B
    assert pk.value < 4.0  # sphere (r≈6.2 voxels) larger than the 3³ blob → diluted


def test_suvpeak_edge_candidates_excluded():
    suv = np.ones((5, 5, 5))
    m = np.zeros_like(suv, dtype=bool)
    m[0, 0, 0] = True
    pk = suv_peak(suv, m, (2.0, 2.0, 2.0))
    assert pk.status == "NOT_AVAILABLE" and pk.candidates_excluded_at_image_edge == 1


def test_small_segment_flagged_for_peak():
    suv = np.ones((15, 15, 15))
    m = np.zeros_like(suv, dtype=bool)
    m[7, 7, 7] = True
    (les,) = quantify_segments(suv, geom(suv.shape), {1: m})
    assert les.suv_peak.status == "COMPUTED"
    assert any(w.code == "SEGMENT_SMALLER_THAN_PEAK_SPHERE" for w in les.warnings)


def test_rejects_mismatched_shapes():
    with pytest.raises(ValueError):
        quantify_segments(np.ones((3, 3, 3)), geom((3, 3, 4)), {1: np.ones((3, 3, 3), bool)})
