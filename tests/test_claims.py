import pydicom
import pytest

from dicom_factory import build_pet_ct_seg_case
from voxeltrace.evidence import (
    claim_diagnosis,
    claim_image_noise,
    claim_protocol_fact,
    claim_quantity,
    claim_treatment_response,
    claim_uptake_change,
    compare_protocols,
    default_case_claims,
)
from voxeltrace.evidence.outputs import protocol_for_run
from voxeltrace.ingest import build_case
from voxeltrace.quant.evidence import quantify_case


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    root = tmp_path_factory.mktemp("claims") / "case"
    build_pet_ct_seg_case(root)
    for f in (root / "a_pet").glob("*.dcm"):  # complete protocol metadata for comparability
        ds = pydicom.dcmread(f)
        ds.ConvolutionKernel = "XYZ Gauss2.00"
        ds.ActualFrameDuration = "120000"
        ds.save_as(f)
    return quantify_case(build_case(root), subject="SYN")


def _with_suvmax(ev, value):
    ev2 = ev.model_copy(deep=True)
    ev2.measured.lesions[0].suv_max = value
    return ev2


def test_supported_quantitative_claim(run):
    les = run.evidence.measured.lesions[0]
    c = claim_quantity(run.evidence, "suv_max", f"{les.suv_max:.4f}", segment=1)
    assert c.status == "SUPPORTED"
    assert c.supporting_measurements[0].value == les.suv_max
    assert any(r.name == "Units" for r in c.supporting_protocol_evidence)


def test_mtv_claim_supported_and_precision_respected(run):
    les = run.evidence.measured.lesions[0]  # MTV 0.096 mL exactly
    assert claim_quantity(run.evidence, "mtv_ml", "0.096").status == "SUPPORTED"
    assert claim_quantity(run.evidence, "mtv_ml", "0.1").status == "SUPPORTED"  # ±0.05
    assert claim_quantity(run.evidence, "mtv_ml", "0.10").status == "SUPPORTED"  # 0.096→0.10
    assert claim_quantity(run.evidence, "mtv_ml", "0.09").status == "CONTRADICTED"  # ±0.005
    assert les.mtv_ml == pytest.approx(0.096)


def test_wrong_value_contradicted(run):
    c = claim_quantity(run.evidence, "suv_max", "25.0", segment=1)
    assert c.status == "CONTRADICTED" and c.conflicting_evidence


def test_unmeasured_value_not_established(run):
    c = claim_quantity(run.evidence, "suv_peak", "1.0", segment=1)  # grid < 1 cm³ sphere
    assert c.status == "NOT_ESTABLISHED"
    c2 = claim_quantity(run.evidence, "suv_max", "1.0", segment=7)
    assert c2.status == "NOT_ESTABLISHED"


def test_quantity_claim_not_established_when_suv_refused(run):
    ev = run.evidence.model_copy(deep=True)
    ev.measured.suv_status = "REFUSED"
    c = claim_quantity(ev, "suv_max", "1.0")
    assert c.status == "NOT_ESTABLISHED" and "SUV refused" in c.missing_evidence[0]


def test_unsupported_diagnostic_claim(run):
    c = claim_diagnosis("This lesion is lung cancer")
    assert c.status == "NOT_ESTABLISHED" and c.claim_type == "DIAGNOSIS"


def test_image_noise_not_established():
    assert claim_image_noise().status == "NOT_ESTABLISHED"


def test_protocol_fact_claims(run):
    p, _ = protocol_for_run(run)
    assert claim_protocol_fact(p, "attenuation_corrected").status == "SUPPORTED"
    assert claim_protocol_fact(p, "scatter_corrected").status == "CONTRADICTED"  # ATTN+DECY only
    assert claim_protocol_fact(p, "time_of_flight").status == "NOT_ESTABLISHED"  # unknown


def test_uptake_change_supported_when_comparable(run):
    p, _ = protocol_for_run(run)
    cmp = compare_protocols(p, p)
    assert cmp.category == "COMPARABLE"
    a = run.evidence
    b = _with_suvmax(a, a.measured.lesions[0].suv_max * 0.5)
    c = claim_uptake_change(a, b, cmp, same_target_confirmed=True)
    assert c.status == "SUPPORTED"
    pct = next(r for r in c.supporting_measurements if r.name == "percent_change")
    assert pct.value == pytest.approx(-50.0)


def test_uptake_change_contradicted_when_increased(run):
    p, _ = protocol_for_run(run)
    a = run.evidence
    b = _with_suvmax(a, a.measured.lesions[0].suv_max * 1.3)
    c = claim_uptake_change(a, b, compare_protocols(p, p), same_target_confirmed=True)
    assert c.status == "CONTRADICTED"


def test_uptake_change_not_established_without_comparability_or_target(run):
    p, _ = protocol_for_run(run)
    a = run.evidence
    b = _with_suvmax(a, a.measured.lesions[0].suv_max * 0.5)
    no_target = claim_uptake_change(a, b, compare_protocols(p, p), same_target_confirmed=False)
    assert no_target.status == "NOT_ESTABLISHED"
    pb = p.model_copy(deep=True)
    pb.reconstruction.convolution_kernel.value = ["XYZ Gauss5.00"]
    pb.reconstruction.convolution_kernel.status = "PRESENT"
    cmp = compare_protocols(p, pb)
    assert cmp.category == "NOT_COMPARABLE"
    c = claim_uptake_change(a, b, cmp, same_target_confirmed=True)
    assert c.status == "NOT_ESTABLISHED"
    assert any("NOT_COMPARABLE" in m for m in c.missing_evidence)
    assert claim_uptake_change(a, None, None).status == "NOT_ESTABLISHED"


def test_uptake_change_partially_supported_with_warnings(run):
    p, _ = protocol_for_run(run)
    pb = p.model_copy(deep=True)
    pb.scanner.software_versions.value = ["NEWER"]
    cmp = compare_protocols(p, pb)
    assert cmp.category == "COMPARABLE_WITH_WARNINGS"
    a = run.evidence
    b = _with_suvmax(a, a.measured.lesions[0].suv_max * 0.8)
    assert (
        claim_uptake_change(a, b, cmp, same_target_confirmed=True).status == "PARTIALLY_SUPPORTED"
    )


def test_treatment_response_remains_not_established_even_with_supported_change(run):
    p, _ = protocol_for_run(run)
    a = run.evidence
    b = _with_suvmax(a, a.measured.lesions[0].suv_max * 0.3)
    assert (
        claim_uptake_change(a, b, compare_protocols(p, p), same_target_confirmed=True).status
        == "SUPPORTED"
    )
    r = claim_treatment_response("Complete metabolic response")
    assert r.status == "NOT_ESTABLISHED" and r.claim_type == "TREATMENT_RESPONSE"


def test_default_claims_have_required_fields(run):
    p, _ = protocol_for_run(run)
    claims = default_case_claims(run.evidence, p)
    ids = [c.claim_id for c in claims]
    assert len(ids) == len(set(ids))
    by_id = {c.claim_id: c for c in claims}
    assert by_id["value-suv_max-seg1"].status == "SUPPORTED"
    assert by_id["value-suv_peak-seg1"].status == "NOT_ESTABLISHED"
    assert "has a value" in by_id["value-suv_peak-seg1"].statement
    for cid in ("response", "diagnosis", "image-noise", "change-suv_max-decrease"):
        assert by_id[cid].status == "NOT_ESTABLISHED"
    for c in claims:
        d = c.model_dump()
        for key in (
            "claim_id",
            "claim_type",
            "statement",
            "status",
            "supporting_measurements",
            "supporting_protocol_evidence",
            "conflicting_evidence",
            "missing_evidence",
            "assumptions",
            "limitations",
        ):
            assert key in d
