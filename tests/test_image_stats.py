import numpy as np
import pytest

from voxeltrace.quant import compute_image_stats


def test_finite_array():
    a = np.arange(1, 101, dtype=np.float32).reshape(4, 5, 5)
    s = compute_image_stats(a)
    assert s.shape == (4, 5, 5)
    assert s.voxel_count == 100 and s.finite_count == 100
    assert s.nan_count == s.posinf_count == s.neginf_count == s.zero_count == 0
    assert s.finite_min == 1.0 and s.finite_max == 100.0
    assert s.finite_mean == pytest.approx(50.5)
    assert s.finite_std == pytest.approx(np.arange(1, 101).std())
    assert s.median == pytest.approx(50.5)
    assert s.p01 == pytest.approx(1.99)
    assert s.p99 == pytest.approx(99.01)


def test_nan_and_inf_counted_not_coerced():
    a = np.array([1.0, np.nan, np.nan, np.inf, -np.inf, 0.0, 3.0, 5.0])
    original = a.copy()
    s = compute_image_stats(a)
    assert s.voxel_count == 8 and s.finite_count == 4
    assert s.nan_count == 2 and s.nan_fraction == pytest.approx(0.25)
    assert s.posinf_count == 1 and s.neginf_count == 1
    assert s.zero_count == 1 and s.zero_fraction == pytest.approx(0.125)
    assert s.finite_min == 0.0 and s.finite_max == 5.0
    assert s.finite_mean == pytest.approx(2.25)
    assert s.median == pytest.approx(2.0)
    np.testing.assert_array_equal(a, original)  # input untouched


def test_all_zero():
    s = compute_image_stats(np.zeros((3, 3, 3), dtype=np.float64))
    assert s.zero_count == 27 and s.zero_fraction == 1.0
    assert s.finite_min == s.finite_max == s.finite_mean == s.finite_std == 0.0
    assert s.p01 == s.p99 == s.median == 0.0


def test_no_finite_voxels():
    s = compute_image_stats(np.array([np.nan, np.inf, -np.inf]))
    assert s.finite_count == 0 and not s.has_finite_voxels
    assert s.nan_count == 1 and s.posinf_count == 1 and s.neginf_count == 1
    for field in ("finite_min", "finite_max", "finite_mean", "finite_std", "median", "p01", "p99"):
        assert getattr(s, field) is None


def test_integer_array_no_overflow():
    a = np.full(10, 200, dtype=np.uint8)
    s = compute_image_stats(a)
    assert s.finite_mean == 200.0 and s.dtype == "uint8"


@pytest.mark.parametrize(
    "bad",
    [np.array(["a", "b"]), np.array([True, False]), np.array([1 + 2j]), [1.0, 2.0]],
)
def test_invalid_input_rejected(bad):
    with pytest.raises(TypeError):
        compute_image_stats(bad)


def test_empty_rejected():
    with pytest.raises(ValueError):
        compute_image_stats(np.array([], dtype=np.float32))


def test_deterministic():
    rng = np.random.default_rng(0)
    a = rng.normal(size=(8, 8, 8))
    assert compute_image_stats(a) == compute_image_stats(a.copy())
