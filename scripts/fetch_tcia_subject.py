#!/usr/bin/env python3
"""Download ONE subject (one study) from a public TCIA collection via the NBIA v4 REST API.

Safety bounds:
- requires an explicit PatientID; never lists or downloads a whole collection;
- refuses if the subject has more than one study unless --study is given;
- refuses if the total size exceeds --max-bytes (default 1 GB);
- downloads only the SeriesInstanceUIDs returned for that subject/study;
- refuses to overwrite an existing subject directory.

Writes series zips + extracted DICOM under OUT/<PatientID>/ and updates OUT/../manifest.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import httpx

API = "https://services.cancerimagingarchive.net/nbia-api/services/v4"
LICENSES = {
    "FDG-PET-CT-Lesions": {
        "license": "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)",
        "variant": "public defaced images served by the anonymous NBIA API",
        "data_citation": (
            "Gatidis, S., Kuestner, T. (2022). A whole-body FDG-PET/CT dataset with manually "
            "annotated tumor lesions (FDG-PET-CT-Lesions) (Version 2) [dataset]. The Cancer "
            "Imaging Archive. https://doi.org/10.7937/gkr0-xv29"
        ),
        "publication": (
            "Gatidis, S., Hepp, T., Früh, M., La Fougère, C., Nikolaou, K., Pfannenberg, C., "
            "Schölkopf, B., Küstner, T., Cyran, C., & Rubin, D. (2022). A whole-body FDG-PET/CT "
            "Dataset with manually annotated Tumor Lesions. Scientific Data 9(1). "
            "https://doi.org/10.1038/s41597-022-01718-3"
        ),
        "policy": "TCIA Data Usage Policy: no attempt to re-identify participants.",
    }
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--collection", required=True)
    ap.add_argument("--patient", required=True)
    ap.add_argument("--study", help="StudyInstanceUID (required if subject has >1 study)")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--max-bytes", type=int, default=1_000_000_000)
    ap.add_argument("--dry-run", action="store_true", help="list series and sizes only")
    args = ap.parse_args(argv)

    client = httpx.Client(timeout=httpx.Timeout(60.0, read=600.0), follow_redirects=True)
    series = client.get(
        f"{API}/getSeries", params={"Collection": args.collection, "PatientID": args.patient}
    )
    series.raise_for_status()
    rows = series.json()
    rows = [r for r in rows if r.get("PatientID") == args.patient]
    if not rows:
        print(f"no series for {args.patient} in {args.collection}", file=sys.stderr)
        return 2
    studies = sorted({r["StudyInstanceUID"] for r in rows})
    if args.study:
        rows = [r for r in rows if r["StudyInstanceUID"] == args.study]
    elif len(studies) > 1:
        print(f"subject has {len(studies)} studies; pass --study one of {studies}", file=sys.stderr)
        return 2
    total = sum(int(r.get("FileSize") or 0) for r in rows)
    for r in rows:
        print(
            f"{r['Modality']:4} {int(r.get('FileSize') or 0):>12,d} B "
            f"{r.get('ImageCount')} img  {r['SeriesInstanceUID']}  '{r.get('SeriesDescription')}'"
        )
    print(f"total {total:,d} bytes in {len(rows)} series, 1 study, 1 subject")
    if total > args.max_bytes:
        print(f"refusing: {total} > --max-bytes {args.max_bytes}", file=sys.stderr)
        return 3
    if args.dry_run:
        return 0

    subj_dir = args.out / args.patient
    if subj_dir.exists():
        print(f"refusing: {subj_dir} already exists", file=sys.stderr)
        return 4
    zip_dir = subj_dir / "_zips"
    zip_dir.mkdir(parents=True)
    (subj_dir / "nbia_series_metadata.json").write_text(json.dumps(rows, indent=2))

    entries = []
    for r in rows:
        uid = r["SeriesInstanceUID"]
        zpath = zip_dir / f"{r['Modality']}_{uid}.zip"
        with client.stream("GET", f"{API}/getImage", params={"SeriesInstanceUID": uid}) as resp:
            resp.raise_for_status()
            with zpath.open("wb") as fh:
                for chunk in resp.iter_bytes(1 << 20):
                    fh.write(chunk)
        dest = subj_dir / "dicom" / f"{r['Modality']}_{uid}"
        with zipfile.ZipFile(zpath) as zf:
            for name in zf.namelist():
                target = (dest / name).resolve()
                if not str(target).startswith(str(dest.resolve())):
                    raise RuntimeError(f"unsafe path in zip: {name}")
            zf.extractall(dest)
        files = [p for p in dest.rglob("*") if p.is_file()]
        entries.append(
            {
                "modality": r["Modality"],
                "series_instance_uid": uid,
                "series_description": r.get("SeriesDescription"),
                "study_instance_uid": r["StudyInstanceUID"],
                "nbia_image_count": r.get("ImageCount"),
                "nbia_file_size": r.get("FileSize"),
                "zip": str(zpath.relative_to(args.out.parent)),
                "zip_bytes": zpath.stat().st_size,
                "zip_sha256": sha256(zpath),
                "extracted_file_count": len(files),
                "extracted_bytes": sum(p.stat().st_size for p in files),
            }
        )
        print(f"  downloaded {r['Modality']}: {zpath.stat().st_size:,d} B, {len(files)} files")

    all_files = [p for p in subj_dir.rglob("*") if p.is_file()]
    record = {
        "collection": args.collection,
        "subject_id": args.patient,
        "study_instance_uids": sorted({e["study_instance_uid"] for e in entries}),
        "source": f"{API} (getSeries, getImage per SeriesInstanceUID)",
        "downloaded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "series": entries,
        "file_count_total": len(all_files),
        "bytes_total": sum(p.stat().st_size for p in all_files),
        "series_metadata_sha256": sha256(subj_dir / "nbia_series_metadata.json"),
        **LICENSES.get(args.collection, {"license": "UNKNOWN - check collection page"}),
    }
    manifest_path = args.out.parent / "manifest.json"
    manifest = (
        json.loads(manifest_path.read_text())
        if manifest_path.exists()
        else {
            "description": "VoxelTrace hackathon-local public data. NEVER commit or push.",
            "datasets": [],
        }
    )
    manifest["datasets"].append(record)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"manifest updated: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
