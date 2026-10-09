"""Protocol fingerprint VT-PROTOCOL-FP-1, fingerprint comparison and site drift."""

from __future__ import annotations

import pytest
from pydicom.uid import generate_uid

from dicom_factory import write_image_series
from voxeltrace.evidence import extract_protocol
from voxeltrace.evidence.fingerprint import (
    FIELDS,
    build_fingerprint,
    compare_protocol_fingerprints,
    identity_view,
)
from voxeltrace.ingest import discover_dicom
from voxeltrace.quant.suv import audit_pet_headers, validate_suv_eligibility
from voxeltrace.rules.common import reconstruction_identity
from voxeltrace.rules.voxeltrace_rules import VT_RECON
from voxeltrace.trial.drift import ScanRecord, detect_drift
from voxeltrace.trial.schema import PairContext, ScanPair, ScanTimepoint

RECON = {
    "ReconstructionMethod": "PSF+TOF 2i21s",
    "ConvolutionKernel": "XYZ Gauss2.00",
    "Manufacturer": "SIEMENS",
    "ManufacturerModelName": "Biograph128_mCT",
    "SoftwareVersions": "VG60A",
    "CorrectedImage": ["NORM", "DTIM", "ATTN", "SCAT", "DECY", "RAN"],
}


def proto(tmp_path, name, drop=(), rp=None, **ov):
    write_image_series(tmp_path / name, modality="PT", study_uid=generate_uid(),
                       pet_overrides={**RECON, **ov}, drop=drop, rp_overrides=rp)  # fmt: skip
    (s,) = discover_dicom(tmp_path / name).series
    val, inputs = validate_suv_eligibility(audit_pet_headers(s))
    return extract_protocol(s, inputs, val)


def test_every_field_serialized_and_hash_deterministic(tmp_path):
    p = proto(tmp_path, "a", drop=("ConvolutionKernel",))
    fp, fp2 = build_fingerprint(p), build_fingerprint(p)
    assert list(fp.fields) == list(FIELDS)
    assert (
        fp.fields["filter_kernel"].status == "MISSING"
        and fp.fields["filter_kernel"].trust == "NONE"
    )
    assert '"filter_kernel"' in fp.canonical(protocol_only=True)  # missing never dropped
    assert fp.protocol_fingerprint_sha256 == fp2.protocol_fingerprint_sha256
    assert len(fp.protocol_fingerprint_sha256) == 64
    assert fp.fields["iterations"].trust == "LEVEL_D"  # parsed from free text
    assert fp.fields["scanner_model"].trust == "LEVEL_A"


def test_protocol_hash_ignores_dose_scan_hash_does_not(tmp_path):
    a = build_fingerprint(proto(tmp_path, "a"))
    b = build_fingerprint(proto(tmp_path, "b", rp={"RadionuclideTotalDose": "250000000"}))
    assert a.protocol_fingerprint_sha256 == b.protocol_fingerprint_sha256
    assert a.scan_fingerprint_sha256 != b.scan_fingerprint_sha256


def test_compare_identical_with_harmonization(tmp_path):
    p = proto(tmp_path, "a")
    c = compare_protocol_fingerprints(build_fingerprint(p, harmonization="EARL1"),
                                      build_fingerprint(p, harmonization="EARL1"))  # fmt: skip
    assert c.result in ("IDENTICAL", "COMPATIBLE_WITH_WARNINGS")
    assert not c.blocking_different and not c.blocking_unknown
    c2 = compare_protocol_fingerprints(build_fingerprint(p), build_fingerprint(p))
    assert "harmonization" in c2.warnings  # never encoded -> visible warning, not silent


def test_reconstruction_change_is_different_with_rule_impact(tmp_path):
    a = build_fingerprint(proto(tmp_path, "a"))
    b = build_fingerprint(proto(tmp_path, "b", ReconstructionMethod="PSF+TOF 3i21s"))
    c = compare_protocol_fingerprints(a, b)
    assert c.result == "DIFFERENT" and "iterations" in c.blocking_different
    d = next(x for x in c.differences if x.field == "iterations")
    assert d.baseline == 2 and d.followup == 3 and "VT-PROTOCOL-IDENTITY" in d.rule_impact
    assert d.quantitative_relevance == "HIGH" and d.trust == "LEVEL_D"


@pytest.mark.parametrize(
    ("b_kw", "f_kw"),
    [
        ({}, {}),
        ({}, {"ReconstructionMethod": "PSF+TOF 3i21s"}),
        ({}, {"ConvolutionKernel": "XYZ Gauss4.00"}),
        ({"drop": ("ReconstructionMethod",)}, {"drop": ("ReconstructionMethod",)}),
        ({}, {"drop": ("ConvolutionKernel",)}),
        ({}, {"ManufacturerModelName": "Biograph64_mCT"}),
        ({}, {"Units": "CNTS"}),
        ({"drop": ("CorrectedImage",)}, {}),
    ],
)
def test_identity_view_agrees_with_rule(tmp_path, b_kw, f_kw):
    pa, pb = proto(tmp_path, "a", **b_kw), proto(tmp_path, "b", **f_kw)
    ctx = PairContext(
        pair=ScanPair(subject_id="s", baseline="b", followup="f"),
        baseline=ScanTimepoint(subject_id="s", timepoint="b", protocol=pa),
        followup=ScanTimepoint(subject_id="s", timepoint="f", protocol=pb),
    )
    c = compare_protocol_fingerprints(build_fingerprint(pa), build_fingerprint(pb))
    assert identity_view(c) == reconstruction_identity(VT_RECON, ctx).status


def _rec(fp, site="A", subj="S1", tp="b", date="2020-01-01"):
    return ScanRecord(site=site, subject=subj, timepoint=tp, scan_pseudonym=f"{subj}-{tp}",
                      date=date, fingerprint=fp)  # fmt: skip


def test_drift_events_cite_evidence(tmp_path):
    a = build_fingerprint(proto(tmp_path, "a"))
    b = build_fingerprint(proto(tmp_path, "b", SoftwareVersions="VG70A"))
    c = build_fingerprint(
        proto(tmp_path, "c", SoftwareVersions="VG70A", drop=("ConvolutionKernel",))
    )
    rep = detect_drift([_rec(c, subj="S3", date="2021-01-01"), _rec(a, date="2020-01-01"),
                        _rec(b, subj="S2", date="2020-06-01")])  # fmt: skip
    ev = {e.event: e for e in rep.events}
    sw = ev["SOFTWARE_CHANGE"]
    assert sw.previous_value == ["VG60A"] and sw.new_value == ["VG70A"]
    assert sw.previous_date == "2020-01-01" and sw.new_date == "2020-06-01"
    unk = ev["UNKNOWN_PROTOCOL_DRIFT"]
    assert unk.field == "filter_kernel" and "PRESENT -> MISSING" in unk.note
    (s,) = rep.sites
    assert (
        s.scans == 3 and s.events["SOFTWARE_CHANGE"] == 1 and s.distinct_protocol_fingerprints == 3
    )


def test_no_drift_for_identical_protocols_and_sites_separate(tmp_path):
    a = build_fingerprint(proto(tmp_path, "a"))
    b = build_fingerprint(proto(tmp_path, "b", SoftwareVersions="VG70A"))
    rep = detect_drift([_rec(a, site="A"), _rec(a, site="A", subj="S2", date="2020-02-01"),
                        _rec(b, site="B")])  # fmt: skip
    assert rep.events == [] and len(rep.sites) == 2


def test_uptake_outlier_is_heuristic(tmp_path):
    fps = [build_fingerprint(proto(tmp_path, f"u{i}")) for i in range(3)]  # 60 min uptake
    inj = {
        "RadiopharmaceuticalStartTime": "084500",
        "RadiopharmaceuticalStartDateTime": "20200101084500",
    }
    far = build_fingerprint(proto(tmp_path, "far", rp=inj))  # 90 min uptake
    recs = [_rec(f, subj=f"S{i}", date=f"2020-0{i + 1}-01") for i, f in enumerate(fps)]
    recs.append(_rec(far, subj="SX", date="2020-09-01"))
    rep = detect_drift(recs)
    out = [e for e in rep.events if e.event == "UPTAKE_OUTLIER"]
    assert far.fields["uptake_interval_s"].value == 5400.0
    assert len(out) == 1 and out[0].heuristic and out[0].new_scan == "SX-b"
    assert out[0].previous_value == 60.0 and out[0].new_value == 90.0
