from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

from voxeltrace.trial.anonymization import audit_anonymization
from voxeltrace.trial.reasons import CATALOG, reason_for_suv_refusal
from voxeltrace.vendors import parser_for


def _ds(
    manufacturer="SIEMENS",
    creator="SIEMENS MED PT",
    private="20200101100000.000000",
    codes=("113100", "113108"),
    **attrs,
):
    ds = Dataset()
    ds.Manufacturer = manufacturer
    ds.SeriesDate, ds.SeriesTime = "20200102", "100000"
    for k, v in attrs.items():
        setattr(ds, k, v)
    if creator is not None:
        ds.add_new(0x00710010, "LO", creator)
        ds.add_new(0x00711022, "DT", private)
    if codes:
        ds.PatientIdentityRemoved = "YES"
        items = []
        for c in codes:
            it = Dataset()
            it.CodeValue, it.CodingSchemeDesignator, it.CodeMeaning = c, "DCM", "x"
            items.append(it)
        ds.DeidentificationMethodCodeSequence = Sequence(items)
    return ds


def test_private_tag_read_only_with_matching_creator():
    ev = parser_for("SIEMENS").read(_ds())[0]
    assert ev.status == "SUPPORTED_READ_ONLY" and ev.value == "20200101100000.000000"
    assert "Conformance Statement" in ev.source


def test_private_tag_not_interpreted_with_wrong_creator():
    ev = parser_for("SIEMENS").read(_ds(creator="SOMEONE ELSE"))[0]
    assert ev.status == "CREATOR_MISMATCH" and ev.value is None
    ev2 = parser_for("SIEMENS").read(_ds(creator=None))[0]
    assert ev2.status == "NOT_PRESENT"


def test_unverified_private_field_reported_unsupported():
    ge = parser_for("GE MEDICAL SYSTEMS")
    statuses = {e.name: e.status for e in ge.read(Dataset())}
    assert statuses["admin_datetime"] == "UNSUPPORTED_PRIVATE_TAG"


def test_date_shift_between_private_and_standard_timing_detected():
    a = audit_anonymization([_ds(PatientSex="F", PatientSize="1.6", PatientWeight="60")])
    (t,) = a.timing_crosschecks
    assert t.code == "INCONSISTENT_METADATA" and "-86400" in t.detail and "date-shift" in t.detail


def test_absent_height_with_retention_option_is_probably_never_encoded():
    a = audit_anonymization([_ds(PatientSex="F", PatientWeight="60")])
    f = next(x for x in a.fields if x.field == "PatientSize")
    assert f.presence == "ABSENT" and f.reason.code == "NEVER_ENCODED"
    assert f.reason.confidence == "PROBABLE" and "E.3.7" in f.reason.evidence_basis


def test_absent_height_without_retention_option_is_unknown_or_stripped():
    a = audit_anonymization([_ds(codes=("113100",), PatientSex="F", PatientWeight="60")])
    f = next(x for x in a.fields if x.field == "PatientSize")
    assert f.reason.code == "UNKNOWN_OR_STRIPPED"


def test_stripped_only_with_explicit_marker():
    a = audit_anonymization([_ds(PatientSex="F", PatientWeight="60", DeviceSerialNumber="REMOVED")])
    f = next(x for x in a.fields if x.field == "DeviceSerialNumber")
    assert f.reason.code == "STRIPPED_BY_ANONYMIZATION" and f.reason.confidence == "CONFIRMED"
    a2 = audit_anonymization([_ds(PatientSex="F", PatientSize="", PatientWeight="60")])
    assert (
        next(x for x in a2.fields if x.field == "PatientSize").reason.code
        != "STRIPPED_BY_ANONYMIZATION"
    )


def test_reason_catalog_actionable():
    for _code, info in CATALOG.items():
        assert info.what and info.why_it_matters and info.remediation and info.site_can_fix
    assert reason_for_suv_refusal("INCONSISTENT_UNITS", "x").code == "INCONSISTENT_METADATA"
    assert reason_for_suv_refusal("SCAN_REFERENCE_AMBIGUOUS", "x").code == "AMBIGUOUS_TIMING"
    assert reason_for_suv_refusal("MISSING_PATIENTWEIGHT", "x").code == "MISSING_REQUIRED_TAG"
