#!/usr/bin/env python3
"""Metadata-only census of ACRIN-NSCLC-FDG-PET (no image volumes are downloaded).

Run with the isolated census venv (``../tmp/census-venv``: idc-index + pydicom).

1. Series-level metadata from the IDC index (idc-index): subject, study, series, modality,
   dates (de-identified, shifted), manufacturer, model, instance count, size.
2. For every PT series: the HEADER of ONE instance, read by an HTTP byte-range request
   (first 16 KB, extended to at most 64 KB if the header is longer) from IDC's public
   bucket, parsed with pydicom ``stop_before_pixels``. Raw bytes are never stored; only
   the parsed attributes listed in FIELDS are kept.

Outputs (../data/census/acrin_nsclc_fdg_pet/): series_index.csv, pet_headers.jsonl (resumable).
"""

from __future__ import annotations

import io
import json
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import pydicom
from idc_index import index

OUT = Path(__file__).resolve().parents[2] / "data" / "census" / "acrin_nsclc_fdg_pet"
FIELDS = (
    "Manufacturer",
    "ManufacturerModelName",
    "SoftwareVersions",
    "StationName",
    "InstitutionName",
    "Units",
    "DecayCorrection",
    "CorrectedImage",
    "AttenuationCorrectionMethod",
    "ScatterCorrectionMethod",
    "ReconstructionMethod",
    "ConvolutionKernel",
    "ImageType",
    "SeriesType",
    "Rows",
    "Columns",
    "PixelSpacing",
    "SliceThickness",
    "NumberOfSlices",
    "SeriesTime",
    "AcquisitionTime",
    "PatientWeight",
    "PatientSize",
    "PatientSex",
    "PatientIdentityRemoved",
    "DeidentificationMethod",
    "FrameOfReferenceUID",
    "SeriesDescription",
    "DecayFactor",
    "DoseCalibrationFactor",
    "ActualFrameDuration",
)
RP_FIELDS = (
    "Radiopharmaceutical",
    "RadionuclideTotalDose",
    "RadionuclideHalfLife",
    "RadiopharmaceuticalStartTime",
    "RadiopharmaceuticalStartDateTime",
)


def _get(url: str, rng: str | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"Range": f"bytes={rng}"} if rng else {})
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 - fixed https host
        return r.read()


def first_key(bucket: str, uuid: str) -> str:
    xml = _get(f"https://{bucket}.s3.amazonaws.com/?list-type=2&prefix={uuid}/&max-keys=1")
    ns = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
    return ET.fromstring(xml).find("s:Contents/s:Key", ns).text  # type: ignore[union-attr]


def header(bucket: str, key: str) -> tuple[dict, int]:
    for size in (16384, 65536):
        data = _get(f"https://{bucket}.s3.amazonaws.com/{key}", f"0-{size - 1}")
        try:
            ds = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True)
            _ = [getattr(ds, f, None) for f in FIELDS]  # force full parse of the header
        except Exception:  # noqa: BLE001 - truncated header: retry with a larger range
            continue
        out = {f: _jsonable(ds.get(f)) for f in FIELDS}
        rp = ds.get("RadiopharmaceuticalInformationSequence")
        item = rp[0] if rp else None
        for f in RP_FIELDS:
            out[f] = _jsonable(item.get(f)) if item is not None else None
        out["private_groups"] = sorted({f"{e.tag.group:04X}" for e in ds if e.tag.is_private})
        out["private_creators"] = sorted(
            {str(e.value) for e in ds if e.tag.is_private and e.tag.element < 0x100}
        )
        return out, len(data)
    raise RuntimeError("header longer than 64 KB")


def _jsonable(v):
    if v is None:
        return None
    if isinstance(v, pydicom.multival.MultiValue | list | tuple):
        return [_jsonable(x) for x in v]
    if isinstance(v, int | float | str):
        return v
    return str(v)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    df = index.IDCClient().index
    a = df[df.collection_id == "acrin_nsclc_fdg_pet"].copy()
    cols = [
        "PatientID", "StudyInstanceUID", "SeriesInstanceUID", "Modality", "StudyDate",
        "SeriesDate", "StudyDescription", "SeriesDescription", "Manufacturer",
        "ManufacturerModelName", "instanceCount", "series_size_MB", "sop_class_name",
        "aws_bucket", "crdc_series_uuid", "license_short_name",
    ]  # fmt: skip
    a[cols].sort_values(["PatientID", "StudyDate", "Modality"]).to_csv(
        OUT / "series_index.csv", index=False
    )
    done_path = OUT / "pet_headers.jsonl"
    done = set()
    if done_path.exists():
        done = {json.loads(x)["SeriesInstanceUID"] for x in done_path.read_text().splitlines()}
    pts = a[a.Modality == "PT"]
    n_bytes = 0
    with done_path.open("a") as fh:
        for _, s in pts.iterrows():
            if s.SeriesInstanceUID in done:
                continue
            rec = {"SeriesInstanceUID": s.SeriesInstanceUID, "PatientID": s.PatientID}
            try:
                key = first_key(s.aws_bucket, s.crdc_series_uuid)
                h, nb = header(s.aws_bucket, key)
                rec.update(h, header_bytes_read=nb, status="OK")
                n_bytes += nb
            except Exception as exc:  # noqa: BLE001 - record and continue
                rec.update(status="ERROR", error=f"{type(exc).__name__}: {exc}")
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            time.sleep(0.05)
    print(f"PT series: {len(pts)}; header bytes read this run: {n_bytes / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
