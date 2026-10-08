#!/usr/bin/env python3
"""ACRIN-NSCLC-FDG-PET census v2 (metadata only; no image volumes; v1 files untouched).

For every AC-primary PET series of census v1:
  * the full object listing of the series (one request), then the headers of N_SAMPLE slices
    chosen deterministically (evenly spaced over the sorted object keys), each read by an HTTP
    byte range (16 KB, 64 KB if longer) and parsed with ``stop_before_pixels``;
  * VoxelTrace's own unchanged strict SUV validator, protocol extractors and pair rules are
    run on those headers (voxeltrace.census.sampled).
For every CT series (>1 instance) in the same studies: one header -> FrameOfReferenceUID.
Raw bytes are never stored.

Outputs: ../data/census/acrin_nsclc_fdg_pet_v2/{pet_series_v2.jsonl, ct_series_v2.jsonl,
pairs_v2.csv, census_v2_summary.json, validation_v1_v2_actual.csv}
"""

from __future__ import annotations

import csv
import io
import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pydicom

from voxeltrace.census.sampled import predict_pet
from voxeltrace.evidence.comparability import compare_protocols
from voxeltrace.rules.registry import assess_pair, get_ruleset
from voxeltrace.trial.schema import PairContext, ScanPair, ScanTimepoint

ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "data" / "census" / "acrin_nsclc_fdg_pet"
V2 = ROOT / "data" / "census" / "acrin_nsclc_fdg_pet_v2"
N_SAMPLE = 12
NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
RULESETS = ("qiba-fdg-1.14", "eanm-fdg-2.0", "percist-1.0")


def _get(url: str, rng: str | None = None) -> bytes:
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={rng}"} if rng else {})
            with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 - fixed https host
                return r.read()
        except Exception:  # noqa: BLE001 - transient network errors: retry
            time.sleep(2**attempt)
    raise RuntimeError(f"failed: {url}")


def keys(bucket: str, uuid: str) -> list[str]:
    out, token = [], None
    while True:
        url = f"https://{bucket}.s3.amazonaws.com/?list-type=2&prefix={uuid}/"
        if token:
            url += f"&continuation-token={urllib.parse.quote(token)}"
        root = ET.fromstring(_get(url))
        out += [c.find("s:Key", NS).text for c in root.findall("s:Contents", NS)]
        t = root.find("s:NextContinuationToken", NS)
        if t is None:
            return sorted(out)
        token = t.text


def header(bucket: str, key: str) -> pydicom.Dataset:
    for size in (16384, 65536, 262144):
        data = _get(f"https://{bucket}.s3.amazonaws.com/{key}", f"0-{size - 1}")
        try:
            ds = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True)
            _ = ds.get("ImagePositionPatient"), ds.get("DecayFactor"), ds.get("PatientSize")
            return ds
        except Exception:  # noqa: BLE001 - truncated header: retry larger
            continue
    raise RuntimeError("header > 256 KB")


def sample_idx(n: int, k: int) -> list[int]:
    if n <= k:
        return list(range(n))
    return sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})


def ev(f) -> dict:
    return {
        "value": f.value if not isinstance(f.value, tuple) else list(f.value),
        "status": f.status,
    }


def do_pet(row: dict) -> dict:
    rec = {"SeriesInstanceUID": row["SeriesInstanceUID"], "PatientID": row["PatientID"]}
    try:
        ks = keys(row["aws_bucket"], row["crdc_series_uuid"])
        hs = [header(row["aws_bucket"], ks[i]) for i in sample_idx(len(ks), N_SAMPLE)]
        p = predict_pet(row["SeriesInstanceUID"], hs)
        pr = p["protocol"]
        rec.update(
            status="OK",
            n_instances_listed=len(ks),
            n_sampled=p["n_sampled"],
            suv_eligible=p["suv_eligible"],
            refusal_codes=p["refusal_codes"],
            warning_codes=p["warning_codes"],
            uptake_s=p["inputs"].decay_interval_s,
            weight_kg=p["inputs"].patient_weight_kg,
            dose_bq=p["inputs"].radionuclide_total_dose_bq,
            height_present=p["height_present"],
            weight_present=p["weight_present"],
            derived=p["derived"],
            multi_bed_detected=p["multi_bed_detected"],
            distinct_acquisition_times=p["distinct_acquisition_times"],
            distinct_frame_reference_times=p["distinct_frame_reference_times"],
            frt_zero_with_decay_factor=p["frt_zero_with_decay_factor"],
            frame_of_reference=str(hs[0].get("FrameOfReferenceUID")),
            manufacturer=str(hs[0].get("Manufacturer")),
            model=str(hs[0].get("ManufacturerModelName")),
            tracer=ev(pr.acquisition.tracer),
            recon_description=ev(pr.reconstruction.reconstruction_method),
            iterations=ev(pr.reconstruction.iterations),
            subsets=ev(pr.reconstruction.subsets),
            software=ev(pr.scanner.software_versions),
            protocol_json=pr.model_dump_json(),
        )
    except Exception as exc:  # noqa: BLE001 - record, never guess
        rec.update(status="ERROR", error=f"{type(exc).__name__}: {exc}")
    return rec


def do_ct(row: dict) -> dict:
    rec = {
        "SeriesInstanceUID": row["SeriesInstanceUID"],
        "StudyInstanceUID": row["StudyInstanceUID"],
        "SeriesDescription": row["SeriesDescription"],
        "series_size_MB": float(row["series_size_MB"]),
    }
    try:
        k = keys(row["aws_bucket"], row["crdc_series_uuid"])
        ds = header(row["aws_bucket"], k[len(k) // 2])
        rec.update(
            status="OK",
            frame_of_reference=str(ds.get("FrameOfReferenceUID")),
            image_type=[str(x) for x in (ds.get("ImageType") or [])],
        )
    except Exception as exc:  # noqa: BLE001
        rec.update(status="ERROR", error=f"{type(exc).__name__}: {exc}")
    return rec


def run_jobs(fn, rows, path: Path) -> dict[str, dict]:
    done = {}
    if path.exists():
        done = {
            json.loads(x)["SeriesInstanceUID"]: json.loads(x) for x in path.read_text().splitlines()
        }
    todo = [r for r in rows if r["SeriesInstanceUID"] not in done]
    with path.open("a") as fh, ThreadPoolExecutor(8) as ex:
        for rec in ex.map(fn, todo):
            fh.write(json.dumps(rec, default=str) + "\n")
            fh.flush()
            done[rec["SeriesInstanceUID"]] = rec
    return done


def timepoint(rec: dict, pid: str, name: str) -> ScanTimepoint:
    from voxeltrace.evidence.protocol import ProtocolEvidence

    tp = ScanTimepoint(subject_id=pid, timepoint=name)
    if rec.get("status") != "OK":
        return tp
    tp.protocol = ProtocolEvidence.model_validate_json(rec["protocol_json"])
    tp.suv_status = "PASS" if rec["suv_eligible"] else "REFUSED"
    tp.suv_refusal_codes = rec["refusal_codes"]
    tp.uptake_s = rec["uptake_s"] if rec["suv_eligible"] else None
    tp.weight_kg = rec["weight_kg"]
    tp.injected_bq = rec["dose_bq"]
    return tp


def main() -> int:
    V2.mkdir(parents=True, exist_ok=True)
    idx = {r["SeriesInstanceUID"]: r for r in csv.DictReader((V1 / "series_index.csv").open())}
    v1risk = list(csv.DictReader((V1 / "pet_series_risk.csv").open()))
    ac = [idx[r["SeriesInstanceUID"]] for r in v1risk if r["ac_primary"] == "True"]
    studies = {r["StudyInstanceUID"] for r in ac}
    cts = [
        r
        for r in idx.values()
        if r["Modality"] == "CT"
        and r["StudyInstanceUID"] in studies
        and int(r["instanceCount"]) > 1
    ]
    print(f"AC PET series {len(ac)}; CT series in those studies {len(cts)}", flush=True)
    pet = run_jobs(do_pet, ac, V2 / "pet_series_v2.jsonl")
    ct = run_jobs(do_ct, cts, V2 / "ct_series_v2.jsonl")

    ct_by_study: dict[str, list[dict]] = defaultdict(list)
    for c in ct.values():
        ct_by_study[c["StudyInstanceUID"]].append(c)
    for s in pet.values():
        study = idx[s["SeriesInstanceUID"]]["StudyInstanceUID"]
        match = [
            c
            for c in ct_by_study.get(study, [])
            if c.get("status") == "OK"
            and c["frame_of_reference"] == s.get("frame_of_reference")
            and "DERIVED" not in c.get("image_type", [])
        ]
        s["ct_same_for"] = bool(match)
        s["ct_same_for_min_MB"] = min((c["series_size_MB"] for c in match), default=None)
        s["StudyInstanceUID"] = study
        s["StudyDate"] = idx[s["SeriesInstanceUID"]]["StudyDate"]
        s["pet_MB"] = float(idx[s["SeriesInstanceUID"]]["series_size_MB"])

    with (V2 / "pet_series_v2_enriched.jsonl").open("w") as fh:
        for s in pet.values():
            fh.write(
                json.dumps({k: v for k, v in s.items() if k != "protocol_json"}, default=str) + "\n"
            )

    def series_ok(s: dict) -> tuple:  # preference order within a study
        return (
            0 if s.get("suv_eligible") else 1,
            0 if s.get("ct_same_for") else 1,
            0 if s.get("height_present") else 1,
            s.get("pet_MB", 1e9),
        )

    best_by_study: dict[str, dict] = {}
    for s in pet.values():
        if s.get("status") != "OK":
            continue
        cur = best_by_study.get(s["StudyInstanceUID"])
        if cur is None or series_ok(s) < series_ok(cur):
            best_by_study[s["StudyInstanceUID"]] = s
    by_patient: dict[str, list[dict]] = defaultdict(list)
    for s in best_by_study.values():
        by_patient[s["PatientID"]].append(s)

    rulesets = {rs: get_ruleset(rs) for rs in RULESETS}
    pairs = []
    for pid, ss in sorted(by_patient.items()):
        ss = sorted(ss, key=lambda s: s["StudyDate"])
        if len(ss) < 2 or ss[0]["StudyDate"] == ss[1]["StudyDate"]:
            continue
        b, f = ss[0], ss[1]
        tb, tf = timepoint(b, pid, "baseline"), timepoint(f, pid, "followup")
        ctx = PairContext(
            pair=ScanPair(subject_id=pid, baseline="baseline", followup="followup"),
            baseline=tb,
            followup=tf,
        )
        cat = (
            compare_protocols(tb.protocol, tf.protocol).category
            if tb.protocol and tf.protocol
            else None
        )
        verdicts = {rs: assess_pair(r, ctx, cat) for rs, r in rulesets.items()}
        qiba = verdicts["qiba-fdg-1.14"]
        suv_both = bool(b.get("suv_eligible") and f.get("suv_eligible"))
        tracer_both = b["tracer"]["status"] == "PRESENT" and f["tracer"]["status"] == "PRESENT"
        height_both = bool(b.get("height_present") and f.get("height_present"))
        ct_both = bool(b.get("ct_same_for") and f.get("ct_same_for"))
        decided = qiba.verdict in ("ASSESSABLE", "ASSESSABLE_WITH_WARNINGS", "NOT_ASSESSABLE")
        if not suv_both or not decided:
            category = "LIKELY_INSUFFICIENT"
        elif height_both and ct_both and tracer_both:
            category = "HIGH_CONFIDENCE_ANALYZABLE"
        else:
            category = "ANALYZABLE_WITH_WARNINGS"
        mb = (
            b["pet_MB"]
            + f["pet_MB"]
            + (b["ct_same_for_min_MB"] or 0)
            + (f["ct_same_for_min_MB"] or 0)
        )
        blocking = sorted(
            {
                c.rule_id
                for c in qiba.checks
                if c.impact == "blocking" and c.status in ("FAIL", "UNKNOWN")
            }
        )
        pairs.append(
            {
                "PatientID": pid,
                "category": category,
                "vendor": vendor(b["manufacturer"]),
                "scanner_baseline": f"{b['manufacturer']} {b['model']}",
                "scanner_followup": f"{f['manufacturer']} {f['model']}",
                "interval_days": (
                    __import__("datetime").date.fromisoformat(f["StudyDate"])
                    - __import__("datetime").date.fromisoformat(b["StudyDate"])
                ).days,
                "suv_baseline": "PASS"
                if b.get("suv_eligible")
                else ";".join(b.get("refusal_codes", [])),
                "suv_followup": "PASS"
                if f.get("suv_eligible")
                else ";".join(f.get("refusal_codes", [])),
                "height_both": height_both,
                "ct_same_for_both": ct_both,
                "tracer_both": tracer_both,
                "recon_baseline": b["recon_description"]["value"],
                "recon_followup": f["recon_description"]["value"],
                "iterations_known_both": b["iterations"]["status"] == "PRESENT"
                and f["iterations"]["status"] == "PRESENT",
                "qiba_predicted": qiba.verdict,
                "eanm_predicted": verdicts["eanm-fdg-2.0"].verdict,
                "percist_predicted": verdicts["percist-1.0"].verdict,
                "qiba_blocking_fail_or_unknown": ";".join(blocking),
                "protocol_comparability": cat,
                "uptake_min_baseline": round(b["uptake_s"] / 60, 1) if b.get("uptake_s") else None,
                "uptake_min_followup": round(f["uptake_s"] / 60, 1) if f.get("uptake_s") else None,
                "download_MB_pet_ct": round(mb, 1),
                "pet_series_baseline": b["SeriesInstanceUID"],
                "pet_series_followup": f["SeriesInstanceUID"],
                "study_baseline": b["StudyInstanceUID"],
                "study_followup": f["StudyInstanceUID"],
            }
        )
    order = {
        "HIGH_CONFIDENCE_ANALYZABLE": 0,
        "ANALYZABLE_WITH_WARNINGS": 1,
        "LIKELY_INSUFFICIENT": 2,
        "UNKNOWN": 3,
    }
    vorder = {
        "ASSESSABLE": 0,
        "ASSESSABLE_WITH_WARNINGS": 1,
        "NOT_ASSESSABLE": 2,
        "INSUFFICIENT_INFORMATION": 3,
    }
    pairs.sort(
        key=lambda p: (
            order[p["category"]],
            not p["height_both"],
            not p["ct_same_for_both"],
            not p["tracer_both"],
            vorder[p["qiba_predicted"]],
            p["download_MB_pet_ct"],
        )
    )
    with (V2 / "pairs_v2.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(pairs[0]))
        w.writeheader()
        w.writerows(pairs)

    ok = [s for s in pet.values() if s.get("status") == "OK"]
    refusals = Counter(c for s in ok for c in s["refusal_codes"])
    summary = {
        "method": f"{N_SAMPLE} sampled slice headers per AC PET series (byte range) + 1 "
        "header per CT series; VoxelTrace strict validator, extractors and pair rules on "
        "the samples",
        "ac_pet_series": len(ac),
        "pet_headers_ok": len(ok),
        "pet_errors": len(pet) - len(ok),
        "ct_series_checked": len(ct),
        "suv_eligible_rate": round(sum(s["suv_eligible"] for s in ok) / len(ok), 4),
        "suv_refusal_codes": dict(refusals.most_common()),
        "decay_factor_consistency_rate": round(
            sum("DECAY_FACTOR_INCONSISTENT" not in s["refusal_codes"] for s in ok) / len(ok), 4
        ),
        "decay_factor_unverified_rate": round(
            sum("DECAY_FACTOR_UNVERIFIED" in s["warning_codes"] for s in ok) / len(ok), 4
        ),
        "frt_zero_with_decay_factor": sum(s["frt_zero_with_decay_factor"] for s in ok),
        "height_rate": round(sum(s["height_present"] for s in ok) / len(ok), 4),
        "ct_same_for_rate": round(sum(s["ct_same_for"] for s in ok) / len(ok), 4),
        "tracer_known_rate": round(
            sum(s["tracer"]["status"] == "PRESENT" for s in ok) / len(ok), 4
        ),
        "iterations_known_rate": round(
            sum(s["iterations"]["status"] == "PRESENT" for s in ok) / len(ok), 4
        ),
        "by_vendor": {
            v: {
                "series": len(g),
                "suv_eligible": sum(s["suv_eligible"] for s in g),
                "height": sum(s["height_present"] for s in g),
                "ct_same_for": sum(s["ct_same_for"] for s in g),
                "tracer": sum(s["tracer"]["status"] == "PRESENT" for s in g),
                "refusals": dict(Counter(c for s in g for c in s["refusal_codes"]).most_common(4)),
            }
            for v, g in _group(ok).items()
        },
        "pairs": len(pairs),
        "pair_categories": dict(Counter(p["category"] for p in pairs)),
        "pair_categories_by_vendor": {
            v: dict(Counter(p["category"] for p in pairs if p["vendor"] == v))
            for v in sorted({p["vendor"] for p in pairs})
        },
        "qiba_predicted": dict(Counter(p["qiba_predicted"] for p in pairs)),
        "likely_ii_pair_rate": round(
            sum(p["category"] == "LIKELY_INSUFFICIENT" for p in pairs) / max(len(pairs), 1), 4
        ),
    }
    (V2 / "census_v2_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


def vendor(m: str) -> str:
    u = m.upper()
    if "PHILIPS" in u:
        return "Philips"
    if u.startswith("GE") or "GEMS" in u:
        return "GE"
    if "SIEMENS" in u or u.startswith("CPS"):
        return "Siemens/CTI"
    return "other"


def _group(ok: list[dict]) -> dict[str, list[dict]]:
    g: dict[str, list[dict]] = defaultdict(list)
    for s in ok:
        g[vendor(s["manufacturer"])].append(s)
    return g


if __name__ == "__main__":
    sys.exit(main())
