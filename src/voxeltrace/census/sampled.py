"""Census v2: predict VoxelTrace outcomes from a SAMPLE of slice headers (no pixel data).

The prediction runs VoxelTrace's own unchanged code on the sampled headers:
  * the strict SUVbw validator (``validate_suv_eligibility``, incl. the DecayFactor check),
  * the protocol evidence extractors (scanner / acquisition / reconstruction / corrections),
  * the trial pair rules (``assess_pair``) for QIBA / EANM / PERCIST.

``sampled_header_audit`` mirrors ``quant.suv.audit_pet_headers`` exactly but takes header
datasets instead of a discovered series (the frozen SUV module is not modified; a test asserts
the two produce identical audits). Limitations: only the sampled slices are checked; a defect
confined to unsampled slices can be missed. Sorting is by ImagePositionPatient z.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydicom.dataset import Dataset

from voxeltrace.evidence.acquisition import extract_acquisition
from voxeltrace.evidence.corrections import extract_corrections
from voxeltrace.evidence.protocol import ProtocolEvidence
from voxeltrace.evidence.reconstruction import extract_reconstruction
from voxeltrace.evidence.scanner import extract_scanner
from voxeltrace.quant import suv as _suv


def sampled_header_audit(series_uid: str, headers: Sequence[Dataset]) -> _suv.PETHeaderAudit:
    """Same construction as ``audit_pet_headers`` on the given headers (sorted by z)."""
    hs = sorted(headers, key=_z)
    fields = {}
    for name, tag, unit in _suv._CONSTANT_FIELDS + _suv._PER_SLICE_FIELDS:
        fields[name] = _suv._field(name, tag, unit, [_suv._raw(_suv._get(h, name)) for h in hs])
    for name, tag, unit in _suv._RP_FIELDS:
        vals = []
        for h in hs:
            item, _ = _suv._rp_item(h)
            vals.append(_suv._raw(_suv._get(item, name)) if item is not None else None)
        fields[name] = _suv._field(name, tag, unit, vals)
    fields["RadiopharmaceuticalInformationSequence.items"] = _suv._field(
        "RadiopharmaceuticalInformationSequence.items",
        "(0054,0016)",
        None,
        [str(_suv._rp_item(h)[1]) for h in hs],
    )
    codes = []
    for h in hs:
        item, _ = _suv._rp_item(h)
        seq = _suv._get(item, "RadionuclideCodeSequence") if item is not None else None
        codes.append(
            f"{_suv._str(_suv._get(seq[0], 'CodeValue'))}|"
            f"{_suv._str(_suv._get(seq[0], 'CodeMeaning'))}"
            if seq
            else None
        )
    fields["RadionuclideCodeSequence"] = _suv._field(
        "RadionuclideCodeSequence", "(0054,0300)", None, codes
    )
    return _suv.PETHeaderAudit(series_uid, list(hs), fields)


def _z(h: Dataset) -> float:
    ipp = h.get("ImagePositionPatient")
    return float(ipp[2]) if ipp is not None else 0.0


def predict_pet(series_uid: str, headers: Sequence[Dataset]) -> dict[str, Any]:
    """Run the strict validator + protocol extractors on sampled headers."""
    audit = sampled_header_audit(series_uid, headers)
    validation, inputs = _suv.validate_suv_eligibility(audit)
    hs = audit.headers
    protocol = ProtocolEvidence(
        series_uid=series_uid,
        scanner=extract_scanner(series_uid, hs),
        acquisition=extract_acquisition(series_uid, hs, None, inputs, validation),
        reconstruction=extract_reconstruction(series_uid, hs, None),
        corrections=extract_corrections(series_uid, hs),
    )
    acq_times = sorted({str(h.get("AcquisitionTime")) for h in hs})
    frts = sorted({str(h.get("FrameReferenceTime")) for h in hs})
    dfs = sorted({str(h.get("DecayFactor")) for h in hs})
    return {
        "n_sampled": len(hs),
        "suv_eligible": validation.eligible,
        "refusal_codes": [r.code for r in validation.reasons],
        "warning_codes": [w.code for w in validation.warnings],
        "inputs": inputs,
        "validation": validation,
        "protocol": protocol,
        "multi_bed_detected": len(acq_times) > 1 or len(frts) > 1,
        "distinct_acquisition_times": len(acq_times),
        "distinct_frame_reference_times": len(frts),
        "distinct_decay_factors": len(dfs),
        "frt_zero_with_decay_factor": all(f in ("0", "0.0") for f in frts)
        and any(d not in ("1", "1.0", "None") for d in dfs),
        "height_present": bool(hs[0].get("PatientSize")),
        "weight_present": bool(hs[0].get("PatientWeight")),
        "derived": "DERIVED" in [str(x) for x in (hs[0].get("ImageType") or [])],
    }
