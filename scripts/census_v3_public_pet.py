#!/usr/bin/env python3
"""Cross-collection public PET census v3, step 2: bounded header sampling + unchanged rules.

Metadata only. Input: ../data/census/public_pet_v3/series_index.csv (census_v3_index.py).

  python scripts/census_v3_public_pet.py sample    # header sampling (resumable, byte-capped)
  python scripts/census_v3_public_pet.py analyse   # pairs, rules, classification, ranking

Sampling (same machinery as census v2, scripts/census_v2_acrin.py):
  * PET candidate series: object listing, then N slice headers evenly spaced over the sorted
    object keys, each an HTTP byte range (16 KB, extended up to 256 KB only if needed), parsed
    with stop_before_pixels; raw bytes are never stored. N = 12, except collections whose
    TCIA description declares a non-FDG tracer (FLT, NaF, PSMA): N = 4 (budget only; the
    tracer used for every decision is read from DICOM, never from the collection name).
  * CT series of those studies: one header (FrameOfReferenceUID, ImageType).
  * Hard cap: MAX_BYTES transferred; the run stops (resumable) when reached.

Analysis:
  * tracer class from DICOM (RadiopharmaceuticalInformationSequence name/code): FDG, PSMA,
    AMYLOID, TAU, OTHER (e.g. FLT, NaF), UNKNOWN. FDG rule sets are applied ONLY to pairs
    whose two series are DICOM-FDG; other known tracers -> REQUIRES_TRACER_SPECIFIC_RULESET.
  * every ordered pair of PET candidate series of a subject with different study dates is
    evaluated with the unchanged assess_pair (QIBA 1.14, EANM 2.0, PERCIST 1.0);
  * classification (precedence order):
      FULLY_DECIDABLE_LIKELY   FDG; QIBA and EANM have no blocking UNKNOWN; strict SUV passes
                               at both timepoints without DECAY_FACTOR_UNVERIFIED
      DECIDABLE_WITH_WARNING   as above but SUV passes only with DECAY_FACTOR_UNVERIFIED, or
                               the only blocking unknown is voxel size (a 12-slice sampling
                               artefact that a full download resolves)
      PERCIST_POSSIBLE         FDG; SUV both; height both; CT in the PET frame both; no PERCIST
                               blocking FAIL; a non-AI or human-corrected lesion SEG at baseline
      LIKELY_INSUFFICIENT      anything else evaluated
      UNKNOWN                  header sampling failed / no evaluable pair
      REQUIRES_TRACER_SPECIFIC_RULESET   known non-FDG tracer at both timepoints
    Missing reconstruction evidence, tracer or height never counts as a pass. A pair that is
    blocked ONLY by reconstruction parameters is flagged qiba_attestation_path_possible (a
    site attestation could be requested); it is NOT counted as decidable.

Writes ../data/census/public_pet_v3/{pet_series_v3.jsonl, ct_series_v3.jsonl,
candidates_v3.csv, census_v3_summary.json}.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import sys
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from voxeltrace.census.sampled import predict_pet
from voxeltrace.evidence.comparability import compare_protocols
from voxeltrace.rules.registry import assess_pair, get_ruleset, verdict
from voxeltrace.trial.schema import PairContext, ScanPair

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / "data" / "census" / "public_pet_v3"
MAX_BYTES = 2_500_000_000
N_DEFAULT = 12
N_BY_COLLECTION = {"acrin_flt_breast": 4, "naf_prostate": 4, "psma_pet_ct_lesions": 4}
RULESETS = ("qiba-fdg-1.14", "eanm-fdg-2.0", "percist-1.0")
RECON_FIELDS = (
    "reconstruction_method", "iterations", "subsets", "convolution_kernel", "time_of_flight",
    "psf_resolution_modelling",
)  # fmt: skip

_spec = importlib.util.spec_from_file_location(
    "census_v2", Path(__file__).with_name("census_v2_acrin.py")
)
census_v2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(census_v2)

_bytes = 0
_lock = threading.Lock()
_orig_get = census_v2._get


def _counting_get(url: str, rng: str | None = None) -> bytes:
    global _bytes
    if _bytes > MAX_BYTES:
        raise RuntimeError("BYTE_CAP_REACHED")
    data = _orig_get(url, rng)
    with _lock:
        _bytes += len(data)
    return data


census_v2._get = _counting_get


# ------------------------------------------------------------------ classification helpers


def tracer_class(name: str | None) -> str:
    if not name:
        return "UNKNOWN"
    s = name.casefold()
    for cls, pat in (
        ("FDG", r"fdg|fluorodeoxyglucose|fludeoxyglucose"),
        ("PSMA", r"psma|dcfpyl|pylarify|gozetotide|piflufolastat|1007"),
        ("AMYLOID", r"florbetapir|florbetaben|flutemetamol|pittsburgh|\bpib\b|nav4694|amyvid"),
        ("TAU", r"flortaucipir|av.?1451|mk.?6240|pi.?2620|tauvid"),
    ):
        if re.search(pat, s):
            return cls
    return "OTHER"


def vendor(m: str) -> str:
    u = (m or "").upper().strip()
    if not u or u in ("NONE", "NAN"):
        return "UNKNOWN_MANUFACTURER"  # never inferred from the model number
    if "UIH" in u or "UNITED IMAGING" in u:
        return "United Imaging"
    v = census_v2.vendor(m or "")
    return {"Siemens/CTI": "Siemens"}.get(v, v)


def architecture(model: str) -> str:
    m = (model or "").casefold()
    if "uexplorer" in m:
        return "TOTAL_BODY"
    if "quadra" in m:
        return "LONG_AFOV"
    if any(k in m for k in ("mmr", "signa pet", "upmr", "pet/mr", "petmr")):
        return "PET_MR"
    return "CONVENTIONAL_AFOV"


def seg_source(desc: str, analysis_id: str) -> str:
    d = (desc or "").casefold()
    if "radiologist" in d and "corrected" in d:
        return "HUMAN_CORRECTED_RADIOLOGIST"
    if "non-expert" in d and "corrected" in d:
        return "HUMAN_CORRECTED_NON_EXPERT"
    if analysis_id and analysis_id != "nan" or " ai " in f" {d} ":
        return "AI_UNREVIEWED"
    return "COLLECTION_ANNOTATION"  # original collection SEG/RTSTRUCT; provenance per TCIA page


# ------------------------------------------------------------------ sampling


def _fv(f) -> dict:
    v = f.value
    return {"value": list(v) if isinstance(v, tuple) else v, "status": f.status}


def record_from_headers(row: dict, hs: list, n_listed: int) -> dict:
    """Census record of one PET series from its sampled headers (no network)."""
    rec = {k: row[k] for k in ("SeriesInstanceUID", "PatientID", "collection_id")}
    p = predict_pet(row["SeriesInstanceUID"], hs)
    pr, inp, h0 = p["protocol"], p["inputs"], hs[0]
    rp = (h0.get("RadiopharmaceuticalInformationSequence") or [None])[0]
    rec.update(
        status="OK",
        n_instances_listed=n_listed,
        n_sampled=p["n_sampled"],
        suv_eligible=p["suv_eligible"],
        refusal_codes=p["refusal_codes"],
        warning_codes=p["warning_codes"],
        uptake_s=inp.decay_interval_s,
        weight_kg=inp.patient_weight_kg,
        dose_bq=inp.radionuclide_total_dose_bq,
        half_life_s=inp.radionuclide_half_life_s,
        height_present=p["height_present"],
        weight_present=p["weight_present"],
        derived=p["derived"],
        units=str(h0.get("Units")),
        decay_correction=str(h0.get("DecayCorrection")),
        corrected_image=[str(x) for x in (h0.get("CorrectedImage") or [])],
        injection_time_present=bool(
            rp is not None
            and (
                rp.get("RadiopharmaceuticalStartDateTime") or rp.get("RadiopharmaceuticalStartTime")
            )
        ),
        scan_time_present=bool(h0.get("SeriesTime") or h0.get("AcquisitionTime")),
        frame_reference_time_present=all(h.get("FrameReferenceTime") is not None for h in hs),
        decay_factor_present=all(h.get("DecayFactor") is not None for h in hs),
        frt_zero_with_decay_factor=p["frt_zero_with_decay_factor"],
        frame_of_reference=str(h0.get("FrameOfReferenceUID")),
        manufacturer=str(h0.get("Manufacturer")),
        model=str(h0.get("ManufacturerModelName")),
        tracer_name=str(pr.acquisition.tracer.value) if pr.acquisition.tracer.known else None,
        tracer_code=str(pr.acquisition.radiopharmaceutical_code.value)
        if pr.acquisition.radiopharmaceutical_code.known
        else None,
        software=_fv(pr.scanner.software_versions),
        recon={f: _fv(getattr(pr.reconstruction, f)) for f in RECON_FIELDS},
        protocol_json=pr.model_dump_json(),
    )
    return rec


def do_pet(row: dict) -> dict:
    try:
        # skip zero-byte "folder" marker objects (present in some IDC prefixes)
        ks = [
            k
            for k in census_v2.keys(row["aws_bucket"], row["crdc_series_uuid"])
            if not k.endswith("/")
        ]
        n = N_BY_COLLECTION.get(row["collection_id"], N_DEFAULT)
        hs = [census_v2.header(row["aws_bucket"], ks[i]) for i in census_v2.sample_idx(len(ks), n)]
        return record_from_headers(row, hs, len(ks))
    except Exception as exc:  # noqa: BLE001 - record, never guess
        rec = {k: row[k] for k in ("SeriesInstanceUID", "PatientID", "collection_id")}
        rec.update(status="ERROR", error=f"{type(exc).__name__}: {exc}")
        return rec


def do_ct(row: dict) -> dict:
    rec = {k: row[k] for k in ("SeriesInstanceUID", "StudyInstanceUID")}
    rec["series_size_MB"] = float(row["series_size_MB"])
    try:
        k = [
            x
            for x in census_v2.keys(row["aws_bucket"], row["crdc_series_uuid"])
            if not x.endswith("/")
        ]
        ds = census_v2.header(row["aws_bucket"], k[len(k) // 2])
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
        for x in path.read_text().splitlines():
            r = json.loads(x)
            if r.get("status") == "OK":  # errors are retried on the next run
                done[r["SeriesInstanceUID"]] = r
    todo = [r for r in rows if r["SeriesInstanceUID"] not in done]
    print(f"{path.name}: {len(done)} done, {len(todo)} to do", flush=True)
    if path.exists():  # rewrite without stale error records
        path.write_text("".join(json.dumps(r, default=str) + "\n" for r in done.values()))
    with path.open("a") as fh, ThreadPoolExecutor(8) as ex:
        for i, rec in enumerate(ex.map(fn, todo), 1):
            fh.write(json.dumps(rec, default=str) + "\n")
            fh.flush()
            done[rec["SeriesInstanceUID"]] = rec
            if i % 100 == 0:
                print(f"  {i}/{len(todo)}  {_bytes / 1e6:.0f} MB", flush=True)
    return done


def sample() -> int:
    rows = list(csv.DictReader((V3 / "series_index.csv").open()))
    pet = [r for r in rows if r["role"] == "PET_CANDIDATE"]
    ct = [r for r in rows if r["role"] == "AUX" and r["Modality"] == "CT"]
    run_jobs(do_pet, pet, V3 / "pet_series_v3.jsonl")
    run_jobs(do_ct, ct, V3 / "ct_series_v3.jsonl")
    (V3 / "sampling_bytes.json").write_text(
        json.dumps({"bytes_this_run": _bytes, "cap": MAX_BYTES}, indent=2) + "\n"
    )
    print(f"transferred this run: {_bytes / 1e6:.1f} MB (cap {MAX_BYTES / 1e6:.0f} MB)")
    return 0


# ------------------------------------------------------------------ analysis


RECON_PARAMS = {
    "reconstruction_method", "iterations", "subsets", "time_of_flight",
    "psf_resolution_modelling", "post_filter",
}  # fmt: skip


def voxel_proxy_same(tb, tf) -> bool:
    """PixelSpacing and SliceThickness known and identical at both timepoints."""
    out = []
    for get in (
        lambda t: t.protocol.acquisition.pixel_spacing_mm,
        lambda t: t.protocol.reconstruction.slice_thickness_mm,
    ):
        a, b = get(tb), get(tf)
        out.append(a.known and b.known and a.value == b.value)
    return all(out)


def both(b: dict, f: dict, fn) -> str:
    return f"{fn(b)} / {fn(f)}"


def _blocking(v, kind):
    return sorted(c.rule_id for c in v.checks if c.impact == "blocking" and c.status == kind)


def enrich(s: dict, r: dict, ct_by_study: dict) -> None:
    """Add study facts, CT frame-of-reference match, tracer class, vendor, architecture."""
    s.update(
        StudyInstanceUID=r["StudyInstanceUID"],
        StudyDate=r["StudyDate"],
        pet_MB=float(r["series_size_MB"]),
        license=r["license_short_name"],
    )
    if s.get("status") != "OK":
        return
    match = [
        c
        for c in ct_by_study.get(r["StudyInstanceUID"], [])
        if c["frame_of_reference"] == s["frame_of_reference"]
    ]
    s["ct_same_for"] = bool(match)
    s["ct_in_pet_frame"] = len(match)
    s["ct_in_pet_frame_derived"] = sum("DERIVED" in c.get("image_type", []) for c in match)
    s["ct_min_MB"] = min((c["series_size_MB"] for c in match), default=None)
    s["tracer_class"] = tracer_class(s.get("tracer_name") or s.get("tracer_code"))
    s["vendor"] = vendor(s["manufacturer"])
    s["architecture"] = architecture(s["model"])


def analyse() -> int:
    rows = list(csv.DictReader((V3 / "series_index.csv").open()))
    idx = {r["SeriesInstanceUID"]: r for r in rows}
    pet = {
        json.loads(x)["SeriesInstanceUID"]: json.loads(x)
        for x in (V3 / "pet_series_v3.jsonl").read_text().splitlines()
    }
    ct = [json.loads(x) for x in (V3 / "ct_series_v3.jsonl").read_text().splitlines()]
    ct_by_study = defaultdict(list)
    for c in ct:
        # mirrors trial/timepoint.py: any CT-modality series in the PET frame of reference
        # (ImageType is NOT filtered there; census v2 excluded DERIVED CTs, which was stricter)
        if c.get("status") == "OK":
            ct_by_study[c["StudyInstanceUID"]].append(c)
    segs = defaultdict(list)
    for r in rows:
        if r["Modality"] in ("SEG", "RTSTRUCT"):
            segs[r["StudyInstanceUID"]].append(
                seg_source(r["SeriesDescription"], r["analysis_result_id"])
            )
    for uid, s in pet.items():
        enrich(s, idx[uid], ct_by_study)
    rulesets = {rs: get_ruleset(rs) for rs in RULESETS}
    by_subject = defaultdict(list)
    for s in pet.values():
        by_subject[(s["collection_id"], s["PatientID"])].append(s)
    cand_rows = []
    for (col, pid), ss in sorted(by_subject.items()):
        ok = [s for s in ss if s.get("status") == "OK"]
        n_dates = len({s["StudyDate"] for s in ok})
        best = None
        for b in ok:
            for f in ok:
                if b["StudyDate"] >= f["StudyDate"]:
                    continue
                row = score_pair(col, pid, b, f, rulesets, segs)
                row["timepoints_available"] = n_dates
                if best is None or row["_key"] < best["_key"]:
                    best = row
        if best is None:
            best = {
                "collection": col, "subject": pid, "class": "UNKNOWN",
                "main_blockers": "header sampling failed or no two dated AC series",
                "_key": (9,),
            }  # fmt: skip
        cand_rows.append(best)
    cand_rows.sort(key=lambda r: r["_key"])
    for i, r in enumerate(cand_rows, 1):
        r["rank"] = i
    fields = ["rank"] + [k for k in cand_rows[0] if k not in ("rank", "_key")]
    allk = []
    for r in cand_rows:
        for k in r:
            if k not in allk and k not in ("_key",):
                allk.append(k)
    fields = ["rank"] + [k for k in allk if k != "rank"]
    with (V3 / "candidates_v3.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(cand_rows)
    ok_series = [s for s in pet.values() if s.get("status") == "OK"]
    summary = {
        "pet_series_sampled": len(pet),
        "pet_series_ok": len(ok_series),
        "pet_series_errors": Counter(
            s.get("error", "")[:60] for s in pet.values() if s.get("status") != "OK"
        ),
        "ct_series_checked": len(ct),
        "subjects": len(cand_rows),
        "class_counts": Counter(r["class"] for r in cand_rows),
        "class_by_collection": {
            col: dict(Counter(r["class"] for r in cand_rows if r["collection"] == col))
            for col in sorted({r["collection"] for r in cand_rows})
        },
        "series_by_vendor": Counter(s["vendor"] for s in ok_series),
        "series_by_vendor_model": Counter(f"{s['vendor']} | {s['model']}" for s in ok_series),
        "series_by_architecture": Counter(s["architecture"] for s in ok_series),
        "series_by_tracer_class": Counter(s["tracer_class"] for s in ok_series),
        "series_by_collection_tracer": Counter(
            f"{s['collection_id']} | {s['tracer_class']}" for s in ok_series
        ),
        "suv_eligible_by_collection": {
            col: f"{sum(s['suv_eligible'] for s in ok_series if s['collection_id'] == col)}/"
            f"{sum(1 for s in ok_series if s['collection_id'] == col)}"
            for col in sorted({s["collection_id"] for s in ok_series})
        },
        "refusals": Counter(c for s in ok_series for c in s["refusal_codes"]),
        "height_by_collection": {
            col: f"{sum(s['height_present'] for s in ok_series if s['collection_id'] == col)}/"
            f"{sum(1 for s in ok_series if s['collection_id'] == col)}"
            for col in sorted({s["collection_id"] for s in ok_series})
        },
        "recon_completeness_by_vendor": {
            v: {
                "series": sum(1 for s in ok_series if s["vendor"] == v),
                **{
                    f: sum(
                        1
                        for s in ok_series
                        if s["vendor"] == v and s["recon"][f]["status"] == "PRESENT"
                    )
                    for f in RECON_FIELDS
                },
            }
            for v in sorted({s["vendor"] for s in ok_series})
        },  # fmt: skip
    }
    (V3 / "census_v3_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    keys = ("subjects", "class_counts", "series_by_vendor", "series_by_tracer_class",
            "suv_eligible_by_collection")  # fmt: skip
    print(json.dumps({k: summary[k] for k in keys}, indent=2, default=str))
    return 0


def score_pair(col, pid, b, f, rulesets, segs) -> dict:
    tb = census_v2.timepoint(b, pid, "baseline")
    tf = census_v2.timepoint(f, pid, "followup")
    ctx = PairContext(pair=ScanPair(subject_id=pid, baseline="baseline", followup="followup"),
                      baseline=tb, followup=tf)  # fmt: skip
    tc = (b["tracer_class"], f["tracer_class"])
    suv_both = bool(b["suv_eligible"] and f["suv_eligible"])
    unverified = any("DECAY_FACTOR_UNVERIFIED" in s["warning_codes"] for s in (b, f))
    height = bool(b["height_present"] and f["height_present"])
    ct_both = bool(b["ct_same_for"] and f["ct_same_for"])
    bseg = segs.get(b["StudyInstanceUID"], [])
    lesion_ok = any(
        x in ("COLLECTION_ANNOTATION", "HUMAN_CORRECTED_RADIOLOGIST", "HUMAN_CORRECTED_NON_EXPERT")
        for x in bseg
    )
    out = {
        "collection": col,
        "subject": pid,
        "vendor": f"{b['vendor']} / {f['vendor']}",
        "scanner": f"{b['manufacturer']} {b['model']} / {f['manufacturer']} {f['model']}",
        "architecture": f"{b['architecture']} / {f['architecture']}",
        "software": f"{b['software']['value']} / {f['software']['value']}",
        "tracer": both(b, f, lambda s: s.get("tracer_name") or s.get("tracer_code")),
        "tracer_class": "/".join(tc),
        "interval_days": (
            date.fromisoformat(f["StudyDate"]) - date.fromisoformat(b["StudyDate"])
        ).days,
        "units": f"{b['units']} / {f['units']}",
        "decay_correction": f"{b['decay_correction']} / {f['decay_correction']}",
        "corrected_image": f"{'+'.join(b['corrected_image'])} / {'+'.join(f['corrected_image'])}",
        "weight": f"{b['weight_kg']} / {f['weight_kg']}",
        "height": f"{b['height_present']} / {f['height_present']}",
        "dose_MBq": both(b, f, lambda s: s["dose_bq"] and round(s["dose_bq"] / 1e6)),
        "half_life_s": f"{b['half_life_s']} / {f['half_life_s']}",
        "injection_time": f"{b['injection_time_present']} / {f['injection_time_present']}",
        "scan_time": f"{b['scan_time_present']} / {f['scan_time_present']}",
        "frame_reference_time": both(b, f, lambda s: s["frame_reference_time_present"]),
        "decay_factor": f"{b['decay_factor_present']} / {f['decay_factor_present']}",
        "uptake_min": both(b, f, lambda s: s["uptake_s"] and round(s["uptake_s"] / 60, 1)),
        "suv": both(b, f, lambda s: "PASS" if s["suv_eligible"] else ";".join(s["refusal_codes"])),
        "decay_crosscheck": "UNVERIFIED (tags absent)" if unverified else "CHECKED_ON_SAMPLES",
        **{
            f"recon_{k}": f"{b['recon'][k]['value']} / {f['recon'][k]['value']}"
            for k in RECON_FIELDS
        },
        "ct_for": f"{b['ct_same_for']} / {f['ct_same_for']}",
        "ct_in_pet_frame (derived)": both(
            b, f, lambda s: f"{s['ct_in_pet_frame']} ({s['ct_in_pet_frame_derived']})"
        ),
        "seg_baseline": ";".join(sorted(bseg)) or "none",
        "seg_followup": ";".join(sorted(segs.get(f["StudyInstanceUID"], []))) or "none",
        "download_MB": round(
            b["pet_MB"] + f["pet_MB"] + (b["ct_min_MB"] or 0) + (f["ct_min_MB"] or 0), 1
        ),
        "license": b["license"],
    }
    if any(t in ("PSMA", "AMYLOID", "TAU", "OTHER") for t in tc) and "UNKNOWN" not in tc:
        out.update(cls="REQUIRES_TRACER_SPECIFIC_RULESET", qiba="NOT_EVALUATED (non-FDG)",
                   eanm="NOT_EVALUATED (non-FDG)", percist="NOT_EVALUATED (non-FDG)",
                   main_blockers="non-FDG tracer: FDG standards not applied")  # fmt: skip
        out["class"] = out.pop("cls")
        out["_key"] = (6, not suv_both, out["download_MB"])
        return out
    cat = compare_protocols(tb.protocol, tf.protocol)
    v = {rs: assess_pair(r, ctx, cat.category) for rs, r in rulesets.items()}
    q, e, p = v["qiba-fdg-1.14"], v["eanm-fdg-2.0"], v["percist-1.0"]
    unk = sorted(set(_blocking(q, "UNKNOWN")) | set(_blocking(e, "UNKNOWN")))
    fail = sorted(set(_blocking(q, "FAIL")) | set(_blocking(e, "FAIL")))
    ident_unk = [c.name for c in cat.checks if c.result == "UNKNOWN" and c.impact == "blocking"]

    voxel_only = (
        bool(unk)
        and set(unk) <= {"VT-PROTOCOL-IDENTITY", "EANM-SAME-SYSTEM-SETTINGS"}
        and set(ident_unk) == {"voxel_size"}
    )
    # voxel size is never known from sampled headers (no full geometry); a full download
    # resolves it. Header proxy: identical PixelSpacing and SliceThickness at both timepoints.
    proxy = voxel_proxy_same(tb, tf)
    sampling_only = voxel_only and proxy
    recon_unk = set(ident_unk) - ({"voxel_size"} if proxy else set())
    recon_only = (
        bool(recon_unk)
        and set(unk) <= {"VT-PROTOCOL-IDENTITY", "EANM-SAME-SYSTEM-SETTINGS", "EANM-EARL-RECON"}
        and recon_unk <= RECON_PARAMS
    )

    def if_voxel_confirmed(res):
        if not sampling_only:
            return res.verdict
        fixed = [
            c.model_copy(update={"status": "PASS"})
            if c.rule_id in ("VT-PROTOCOL-IDENTITY", "EANM-SAME-SYSTEM-SETTINGS")
            and c.status == "UNKNOWN"
            else c
            for c in res.checks
        ]
        return verdict(fixed)

    q_eff, e_eff, p_eff = if_voxel_confirmed(q), if_voxel_confirmed(e), if_voxel_confirmed(p)
    pfail = _blocking(p, "FAIL")
    p_ident = next(c.status for c in p.checks if c.rule_id == "VT-PROTOCOL-IDENTITY")
    if not suv_both:
        readiness = "UNKNOWN"
    elif not height:
        readiness = "PERCIST_BLOCKED_BY_SUL"
    elif not ct_both:
        readiness = "PERCIST_BLOCKED_BY_REFERENCE"
    elif p_ident == "FAIL" or (p_ident == "UNKNOWN" and not sampling_only):
        readiness = "PERCIST_BLOCKED_BY_RECON"
    elif lesion_ok:
        readiness = "PERCIST_READY (pending human review of liver + lesion)"
    else:
        readiness = "PERCIST_LIVER_READY_BUT_LESION_MISSING"
    decided = not unk or sampling_only
    if tc != ("FDG", "FDG"):
        cls = "LIKELY_INSUFFICIENT"  # tracer unknown at >= 1 timepoint: never a pass
    elif suv_both and decided and not unverified:
        cls = "FULLY_DECIDABLE_LIKELY"
    elif suv_both and decided:
        cls = "DECIDABLE_WITH_WARNING"
    elif suv_both and height and ct_both and lesion_ok and not pfail:
        cls = "PERCIST_POSSIBLE"
    else:
        cls = "LIKELY_INSUFFICIENT"
    assessable = q_eff.startswith("ASSESSABLE") and e_eff.startswith("ASSESSABLE")
    out.update(
        {
            "class": cls,
            "qiba": q.verdict,
            "eanm": e.verdict,
            "percist": p.verdict,
            "qiba_if_voxel_confirmed": q_eff,
            "eanm_if_voxel_confirmed": e_eff,
            "percist_if_voxel_confirmed": p_eff,
            "voxel_header_proxy_same": proxy,
            "percist_readiness": readiness,
            "blocking_unknown": ";".join(unk),
            "blocking_fail": ";".join(fail),
            "identity_unknown_fields": ";".join(ident_unk),
            "qiba_attestation_path_possible": recon_only and suv_both and tc == ("FDG", "FDG"),
            "predicted_assessable": assessable and tc == ("FDG", "FDG"),
            "main_blockers": ";".join(
                [u for u in unk if not sampling_only]
                + fail
                + (["voxel size: confirm on download"] if sampling_only else [])
                + (["DECAY_FACTOR_UNVERIFIED"] if unverified else [])
            )
            or "none",
        }
    )
    order = {
        "FULLY_DECIDABLE_LIKELY": 0,
        "DECIDABLE_WITH_WARNING": 1,
        "PERCIST_POSSIBLE": 2,
        "LIKELY_INSUFFICIENT": 3,
    }
    out["_key"] = (
        order[cls],
        not out["predicted_assessable"],
        not suv_both,
        len(unk),
        len(fail),
        not height,
        not ct_both,
        out["download_MB"],
    )
    return out


if __name__ == "__main__":
    sys.exit({"sample": sample, "analyse": analyse}[sys.argv[1]]())
