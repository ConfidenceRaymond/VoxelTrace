"""Reference regions: cylinder VOI, CT-guided proposals (phantom), review gate, reasons."""

import numpy as np
import pytest

from test_lesions import geom
from voxeltrace.quant.reference_auto import (
    ALGORITHM_VERSION,
    ReferenceProposal,
    propose_reference_regions,
)
from voxeltrace.quant.reference_region import (
    ReferenceRegionSpec,
    cylinder_mask,
    measure_reference_region,
    sphere_mask,
)
from voxeltrace.schemas import ImageGeometry

# ------------------------------------------------------------------ VOI masks


def _brute(g, inside):
    nk, nj, ni = g.shape_ijk[2], g.shape_ijk[1], g.shape_ijk[0]
    aff = np.asarray(g.affine)
    out = np.zeros((nk, nj, ni), bool)
    for k in range(nk):
        for j in range(nj):
            for i in range(ni):
                out[k, j, i] = inside(*(aff @ [i, j, k, 1.0])[:3])
    return out


def test_sphere_mask_bbox_equals_full_grid():
    g = geom((14, 15, 16), (2.0, 2.5, 3.0))
    c = (15.3, 17.1, 20.2)
    want = _brute(g, lambda x, y, z: (x - c[0]) ** 2 + (y - c[1]) ** 2 + (z - c[2]) ** 2 <= 81)
    assert np.array_equal(sphere_mask(g, c, 18.0), want)


def test_cylinder_mask_known_voxels():
    g = geom((20, 20, 20), (2.0, 2.0, 2.0))
    c = (20.0, 20.0, 20.0)
    m = cylinder_mask(g, c, 10.0, 20.0)
    want = _brute(
        g, lambda x, y, z: (x - c[0]) ** 2 + (y - c[1]) ** 2 <= 25 and abs(z - c[2]) <= 10
    )
    assert np.array_equal(m, want)
    # radius 5 mm on a 2 mm grid: 21 in-plane voxels; |dz| <= 10 mm: 11 slices
    assert m.sum() == 21 * 11
    assert cylinder_mask(g, (20.0, 20.0, 34.0), 10.0, 20.0) is None  # leaves the image


def test_cylinder_measurement_and_validation():
    g = geom((20, 20, 20), (2.0, 2.0, 2.0))
    suv = np.full((20, 20, 20), 1.5)
    spec = ReferenceRegionSpec(
        region="BLOOD_POOL",
        method="CYLINDER_AT_SUPPLIED_CENTRE",
        centre_patient_mm=(20.0, 20.0, 20.0),
        diameter_mm=10.0,
        length_mm=20.0,
        provenance="t",
    )
    r = measure_reference_region(suv, g, spec)
    assert r.status == "COMPUTED" and r.voxel_count == 231 and r.suv_mean == pytest.approx(1.5)
    assert r.suv_max == pytest.approx(1.5) and r.length_mm == 20.0
    bad = spec.model_copy(update={"length_mm": None})
    assert "positive length" in measure_reference_region(suv, g, bad).refusal


# ------------------------------------------------------------------ CT phantom proposer

ORIGIN = (-170.0, -170.0, 0.0)
SP = (2.0, 2.0, 3.0)
SHAPE = (120, 171, 171)  # k, j, i
LIVER_BOX = ((-130, -20), (-70, 60), (80, 215))
AORTA = (22.0, 35.0, 10.0)  # x, y, radius


def phantom_geom() -> ImageGeometry:
    nk, nj, ni = SHAPE
    aff = [
        [SP[0], 0, 0, ORIGIN[0]],
        [0, SP[1], 0, ORIGIN[1]],
        [0, 0, SP[2], ORIGIN[2]],
        [0, 0, 0, 1.0],
    ]
    return ImageGeometry(
        coordinate_system="LPS",
        shape_ijk=(ni, nj, nk),
        spacing_ijk=SP,
        origin=ORIGIN,
        direction=(1, 0, 0, 0, 1, 0, 0, 0, 1),
        affine=aff,
        extent_mm=(ni * SP[0], nj * SP[1], nk * SP[2]),
        uniform_slice_spacing=True,
    )


def phantom_ct() -> np.ndarray:
    nk, nj, ni = SHAPE
    z = ORIGIN[2] + SP[2] * np.arange(nk)[:, None, None]
    y = ORIGIN[1] + SP[1] * np.arange(nj)[None, :, None]
    x = ORIGIN[0] + SP[0] * np.arange(ni)[None, None, :]
    ct = np.full(SHAPE, -1000.0)
    body = (x / 160) ** 2 + (y / 130) ** 2 <= 1
    ct[np.broadcast_to(body, SHAPE)] = -100.0  # fat
    (x0, x1), (y0, y1), (z0, z1) = LIVER_BOX
    ct[(x >= x0) & (x <= x1) & (y >= y0) & (y <= y1) & (z >= z0) & (z <= z1)] = 60.0
    for cx in (-65.0, 65.0):
        lung = ((x - cx) / 40) ** 2 + (y / 55) ** 2 + ((z - 270) / 70) ** 2 <= 1
        ct[lung] = -800.0
    spine = np.broadcast_to(x**2 + (y - 60) ** 2 <= 15**2, SHAPE)
    ct[spine] = 700.0
    ax, ay, ar = AORTA
    aorta = ((x - ax) ** 2 + (y - ay) ** 2 <= ar**2) & (z >= 100) & (z <= 340)
    ct[aorta] = 150.0
    return ct


@pytest.fixture(scope="module")
def phantom():
    g = phantom_geom()
    ct = phantom_ct()
    props, work = propose_reference_regions(
        ct, g, pet_series_pseudonym="pet-x", ct_series_pseudonym="ct-x"
    )
    return g, ct, props, work


def test_phantom_liver_proposal_inside_liver(phantom):
    _, _, props, _ = phantom
    p = props["LIVER"]
    assert p.status == "PROPOSED" and p.algorithm_version == ALGORITHM_VERSION
    assert p.method == "SPHERE_AT_SUPPLIED_CENTRE" and p.diameter_mm == 30.0
    (x0, x1), (y0, y1), (z0, z1) = LIVER_BOX
    x, y, z = p.centre_patient_mm
    # the whole 15 mm-radius sphere lies inside the liver block
    assert x0 + 15 <= x <= x1 - 15 and y0 + 15 <= y <= y1 - 15 and z0 + 15 <= z <= z1 - 15
    assert p.qc["ct_hu_mean"] == pytest.approx(60.0, abs=5)


def test_phantom_blood_pool_proposal_in_aorta(phantom):
    _, _, props, _ = phantom
    p = props["BLOOD_POOL"]
    assert p.status == "PROPOSED" and p.method == "CYLINDER_AT_SUPPLIED_CENTRE"
    assert (p.diameter_mm, p.length_mm) == (10.0, 20.0)
    x, y, z = p.centre_patient_mm
    assert np.hypot(x - AORTA[0], y - AORTA[1]) <= 4.5
    # within the 30-75 % lung band (lungs z 200-340)
    assert 242 <= z <= 305
    assert p.qc["ct_hu_mean"] == pytest.approx(150.0, abs=10)


def test_proposals_are_deterministic(phantom):
    g, ct, props, _ = phantom
    again, _ = propose_reference_regions(
        ct, g, pet_series_pseudonym="pet-x", ct_series_pseudonym="ct-x"
    )
    assert {r: p.sha256 for r, p in again.items()} == {r: p.sha256 for r, p in props.items()}
    other, _ = propose_reference_regions(
        ct, g, pet_series_pseudonym="pet-OTHER", ct_series_pseudonym="ct-x"
    )
    assert other["LIVER"].sha256 != props["LIVER"].sha256  # bound to the PET series


def test_no_lungs_not_found():
    g = phantom_geom()
    ct = phantom_ct()
    ct[ct == -800.0] = -100.0
    props, _ = propose_reference_regions(ct, g)
    assert {p.status for p in props.values()} == {"NOT_FOUND"}
    assert props["LIVER"].failure_reason == "lungs not found on CT"


def test_non_axial_ct_refused():
    g = phantom_geom().model_copy(update={"direction": (1, 0, 0, 0, 0, 1, 0, -1, 0)})
    props, work = propose_reference_regions(np.zeros(SHAPE), g)
    assert work is None and "non-axial" in props["BLOOD_POOL"].failure_reason


def test_qc_render(phantom):
    from voxeltrace.visualization.reference_qc import render_proposal_qc

    _, _, props, work = phantom
    png = render_proposal_qc(work, props["BLOOD_POOL"], title="phantom")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    with pytest.raises(ValueError):
        render_proposal_qc(work, ReferenceProposal(region="LIVER", status="NOT_FOUND"), title="x")
