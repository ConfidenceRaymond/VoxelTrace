#!/usr/bin/env python3
"""Build the vendor / scanner knowledge base (configs/vendor_kb.yaml + docs/vendor_knowledge_base.md).

Sources, and nothing else:
  * curated entries below: model list, architecture class, availability and references ONLY
    from documents this project actually read (docs/multivendor_validation_plan.md,
    docs/vendor_decay_timing.md, docs/reconstruction_audit_168.md, vendors/*.py);
  * OBSERVED per-model statistics from census v3 sampled headers
    (../data/census/public_pet_v3/pet_series_v3.jsonl) and census v2 (ACRIN);
  * validation status from real pairs analysed in this project.
Unknown information is written as null / NOT_DOCUMENTED, never filled in.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
REPO = Path(__file__).resolve().parents[1]
V3 = ROOT / "data" / "census" / "public_pet_v3" / "pet_series_v3.jsonl"
V2 = ROOT / "data" / "census" / "acrin_nsclc_fdg_pet_v2" / "pet_series_v2.jsonl"
RECON = ("reconstruction_method", "iterations", "subsets", "convolution_kernel", "time_of_flight",
         "psf_resolution_modelling")  # fmt: skip

SIEMENS_CS = "Siemens Biograph TruePoint 6.7 DICOM Conformance Statement (private creator 'SIEMENS MED PT' (0071,1022) Decay Correction DateTime)"
QIBA_PSEUDO = "QIBA SUV vendor-neutral pseudo-code 2018-06-26"
GE_CS = "GE Discovery LS DICOM conformance statement (Direction 5101600GD0 / 2343444GSP): listed on GE site, PDF NOT retrievable (HTTP 502), not read"

# (vendor, model key, census model strings, architecture, public DICOM, notes, validation)
CURATED = [
    ("SIEMENS", "Biograph mCT", ["Biograph128_mCT", "Biograph64_mCT", "Biograph40_mCT", "Biograph mCT Flow 20", "Biograph64_mCT 4R", "SOMATOM Definition AS_mCT"], "CONVENTIONAL_AFOV", "OPEN (IDC: fdg_pet_ct_lesions, psma_pet_ct_lesions, varepop_apollo, cmb_*)", "reconstruction encoded as structured text (e.g. 'PSF+TOF 2i21s') + ConvolutionKernel; DecayFactor/FrameReferenceTime present", "REAL_PAIRS_VALIDATED: autoPET PETCT_c2ffda4725 (Biograph128 mCT) QIBA ASSESSABLE; cmb_mel MSB-07612 (Biograph40 mCT) decided NOT_ASSESSABLE; DecayFactor VERIFIED"),
    ("SIEMENS", "Biograph (TruePoint / Biograph64 / 16)", ["Biograph64", "Biograph 64-4R TruePoint", "Biograph 16", "Biograph128"], "CONVENTIONAL_AFOV", "OPEN (IDC: cc_tumor_heterogeneity, psma_pet_ct_lesions)", "older syngo software (e.g. MI.PET/CT 2011A)", "REAL_PAIR_VALIDATED: cc_tumor CCTH-B02 (Biograph64) QIBA ASSESSABLE; DecayFactor VERIFIED"),
    ("SIEMENS", "Biograph Vision", [], "CONVENTIONAL_AFOV", "NOT_OBSERVED in open IDC PET (v25)", None, "NOT_VALIDATED"),
    ("SIEMENS", "Biograph Vision Quadra", [], "LONG_AFOV", "GATED (UDPET, data-transfer agreement; low-dose images simulated)", None, "NOT_VALIDATED"),
    ("SIEMENS", "Biograph Horizon", ["Biograph Horizon"], "CONVENTIONAL_AFOV", "OPEN (observed in IDC, 2 series)", None, "CENSUS_ONLY"),
    ("SIEMENS/CTI", "CPS/CTI legacy (1023, 1024, 1080, 1093, 1094)", ["1023", "1024", "1080", "1093", "1094"], "CONVENTIONAL_AFOV", "OPEN (IDC: ACRIN NSCLC/FLT, others); Manufacturer often 'CPS' or EMPTY", "tracer name/code often absent; height absent in ACRIN; FrameReferenceTime=0 with per-bed DecayFactor seen on 1023", "REAL_PAIRS_ANALYZED: ACRIN 050 (CPS 1080) SUV PASS, DecayFactor VERIFIED; ACRIN 153 (CPS 1023) refused DECAY_FACTOR_INCONSISTENT (INTERNALLY_INCONSISTENT)"),
    ("GE", "Discovery LS", ["Discovery LS"], "CONVENTIONAL_AFOV", "OPEN (IDC: ACRIN NSCLC/FLT)", "software 16.01 encodes no reconstruction method/iterations/subsets; DecayFactor absent on 167/168; on 094 DecayFactor at mid-frame vs FrameReferenceTime at frame start (PLAUSIBLE_BUT_UNVERIFIED)", "REAL_PAIRS_ANALYZED: ACRIN 167/168 SUV PASS (DecayFactor NOT_AVAILABLE); 094 refused DECAY_FACTOR_INCONSISTENT; reconstruction identity NOT_ESTABLISHED (168)"),
    ("GE", "Discovery ST / STE / RX", ["Discovery ST", "Discovery STE", "Discovery RX"], "CONVENTIONAL_AFOV", "OPEN (IDC: ACRIN, RIDER-adjacent)", "iterations/subsets never encoded in census", "CENSUS_ONLY (strict SUV mostly refused: DECAY_FACTOR_INCONSISTENT / non-BQML)"),
    ("GE", "Discovery 690 / 710", ["Discovery 690", "Discovery 710"], "CONVENTIONAL_AFOV", "OPEN (IDC: psma_pet_ct_lesions)", "reconstruction text e.g. 'VPFX'", "CENSUS_ONLY"),
    ("GE", "Advance", ["Advance"], "CONVENTIONAL_AFOV", "OPEN (IDC: RIDER Lung PET-CT)", "Units GML (not BQML)", "CENSUS_ONLY (strict SUV refused: UNSUPPORTED_UNITS)"),
    ("GE", "Discovery MI", [], "CONVENTIONAL_AFOV", "NOT_OBSERVED in open IDC PET (v25)", None, "NOT_VALIDATED"),
    ("GE", "Omni Legend", [], "CONVENTIONAL_AFOV", "NOT_OBSERVED; no documentation retrieved", None, "NOT_VALIDATED"),
    ("PHILIPS", "Gemini (TF TOF 16/64, Big Bore)", ["GEMINI TF TOF 16", "GEMINI TF Big Bore", "GEMINI TF TOF 64"], "CONVENTIONAL_AFOV", "OPEN (IDC: ACRIN FLT/NSCLC)", "Units CNTS with Philips private scale factors; strict BQML path refuses", "CENSUS_ONLY (strict SUV refused: UNSUPPORTED_UNITS / MISSING_CORRECTION)"),
    ("PHILIPS", "Allegro", ["Allegro Body(C)"], "CONVENTIONAL_AFOV", "OPEN (observed in IDC: ACRIN NSCLC and others)", None, "CENSUS_ONLY"),
    ("PHILIPS", "Ingenuity", [], "CONVENTIONAL_AFOV", "NOT_OBSERVED in open IDC PET (v25)", None, "NOT_VALIDATED"),
    ("PHILIPS", "Vereos", [], "CONVENTIONAL_AFOV", "NOT_OBSERVED in open IDC PET (v25)", None, "NOT_VALIDATED"),
    ("UNITED IMAGING", "uEXPLORER", [], "TOTAL_BODY", "GATED (UDPET DTA; simulated low-dose); NO_OPEN_DICOM_IDENTIFIED", None, "NOT_VALIDATED"),
    ("UNITED IMAGING", "uMI Panorama", [], "CONVENTIONAL_AFOV", "NO_OPEN_DICOM_IDENTIFIED (FDA K241585 record only)", None, "NOT_VALIDATED"),
    ("UNITED IMAGING", "uMI 780", [], "CONVENTIONAL_AFOV", "NO_OPEN_DICOM_IDENTIFIED", None, "NOT_VALIDATED"),
    ("UNITED IMAGING", "uMI 550", ["uMI 550"], "CONVENTIONAL_AFOV", "OPEN but only 1 DERIVED series in IDC (cmb_pca 'MIP MOVIE: PET AC PYLARIFY', via MIM)", "no quantitative series available", "NOT_VALIDATED"),
    ("UNITED IMAGING", "uPMR 790", [], "PET_MR", "NO_OPEN_DICOM_IDENTIFIED (FDA K183014/K222540/K234154 records only)", None, "NOT_VALIDATED"),
]  # fmt: skip
PRIVATE = {
    "SIEMENS": [{"creator": "SIEMENS MED PT", "tag": "(0071,xx22)", "field": "Decay Correction DateTime", "status": "DOCUMENTED (read-only)", "source": SIEMENS_CS}],
    "GE": [{"creator": "GEMS_PETD_01", "tag": "(0009,xx0D)", "field": "scan datetime (decay reference)", "status": "DOCUMENTED via QIBA pseudo-code (read-only)", "source": QIBA_PSEUDO},
           {"creator": "GEMS_PETD_01", "tag": "(0009,xx38/39/3B/3C/3D)", "field": "tracer activity / datetimes (pydicom names)", "status": "UNSUPPORTED (secondary dictionaries only)", "source": "pydicom 3.0.2 / GDCM private dictionaries"}],
    "PHILIPS": [{"creator": "Philips PET Private Group", "tag": "(7053,xx00) / (7053,xx09)", "field": "SUV / activity scale factor (Units CNTS)", "status": "DOCUMENTED via QIBA pseudo-code; NOT used by the strict BQML path", "source": QIBA_PSEUDO}],
}  # fmt: skip


def observed() -> dict[str, dict]:
    stats: dict[str, dict] = defaultdict(lambda: {"series": 0, "suv_pass": 0, "height": 0, "df": 0, "frt": 0,
                                                  "refusals": Counter(), "recon": Counter(), "sources": set()})  # fmt: skip
    for path, tag in ((V3, "census_v3"), (V2, "census_v2_acrin")):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            r = json.loads(line)
            if r.get("status") != "OK":
                continue
            m = str(r.get("model") or "").strip()
            s = stats[m]
            s["series"] += 1
            s["suv_pass"] += bool(r.get("suv_eligible"))
            s["height"] += bool(r.get("height_present"))
            s["df"] += bool(r.get("decay_factor_present"))
            s["frt"] += bool(r.get("frame_reference_time_present"))
            s["refusals"].update(r.get("refusal_codes", []))
            rec = r.get("recon") or {
                k: {"status": (r.get(k) or {}).get("status")}
                for k in ("recon_description", "iterations", "subsets")
            }
            for k, v in rec.items():
                s["recon"][k] += (v or {}).get("status") == "PRESENT"
            s["sources"].add(tag)
    return stats


def main() -> int:
    obs = observed()
    entries = []
    for vendor, model, keys, arch, avail, notes, validation in CURATED:
        agg = {
            "series": 0,
            "suv_pass": 0,
            "height": 0,
            "recon": Counter(),
            "refusals": Counter(),
            "sources": set(),
        }
        for k in keys:
            if k in obs:
                o = obs[k]
                for f in ("series", "suv_pass", "height"):
                    agg[f] += o[f]
                agg["recon"].update(o["recon"])
                agg["refusals"].update(o["refusals"])
                agg["sources"] |= o["sources"]
        n = agg["series"]
        entries.append({
            "vendor": vendor,
            "model": model,
            "census_model_strings": keys,
            "architecture": arch,
            "public_dicom_availability": avail,
            "public_conformance_docs": SIEMENS_CS if vendor.startswith("SIEMENS") and "Biograph" in model and "TruePoint" in model
                                       else GE_CS if model == "Discovery LS" else "NOT_RETRIEVED",
            "documented_private_fields": PRIVATE.get(vendor.split("/")[0], []),
            "observed_in_open_data": {
                "series_sampled": n,
                "strict_suv_pass": f"{agg['suv_pass']}/{n}" if n else None,
                "height_present": f"{agg['height']}/{n}" if n else None,
                "reconstruction_fields_present": {k: f"{v}/{n}" for k, v in agg["recon"].items()} if n else None,
                "top_refusals": dict(agg["refusals"].most_common(3)),
                "sources": sorted(agg["sources"]),
            },
            "timing_and_reconstruction_notes": notes or "NOT_DOCUMENTED",
            "anonymization_risks": "de-identified IDC data: injection DateTime often absent (date taken from series); height absent in some collections" if n else "NOT_DOCUMENTED",
            "parser_coverage": "standard BQML/START path (vendor-neutral) + documented private timing (read-only)" if vendor in ("SIEMENS", "GE", "SIEMENS/CTI") else
                               "standard BQML path only; Philips CNTS scale factors not used" if vendor == "PHILIPS" else "none (no vendor module)",
            "validation_status": validation,
        })  # fmt: skip
    (REPO / "configs" / "vendor_kb.yaml").write_text(
        "# Generated by scripts/build_vendor_kb.py. Do not edit by hand; no information is inferred.\n"
        + yaml.safe_dump(
            {"schema": "VT-VENDOR-KB-1", "entries": entries}, sort_keys=False, width=110
        )
    )
    lines = ["# Vendor / scanner knowledge base (VT-VENDOR-KB-1)", "",
             "Generated by `scripts/build_vendor_kb.py` -> `configs/vendor_kb.yaml`. Observed statistics come from census v2/v3 sampled headers; nothing is inferred. NOT_OBSERVED / NOT_RETRIEVED / NOT_DOCUMENTED mean exactly that.", "",
             "| Vendor | Model | Architecture | Public DICOM | Series sampled | Strict SUV pass | Height | Validation status |",
             "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for e in entries:
        o = e["observed_in_open_data"]
        lines.append(
            f"| {e['vendor']} | {e['model']} | {e['architecture']} | {e['public_dicom_availability']} | {o['series_sampled']} | {o['strict_suv_pass'] or '-'} | {o['height_present'] or '-'} | {e['validation_status']} |"
        )
    lines += ["", "## Documented private fields", ""]
    for v, fs in PRIVATE.items():
        for f in fs:
            lines.append(
                f"- **{v}** `{f['creator']}` {f['tag']}: {f['field']}: {f['status']} ({f['source']})"
            )
    lines += ["", "## Reconstruction fields present (observed)", ""]
    for e in entries:
        r = e["observed_in_open_data"]["reconstruction_fields_present"]
        if r:
            lines.append(f"- {e['vendor']} {e['model']}: {r}")
    (REPO / "docs" / "vendor_knowledge_base.md").write_text("\n".join(lines) + "\n")
    print(f"{len(entries)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
