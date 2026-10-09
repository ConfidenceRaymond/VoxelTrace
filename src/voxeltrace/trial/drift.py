"""Site / protocol drift over chronological scan order (reporting only; no rule reads this).

Per site, scans are ordered by acquisition date and consecutive protocol fingerprints
(VT-PROTOCOL-FP-1) are compared field by field. Every event cites the field, both values,
both trust levels and both scans (pseudonyms + dates). An evidence-availability change
(a field PRESENT in one scan and MISSING in the next) is UNKNOWN_PROTOCOL_DRIFT, never a
claimed protocol change. Uptake / injected-activity behaviour is summarised per site and
outliers are flagged with HEURISTIC thresholds (stated in every event; not rule thresholds).
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from typing import Any

from pydantic import BaseModel, Field

from voxeltrace.evidence.fingerprint import ProtocolFingerprint, _norm

DRIFT_SCHEMA = "VT-DRIFT-1"
EVENT_FOR_FIELD = {
    "manufacturer": "SCANNER_CHANGE",
    "scanner_model": "SCANNER_CHANGE",
    "software": "SOFTWARE_CHANGE",
    "reconstruction_method": "RECONSTRUCTION_CHANGE",
    "iterations": "RECONSTRUCTION_CHANGE",
    "subsets": "RECONSTRUCTION_CHANGE",
    "filter_kernel": "FILTER_CHANGE",
    "matrix": "MATRIX_CHANGE",
    "voxel_size_mm": "VOXEL_SIZE_CHANGE",
    "slice_thickness_mm": "VOXEL_SIZE_CHANGE",
    "time_of_flight": "TOF_CHANGE",
    "psf_resolution_modelling": "PSF_CHANGE",
    "corrections": "CORRECTION_CHANGE",
    "tracer": "TRACER_CHANGE",
    "units": "QUANTITATIVE_STATE_CHANGE",
    "decay_correction": "QUANTITATIVE_STATE_CHANGE",
    "harmonization": "HARMONIZATION_CHANGE",
}
UPTAKE_OUTLIER_MIN = 15.0  # heuristic, minutes from the site median
DOSE_OUTLIER_REL = 0.30  # heuristic, relative to the site median


class ScanRecord(BaseModel):
    site: str
    subject: str
    timepoint: str
    scan_pseudonym: str
    date: str | None = Field(default=None, description="ISO date (de-identified dates allowed)")
    fingerprint: ProtocolFingerprint


class DriftEvent(BaseModel):
    site: str
    event: str
    field: str
    previous_value: Any = None
    new_value: Any = None
    previous_trust: str
    new_trust: str
    previous_scan: str
    new_scan: str
    previous_date: str | None
    new_date: str | None
    heuristic: bool = False
    note: str = ""


class SiteDriftSummary(BaseModel):
    site: str
    scans: int
    undated_scans: int
    date_range: list[str | None]
    scanners: list[str]
    software_versions: list[str]
    distinct_protocol_fingerprints: int
    events: dict[str, int]
    uptake_min: dict[str, float | None]
    injected_MBq: dict[str, float | None]


class DriftReport(BaseModel):
    schema_version: str = DRIFT_SCHEMA
    events: list[DriftEvent]
    sites: list[SiteDriftSummary]
    note: str = "Reporting only; rule verdicts are unchanged. Heuristic outlier thresholds: uptake +/-15 min, activity +/-30 % from the site median."


def _v(fp: ProtocolFingerprint, f: str):
    x = fp.fields[f]
    return x.value if x.status == "PRESENT" else None


def _stats(vals: list[float]) -> dict[str, float | None]:
    if not vals:
        return {"median": None, "min": None, "max": None}
    return {
        "median": round(statistics.median(vals), 2),
        "min": round(min(vals), 2),
        "max": round(max(vals), 2),
    }


def detect_drift(scans: list[ScanRecord]) -> DriftReport:
    by_site: dict[str, list[ScanRecord]] = defaultdict(list)
    for s in scans:
        by_site[s.site].append(s)
    events: list[DriftEvent] = []
    summaries: list[SiteDriftSummary] = []
    for site, ss in sorted(by_site.items()):
        ordered = sorted(ss, key=lambda s: (s.date is None, s.date or "", s.subject, s.timepoint))
        for prev, cur in zip(ordered, ordered[1:], strict=False):
            seen: set[tuple[str, str]] = set()
            for f, ev in EVENT_FOR_FIELD.items():
                a, b = prev.fingerprint.fields[f], cur.fingerprint.fields[f]
                base = dict(site=site, field=f, previous_value=a.value, new_value=b.value,
                            previous_trust=a.trust, new_trust=b.trust,
                            previous_scan=prev.scan_pseudonym, new_scan=cur.scan_pseudonym,
                            previous_date=prev.date, new_date=cur.date)  # fmt: skip
                if a.status == "PRESENT" and b.status == "PRESENT":
                    if _norm(a.value) != _norm(b.value) and (ev, f) not in seen:
                        seen.add((ev, f))
                        events.append(DriftEvent(event=ev, **base))
                elif (a.status == "PRESENT") != (b.status == "PRESENT"):
                    events.append(DriftEvent(event="UNKNOWN_PROTOCOL_DRIFT", **base,
                                             note=f"evidence availability changed: {a.status} -> {b.status}"))  # fmt: skip
        upt = [(s, _v(s.fingerprint, "uptake_interval_s")) for s in ordered]
        dose = [(s, _v(s.fingerprint, "injected_activity_bq")) for s in ordered]
        u_vals = [u / 60 for _, u in upt if u is not None]
        d_vals = [d / 1e6 for _, d in dose if d is not None]
        if len(u_vals) >= 3:
            med = statistics.median(u_vals)
            for s, u in upt:
                if u is not None and abs(u / 60 - med) > UPTAKE_OUTLIER_MIN:
                    events.append(DriftEvent(site=site, event="UPTAKE_OUTLIER", field="uptake_interval_s",
                                             previous_value=round(med, 2), new_value=round(u / 60, 2),
                                             previous_trust="SITE_MEDIAN", new_trust=s.fingerprint.fields["uptake_interval_s"].trust,
                                             previous_scan="(site median)", new_scan=s.scan_pseudonym,
                                             previous_date=None, new_date=s.date, heuristic=True,
                                             note=f"|uptake - site median| > {UPTAKE_OUTLIER_MIN} min (heuristic)"))  # fmt: skip
        if len(d_vals) >= 3:
            med = statistics.median(d_vals)
            for s, d in dose:
                if d is not None and abs(d / 1e6 - med) > DOSE_OUTLIER_REL * med:
                    events.append(DriftEvent(site=site, event="DOSE_OUTLIER", field="injected_activity_bq",
                                             previous_value=round(med, 1), new_value=round(d / 1e6, 1),
                                             previous_trust="SITE_MEDIAN", new_trust=s.fingerprint.fields["injected_activity_bq"].trust,
                                             previous_scan="(site median)", new_scan=s.scan_pseudonym,
                                             previous_date=None, new_date=s.date, heuristic=True,
                                             note=f"> {DOSE_OUTLIER_REL:.0%} from the site median (heuristic)"))  # fmt: skip
        dates = [s.date for s in ordered if s.date]
        site_events = Counter(e.event for e in events if e.site == site)
        summaries.append(
            SiteDriftSummary(
                site=site,
                scans=len(ordered),
                undated_scans=sum(s.date is None for s in ordered),
                date_range=[min(dates) if dates else None, max(dates) if dates else None],
                scanners=sorted({f"{_v(s.fingerprint, 'manufacturer')} {_v(s.fingerprint, 'scanner_model')}" for s in ordered}),
                software_versions=sorted({str(_v(s.fingerprint, "software")) for s in ordered}),
                distinct_protocol_fingerprints=len({s.fingerprint.protocol_fingerprint_sha256 for s in ordered}),
                events=dict(site_events),
                uptake_min=_stats(u_vals),
                injected_MBq=_stats(d_vals),
            )
        )  # fmt: skip
    return DriftReport(events=events, sites=summaries)
