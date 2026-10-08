#!/usr/bin/env python3
"""Read-only inventory of ALL PET header elements (standard + private) for a real pair and a
baseline/follow-up diff. Nothing is decoded or interpreted here.

  inventory_recon_metadata.py <subject> [--out-name acrin_longitudinal_168]

Writes ../outputs/<out-name>/recon_inventory.json:
  standard[keyword] = {baseline: summary, followup: summary, class, recon_relevant}
  private[(group,creator,element)] = {vr, length, preview|sha256, class}
Classes: IDENTICAL, DIFFERENT, MISSING_BOTH, MISSING_BASELINE, MISSING_FOLLOWUP,
AMBIGUOUS (values vary across slices), PRIVATE_UNSUPPORTED.
Identifying attributes and UIDs are never printed: they are reduced to a sha256 prefix.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import pydicom

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "acrin_longitudinal"

RECON_RELEVANT = {
    "SeriesDescription", "ProtocolName", "StudyDescription", "ImageComments",
    "DerivationDescription", "SeriesType", "NumberOfIterations", "NumberOfSubsets",
    "ReconstructionMethod", "ReconstructionDiameter", "ConvolutionKernel", "SliceThickness",
    "PixelSpacing", "Rows", "Columns", "ImageType", "CorrectedImage", "SoftwareVersions",
    "Manufacturer", "ManufacturerModelName", "ReconstructionAlgorithmSequence",
    "ReconstructionType", "ReconstructionTargetCenterPatient", "FilterType",
    "AxialAcceptance", "AxialMash", "TransverseMash", "CollimatorType", "CountsSource",
    "RandomsCorrectionMethod", "AttenuationCorrectionMethod", "ScatterCorrectionMethod",
    "DecayCorrection", "Units", "RealWorldValueMappingSequence", "SpacingBetweenSlices",
    "SliceSensitivityFactor", "ScatterFractionFactor", "DeadTimeFactor",
    "DoseCalibrationFactor", "ActualFrameDuration", "FrameReferenceTime", "DecayFactor",
    "AcquisitionStartCondition", "AcquisitionTerminationCondition", "GantryDetectorTilt",
    "TypeOfDetectorMotion", "EnergyWindowRangeSequence", "SecondaryCaptureDeviceManufacturer",
    "ConversionType", "SOPClassUID", "BurnedInAnnotation", "LossyImageCompression",
}  # fmt: skip
IDENTIFYING = {
    "PatientName", "PatientID", "OtherPatientIDs", "OtherPatientIDsSequence",
    "PatientBirthDate", "InstitutionName", "InstitutionAddress", "StationName",
    "ReferringPhysicianName", "OperatorsName", "PerformingPhysicianName", "AccessionNumber",
    "DeviceSerialNumber", "InstitutionalDepartmentName", "PhysiciansOfRecord",
    "RequestingPhysician", "StudyID",
}  # fmt: skip


def _hash(v) -> str:
    return "sha256:" + hashlib.sha256(str(v).encode()).hexdigest()[:16]


def _show(kw: str, v) -> str:
    if kw in IDENTIFYING or kw.endswith("UID") or kw.endswith("UIDs"):
        return _hash(v)
    s = str(v)
    return s if len(s) <= 120 else s[:117] + "..."


def summarise(headers, kw: str):
    vals = []
    for h in headers:
        if kw not in h:
            vals.append(None)
            continue
        el = h[kw]
        vals.append(_show(kw, el.value) if el.VR != "SQ" else f"SQ[{len(el.value)}]")
    present = [v for v in vals if v is not None]
    distinct = sorted(set(present))
    return {
        "present_slices": len(present),
        "slices": len(vals),
        "n_distinct": len(distinct),
        "values": distinct[:5],
    }


def classify(b, f) -> str:
    if b["present_slices"] == 0 and f["present_slices"] == 0:
        return "MISSING_BOTH"
    if b["present_slices"] == 0:
        return "MISSING_BASELINE"
    if f["present_slices"] == 0:
        return "MISSING_FOLLOWUP"
    if b["n_distinct"] > 1 or f["n_distinct"] > 1:
        return "AMBIGUOUS" if b["values"] != f["values"] else "IDENTICAL"
    return "IDENTICAL" if b["values"] == f["values"] else "DIFFERENT"


def private_blocks(headers):
    """{(group, creator, element_offset): {vr, lengths, digest set, preview}}."""
    out: dict[str, dict] = {}
    for h in headers:
        creators = {}
        for e in h:
            if e.tag.is_private and e.tag.element < 0x100:
                creators[(e.tag.group, e.tag.element)] = str(e.value)
        for e in h:
            if not e.tag.is_private or e.tag.element < 0x100:
                continue
            block = e.tag.element >> 8
            creator = creators.get((e.tag.group, block), "UNKNOWN_CREATOR")
            key = f"({e.tag.group:04X},xx{e.tag.element & 0xFF:02X}) {creator}"
            raw = e.value if isinstance(e.value, bytes) else str(e.value).encode()
            rec = out.setdefault(
                key, {"vr": e.VR, "lengths": set(), "digests": set(), "previews": set()}
            )
            rec["lengths"].add(len(raw))
            rec["digests"].add(hashlib.sha256(raw).hexdigest()[:16])
            txt = str(e.value)
            if e.VR in ("LO", "SH", "CS", "DS", "IS", "UL", "US", "SL", "SS", "FL", "FD") and (
                len(txt) <= 40
            ):
                rec["previews"].add(txt)
    return {
        k: {
            "vr": v["vr"],
            "lengths": sorted(v["lengths"]),
            "n_distinct_values": len(v["digests"]),
            "digests": sorted(v["digests"])[:3],
            "preview": sorted(v["previews"])[:3] if v["previews"] else None,
        }
        for k, v in out.items()
    }


def main(argv: list[str]) -> int:
    subject = argv[1]
    out_name = (
        argv[argv.index("--out-name") + 1] if "--out-name" in argv else "acrin_longitudinal_168"
    )
    hs = {
        tp: [
            pydicom.dcmread(f, stop_before_pixels=True)
            for f in sorted((DATA / subject / tp / "PET").glob("*.dcm"))
        ]
        for tp in ("baseline", "followup")
    }
    keywords = set()
    for tp in hs:
        for h in hs[tp]:
            keywords |= {e.keyword for e in h if e.keyword and not e.tag.is_private}
    keywords |= RECON_RELEVANT
    std = {}
    for kw in sorted(keywords):
        b, f = summarise(hs["baseline"], kw), summarise(hs["followup"], kw)
        std[kw] = {
            "baseline": b,
            "followup": f,
            "class": classify(b, f),
            "recon_relevant": kw in RECON_RELEVANT,
            "redacted": kw in IDENTIFYING or kw.endswith("UID"),
        }
    pb, pf = private_blocks(hs["baseline"]), private_blocks(hs["followup"])
    priv = {}
    for k in sorted(set(pb) | set(pf)):
        b, f = pb.get(k), pf.get(k)
        if b and f:
            cls = (
                "PRIVATE_UNSUPPORTED (IDENTICAL bytes)"
                if b["digests"] == f["digests"]
                else "PRIVATE_UNSUPPORTED (DIFFERENT bytes)"
            )
        else:
            cls = (
                "PRIVATE_UNSUPPORTED (MISSING_BASELINE)"
                if not b
                else "PRIVATE_UNSUPPORTED (MISSING_FOLLOWUP)"
            )
        priv[k] = {"baseline": b, "followup": f, "class": cls}
    out = {
        "subject": subject,
        "slices": {tp: len(v) for tp, v in hs.items()},
        "standard": std,
        "private": priv,
        "summary": {
            "standard_classes": dict(_count(v["class"] for v in std.values())),
            "recon_relevant_classes": dict(
                _count(v["class"] for v in std.values() if v["recon_relevant"])
            ),
            "private_elements": len(priv),
        },
    }
    p = ROOT / "outputs" / out_name / "recon_inventory.json"
    p.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out["summary"], indent=2))
    for kw, v in std.items():
        if v["recon_relevant"]:
            print(
                f"{kw:36} {v['class']:17} B:{v['baseline']['present_slices']}/"
                f"{v['baseline']['slices']} {v['baseline']['values'][:2]}  F:"
                f"{v['followup']['present_slices']} {v['followup']['values'][:2]}"
            )
    print("--- private")
    for k, v in priv.items():
        b, f = v["baseline"] or {}, v["followup"] or {}
        print(
            f"{k:48} {v['class']:40} VR {b.get('vr') or f.get('vr')} len "
            f"{b.get('lengths')}/{f.get('lengths')} preview {b.get('preview')}/{f.get('preview')}"
        )
    return 0


def _count(it):
    d: dict[str, int] = defaultdict(int)
    for x in it:
        d[x] += 1
    return d


if __name__ == "__main__":
    sys.exit(main(sys.argv))
