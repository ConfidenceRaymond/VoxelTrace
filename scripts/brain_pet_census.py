#!/usr/bin/env python3
"""Metadata-only Brain PET census of OpenNeuro PET datasets (no image download).

  brain_pet_census.py

Input: ../data/census/openneuro_pet/graphql_pet_datasets_2026-10-08.json (dataset list).
Per dataset, from the public openneuro.org S3 bucket (HTTPS), reads ONLY small text files:
dataset_description.json and up to 3 *_pet.json sidecars.
The object listing is capped (MAX_KEYS); files > 200 kB are skipped. Raw files are not stored;
only extracted fields are kept.

Writes ../data/census/openneuro_pet/brain_pet_census.json and docs/brain_pet_census.md.
Categories (from sidecar TracerName / title; tracer families only, no quantification):
BRAIN_FDG, AMYLOID, TAU, TSPO, SV2A_UCBJ, OTHER, plus flags DYNAMIC_KINETIC and PET_MR.
"""

from __future__ import annotations

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "census" / "openneuro_pet" / "graphql_pet_datasets_2026-10-08.json"
OUT = ROOT / "data" / "census" / "openneuro_pet" / "brain_pet_census.json"
BUCKET = "https://s3.amazonaws.com/openneuro.org"
NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
MAX_KEYS = 3000
MAX_BYTES = 200_000
FAMILIES = [
    ("BRAIN_FDG", r"fdg|fluorodeoxyglucose|glucose"),
    ("AMYLOID", r"florbetapir|florbetaben|flutemetamol|\bpib\b|pittsburgh|nav4694|amyloid|av-?45"),
    ("TAU", r"flortaucipir|av-?1451|mk-?6240|pi-?2620|\btau\b|pbb3|ro-?948"),
    ("TSPO", r"tspo|pbr28|pk11195|dpa-?714|ger-?0?22|sf51|fepbr|translocator"),
    ("SV2A_UCBJ", r"ucb-?j|synvest|sv2a|ucb-?h"),
]
SIDE_FIELDS = ("TracerName", "TracerRadionuclide", "ModeOfAdministration", "InjectedRadioactivity",
               "InjectedRadioactivityUnits", "TimeZero", "ScanStart", "InjectionStart", "FrameTimesStart",
               "FrameDuration", "ReconMethodName", "ReconMethodParameterLabels", "ReconMethodParameterValues",
               "ReconFilterType", "ReconFilterSize", "AttenuationCorrection", "Manufacturer",
               "ManufacturersModelName", "BodyPart", "PharmaceuticalName", "ImageDecayCorrected",
               "Units")  # fmt: skip


def _get(url: str, limit: int | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"Range": f"bytes=0-{limit - 1}"} if limit else {})
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 - fixed public host
        return r.read()


def keys(ds: str) -> list[tuple[str, int]]:
    out, token = [], None
    while len(out) < MAX_KEYS:
        url = f"{BUCKET}?list-type=2&prefix={ds}/&max-keys=1000"
        if token:
            url += "&continuation-token=" + urllib.parse.quote(token)
        root = ET.fromstring(_get(url))
        out += [
            (c.find("s:Key", NS).text, int(c.find("s:Size", NS).text))
            for c in root.findall("s:Contents", NS)
        ]
        t = root.find("s:NextContinuationToken", NS)
        if t is None:
            return out
        token = t.text
    return out


def family(text: str) -> str:
    t = text.casefold()
    for name, pat in FAMILIES:
        if re.search(pat, t):
            return name
    return "OTHER"


def census_one(node: dict) -> dict:
    ds = node["id"]
    snap = node.get("latestSnapshot") or {}
    title = ((snap.get("description") or {}).get("Name")) or ""
    summ = snap.get("summary") or {}
    rec = {"dataset": ds, "version": snap.get("tag"), "title": title, "modalities": summ.get("modalities"),
           "subjects": len(summ.get("subjects") or []), "sessions": len(summ.get("sessions") or []),
           "size_GB": round((summ.get("size") or 0) / 1e9, 2)}  # fmt: skip
    try:
        ks = keys(ds)
        rec["listing_truncated"] = len(ks) >= MAX_KEYS
        names = {k for k, _ in ks}
        try:
            dd = json.loads(_get(f"{BUCKET}/{ds}/dataset_description.json", MAX_BYTES))
            rec["license"] = dd.get("License")
            rec["bids_version"] = dd.get("BIDSVersion")
        except Exception:  # noqa: BLE001
            rec["license"] = None
        sides = [k for k, sz in ks if k.endswith("_pet.json") and sz <= MAX_BYTES][:3]
        rec["pet_sidecars_found_in_listing"] = sum(k.endswith("_pet.json") for k in names)
        rec["has_blood"] = any(re.search(r"_(recording-.*_)?blood\.(tsv|json)", k) for k in names)
        rec["has_anat_mri"] = any("/anat/" in k for k in names)
        rec["has_derivatives"] = any("/derivatives/" in k for k in names)
        rec["sidecars"] = []
        for k in sides:
            try:
                sc = json.loads(_get(f"{BUCKET}/{k}", MAX_BYTES))
                rec["sidecars"].append({f: sc.get(f) for f in SIDE_FIELDS if f in sc})
            except Exception as exc:  # noqa: BLE001
                rec["sidecars"].append({"error": type(exc).__name__})
    except Exception as exc:  # noqa: BLE001 - record, never guess
        rec["error"] = f"{type(exc).__name__}: {exc}"
    tracer_text = " ".join(str(s.get("TracerName", "")) for s in rec.get("sidecars", [])) or title
    rec["tracer_names"] = sorted(
        {str(s.get("TracerName")) for s in rec.get("sidecars", []) if s.get("TracerName")}
    )
    rec["category"] = family(tracer_text + " " + title)
    frames = [
        len(s.get("FrameDuration") or [])
        for s in rec.get("sidecars", [])
        if isinstance(s.get("FrameDuration"), list)
    ]
    rec["dynamic"] = (max(frames) > 1) if frames else None  # None = no sidecar read: UNKNOWN
    rec["frames_max"] = max(frames) if frames else None
    rec["pet_mr"] = bool(rec.get("has_anat_mri")) and "mri" in (rec.get("modalities") or [])
    rec["scanners"] = sorted(
        {
            f"{s.get('Manufacturer')} {s.get('ManufacturersModelName')}"
            for s in rec.get("sidecars", [])
            if s.get("Manufacturer")
        }
    )
    rec["preclinical_scanner"] = any(
        re.search(r"inveon|mediso|molecubes|beta-cube|lfer", x, re.I) for x in rec["scanners"]
    )
    rec["recon"] = sorted(
        {str(s.get("ReconMethodName")) for s in rec.get("sidecars", []) if s.get("ReconMethodName")}
    )
    rec["attenuation_correction"] = sorted(
        {
            str(s.get("AttenuationCorrection"))
            for s in rec.get("sidecars", [])
            if s.get("AttenuationCorrection")
        }
    )
    return rec


def main() -> int:
    import urllib.parse  # noqa: F401 - used in keys()

    nodes = [e["node"] for e in json.loads(SRC.read_text())["data"]["datasets"]["edges"]]
    recs = [census_one(n) for n in nodes]
    OUT.write_text(json.dumps(recs, indent=2, default=str) + "\n")
    print(
        json.dumps(
            [
                {
                    k: r.get(k)
                    for k in (
                        "dataset",
                        "category",
                        "dynamic",
                        "subjects",
                        "sessions",
                        "tracer_names",
                        "error",
                    )
                }
                for r in recs
            ],
            indent=1,
        )
    )
    return 0


TOP5 = [
    ("ds004856", "Dallas Lifespan Brain Study: amyloid (AV-45) and tau (AV-1451), human, 464 subjects, 3 sessions, GE Discovery MI; longitudinal static SUVR-type data"),
    ("ds006756", "[18F]MK6240 tau, human, 33 subjects, 2 sessions, HRRT, dynamic: tau tracer-specific rules and repeat sessions"),
    ("ds007561", "[11C]UCB-J SV2A, human, 20 subjects, Siemens Biograph Horizon, dynamic, with T1w MRI"),
    ("ds003382", "FDG functional PET on Siemens Biograph mMR (PET/MR), human, dynamic (90 frames), arterial blood: kinetic + PET/MR provenance"),
    ("ds005698", "[18F]PF-PDE4B test-retest, human, 25 subjects, 4 sessions, Siemens mCT, dynamic with blood: repeatability"),
]  # fmt: skip


def write_doc() -> int:
    recs = json.loads(OUT.read_text())
    from collections import Counter

    lines = ["# Brain PET metadata census (OpenNeuro; metadata only, 2026-10-09)", "",
             "Source: `scripts/brain_pet_census.py` -> `../data/census/openneuro_pet/brain_pet_census.json`. Read only dataset_description.json and <= 3 *_pet.json sidecars per dataset (listing capped at 3,000 keys); no image data. Categories from sidecar TracerName (else title). Planning input only: no brain rules exist.", "",
             f"Datasets: {len(recs)}; categories: {dict(Counter(r['category'] for r in recs))}; dynamic: {sum(r['dynamic'] is True for r in recs)}, static: {sum(r['dynamic'] is False for r in recs)}, UNKNOWN (no sidecar read): {sum(r['dynamic'] is None for r in recs)}; with blood data: {sum(bool(r.get('has_blood')) for r in recs)}; with anatomical MRI: {sum(bool(r.get('has_anat_mri')) for r in recs)}; preclinical scanners: {sum(r['preclinical_scanner'] for r in recs)}. Licence: CC0 except one 'not for public distribution (yet)'. All are BIDS/NIfTI: none is DICOM.", "",
             "| Dataset | Category | Tracer (sidecar) | Dynamic (max frames) | Subjects | Sessions | Scanner | Blood | Anat MRI | Preclinical | Size GB |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for r in recs:
        dyn = (
            "UNKNOWN"
            if r["dynamic"] is None
            else (f"yes ({r['frames_max']})" if r["dynamic"] else "no")
        )
        lines.append(
            f"| {r['dataset']} | {r['category']} | {', '.join(r['tracer_names']) or '-'} | {dyn} | {r['subjects']} | {r['sessions']} | {', '.join(r['scanners']) or '-'} | {'yes' if r.get('has_blood') else '-'} | {'yes' if r.get('has_anat_mri') else '-'} | {'yes' if r['preclinical_scanner'] else '-'} | {r['size_GB']} |"
        )
    lines += ["", "## Top 5 future datasets (for the THEN stage; not downloaded)", ""]
    lines += [f"{i}. **{d}**: {why}" for i, (d, why) in enumerate(TOP5, 1)]
    lines += [
        "",
        "Notes: tracer families are labels for planning only; amyloid/tau/TSPO/SV2A reference regions and kinetic models are tracer-specific and NOT implemented. Preclinical datasets (Inveon, Mediso, Molecubes) are out of scope for human trial audit.",
    ]
    (REPO / "docs" / "brain_pet_census.md").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    import sys
    import urllib.parse

    raise SystemExit(write_doc() if sys.argv[1:] == ["doc"] else main())
