#!/usr/bin/env python3
"""Bounded download of EXACT, allow-listed ACRIN series from IDC's public bucket.

  fetch_acrin_series.py configs/acrin_longitudinal/allowlist.json [--plan-only]

Guards (any failure STOPS before or during download, nothing outside the list is fetched):
  * every allow-list entry belongs to an approved subject;
  * each series is fetched only from its own object prefix ``<crdc_series_uuid>/``; the
    listing must contain exactly ``expected_instances`` objects whose total size is within 5 %
    of ``expected_MB`` (checked for ALL series before the first byte of pixel data);
  * every downloaded file must parse as DICOM with the expected PatientID,
    StudyInstanceUID, SeriesInstanceUID and Modality, else it is deleted and the run stops.

Layout: ../data/acrin_longitudinal/<subject>/<timepoint>/<PET|CT>/<SOPInstanceUID>.dcm
Writes ../data/acrin_longitudinal/provenance_manifest.json (per-file sha256 and S3 ETag) and
prints the series-level manifest for configs/acrin_longitudinal/provenance_manifest.json.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

import pydicom

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "data" / "acrin_longitudinal"
NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310 - fixed https host
        return r.read()


def software_versions(ds) -> list[str] | None:
    v = ds.get("SoftwareVersions")
    if v is None:
        return None
    return [str(v)] if isinstance(v, str) else [str(x) for x in v]


def list_series(bucket: str, uuid: str) -> list[dict]:
    out, token = [], None
    while True:
        url = f"https://{bucket}.s3.amazonaws.com/?list-type=2&prefix={uuid}/"
        if token:
            url += f"&continuation-token={urllib.parse.quote(token)}"
        root = ET.fromstring(_get(url))
        for c in root.findall("s:Contents", NS):
            out.append(
                {
                    "key": c.find("s:Key", NS).text,
                    "size": int(c.find("s:Size", NS).text),
                    "etag": c.find("s:ETag", NS).text.strip('"'),
                }
            )
        t = root.find("s:NextContinuationToken", NS)
        if t is None:
            return out
        token = t.text


def main(argv: list[str]) -> int:
    allow = json.loads(Path(argv[1]).read_text())
    plan_only = "--plan-only" in argv
    approved = set(allow["approved_subjects"])
    plans = []
    for s in allow["series"]:
        if s["PatientID"] not in approved:
            print(f"STOP: {s['PatientID']} is not an approved subject", file=sys.stderr)
            return 2
        objs = list_series(s["aws_bucket"], s["crdc_series_uuid"])
        mb = sum(o["size"] for o in objs) / 1e6
        if any(not o["key"].startswith(f"{s['crdc_series_uuid']}/") for o in objs):
            print("STOP: listing escaped the series prefix", file=sys.stderr)
            return 2
        if len(objs) != s["expected_instances"] or abs(mb - s["expected_MB"]) > 0.05 * max(
            s["expected_MB"], 1
        ):
            print(
                f"STOP: {s['SeriesInstanceUID']}: {len(objs)} objects / {mb:.1f} MB, expected "
                f"{s['expected_instances']} / {s['expected_MB']:.1f} MB",
                file=sys.stderr,
            )
            return 2
        plans.append((s, objs, mb))
    total = sum(p[2] for p in plans)
    print(f"plan: {len(plans)} series, {sum(len(p[1]) for p in plans)} files, {total:.1f} MB")
    for s, objs, mb in plans:
        print(f"  {s['PatientID']} {s['timepoint']} {s['modality']} {len(objs)} files {mb:.1f} MB")
    if plan_only:
        return 0

    manifest = {"collection": "ACRIN-NSCLC-FDG-PET", "series": []}
    for s, objs, _mb in plans:
        d = DEST / s["PatientID"] / s["timepoint"] / s["modality"]
        d.mkdir(parents=True, exist_ok=True)
        files, meta = [], None
        started = datetime.now(UTC).isoformat(timespec="seconds")
        for o in objs:
            data = _get(f"https://{s['aws_bucket']}.s3.amazonaws.com/{o['key']}")
            ds = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True)
            ok = (
                ds.PatientID == s["PatientID"]
                and ds.StudyInstanceUID == s["StudyInstanceUID"]
                and ds.SeriesInstanceUID == s["SeriesInstanceUID"]
                and ds.Modality == ("PT" if s["modality"] == "PET" else "CT")
            )
            if not ok or len(data) != o["size"]:
                print(f"STOP: unexpected content in {o['key']}", file=sys.stderr)
                return 3
            target = d / f"{ds.SOPInstanceUID}.dcm"
            target.write_bytes(data)
            target.chmod(0o444)
            files.append(
                {
                    "file": target.name,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "s3_etag": o["etag"],
                }
            )
            meta = meta or {
                "Manufacturer": str(ds.get("Manufacturer", "")),
                "ManufacturerModelName": str(ds.get("ManufacturerModelName", "")),
                "SoftwareVersions": software_versions(ds),
            }
        files.sort(key=lambda f: f["file"])
        series_hash = hashlib.sha256("".join(f["sha256"] for f in files).encode()).hexdigest()
        manifest["series"].append(
            {
                **{
                    k: s[k]
                    for k in (
                        "collection",
                        "PatientID",
                        "timepoint",
                        "modality",
                        "StudyInstanceUID",
                        "SeriesInstanceUID",
                        "SeriesDescription",
                        "license",
                    )
                },
                **meta,
                "file_count": len(files),
                "bytes": sum(f["bytes"] for f in files),
                "download_source": f"s3://{s['aws_bucket']}/{s['crdc_series_uuid']}/ (IDC "
                "public bucket, HTTPS)",
                "download_started": started,
                "download_finished": datetime.now(UTC).isoformat(timespec="seconds"),
                "source_checksum": "S3 ETag per object (in data/ manifest)",
                "series_sha256": series_hash,
                "files": files,
            }
        )
        print(f"  fetched {s['PatientID']} {s['timepoint']} {s['modality']}: {len(files)} files")
    manifest["total_bytes"] = sum(x["bytes"] for x in manifest["series"])
    (DEST / "provenance_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"total bytes: {manifest['total_bytes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
