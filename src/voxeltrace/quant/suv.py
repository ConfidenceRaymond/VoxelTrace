"""Strict, vendor-neutral body-weight SUV (SUVbw) for one supported DICOM path.

Supported path (everything else is REFUSED, never approximated):
    Units == BQML, DecayCorrection == START, CorrectedImage contains ATTN and DECY,
    exactly one radiopharmaceutical item, single-frame PET slices with valid geometry.

    SUVbw = C_PET[Bq/mL] * W[g] / (D_inj[Bq] * 2^(-Δt[s] / T½[s]))

    C_PET  = stored * RescaleSlope_k + RescaleIntercept_k   (per slice k; Units = BQML)
    W      = PatientWeight [kg] * 1000
    D_inj  = RadionuclideTotalDose [Bq]
    T½     = RadionuclideHalfLife [s]
    Δt     = T_ref - T_inj  (seconds)

Timing policy (see docs/quantification.md):
    T_inj  = RadiopharmaceuticalStartDateTime (DT) when present (must agree with
             RadiopharmaceuticalStartTime if that is also present). If only the TM is present,
             it is combined with the SeriesDate; if that places injection after T_ref, it is
             moved to the previous day (documented midnight rule, WARNING, provenance).
    T_ref  = the DICOM PET decay-correction reference for START, i.e. Series Date/Time,
             accepted ONLY when cross-validated against acquisition timing:
               (a) |SeriesDateTime − earliest AcquisitionDateTime| ≤ 1 s, or
               (b) SeriesDateTime < earliest AcquisitionDateTime and every slice's
                   FrameReferenceTime confirms offsets from SeriesDateTime.
             SeriesDateTime later than the earliest acquisition (post-processed series)
             or any other disagreement is REFUSED. Series Time is never a silent fallback.
"""

from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pydicom
from pydicom.dataset import Dataset

import voxeltrace
from voxeltrace.config import REPO_ROOT
from voxeltrace.ingest.dicom import (
    IngestError,
    LoadedVolume,
    _floats,
    _get,
    _str,
    load_series_volume,
    ordered_instances,
)
from voxeltrace.quant.dicom_time import (
    DicomTimeError,
    combine_da_tm,
    parse_da,
    parse_dt,
    parse_tm,
    parse_utc_offset,
)
from voxeltrace.quant.image_stats import compute_image_stats
from voxeltrace.schemas import (
    CheckResult,
    ImagingSeries,
    QCWarning,
    QuantField,
    QuantitativeProvenance,
    RescaleAudit,
    SUVInputs,
    SUVRefusal,
    SUVRefusalReason,
    SUVResult,
    SUVScaleFactors,
    SUVValidation,
)

CALCULATION_VERSION = "suvbw-strict-1"
LN2 = math.log(2.0)

# Plausibility gates. Values outside the REFUSE ranges are treated as unit/entry errors.
WEIGHT_REFUSE_KG = (1.0, 500.0)
WEIGHT_WARN_KG = (20.0, 300.0)
DOSE_REFUSE_BQ = (1.0e6, 1.0e11)
F18_HALF_LIFE_S = (6570.0, 6600.0)  # nominal 109.77 min = 6586.2 s
MAX_DECAY_INTERVAL_S = 12 * 3600.0
SHORT_DECAY_INTERVAL_S = 60.0
SERIES_ACQ_TOLERANCE_S = 1.0
DECAY_FACTOR_REL_TOL = 1.0e-3

F18_CODES = {"C-111A1", "77004003", "126T"}

ASSUMPTIONS = [
    "PatientWeight interpreted in kg, RadionuclideTotalDose in Bq, RadionuclideHalfLife in s, "
    "as defined by DICOM PS3.3; values outside plausibility gates are refused, not rescaled.",
    "Activity concentration = stored value × RescaleSlope + RescaleIntercept per slice, in "
    "Bq/mL (Units=BQML). No other scaling or private vendor factor is applied.",
    "For DecayCorrection=START, image activity is decay-corrected to the PET Series Date/Time "
    "(DICOM PET Series module); this reference is used only when cross-validated against "
    "acquisition timing.",
    "SUVbw uses total body weight; SUV is reported in g/mL (numerically unitless if tissue "
    "density is taken as 1 g/mL).",
    "No CT-derived information is used.",
]
REFERENCES = [
    "DICOM PS3.3 C.8.9 (PET Series/Image, Radiopharmaceutical Information)",
    "QIBA FDG-PET/CT Profile and vendor-neutral SUV pseudo-code (Kinahan et al.)",
]


@dataclass
class _Ctx:
    checks: list[CheckResult]
    reasons: list[SUVRefusalReason]
    warnings: list[QCWarning]
    series_uid: str

    def ok(self, name: str, detail: str) -> None:
        self.checks.append(CheckResult(name=name, passed=True, detail=detail))

    def refuse(self, name: str, code: str, message: str, field: str | None = None) -> None:
        self.checks.append(CheckResult(name=name, passed=False, detail=message))
        self.reasons.append(SUVRefusalReason(code=code, message=message, field=field))

    def warn(self, code: str, message: str) -> None:
        self.warnings.append(QCWarning(code=code, message=message, series_uid=self.series_uid))


# --------------------------------------------------------------------------------------
# Pure computation (oracle-tested)
# --------------------------------------------------------------------------------------


def suv_scale_factors(
    weight_kg: float, dose_bq: float, half_life_s: float, decay_interval_s: float
) -> SUVScaleFactors:
    """SUVbw multiplier for Bq/mL. Raises ValueError on non-finite or non-physical inputs."""
    for name, v in (("weight", weight_kg), ("dose", dose_bq), ("half-life", half_life_s)):
        if not math.isfinite(v) or v <= 0:
            raise ValueError(f"{name} must be finite and > 0, got {v}")
    if not math.isfinite(decay_interval_s) or decay_interval_s < 0:
        raise ValueError(f"decay interval must be finite and >= 0, got {decay_interval_s}")
    decay = math.exp(-LN2 * decay_interval_s / half_life_s)
    decayed = dose_bq * decay
    weight_g = weight_kg * 1000.0
    factor = weight_g / decayed
    if not (math.isfinite(decay) and math.isfinite(decayed) and math.isfinite(factor)):
        raise ValueError("non-finite intermediate in SUV scale factor")
    return SUVScaleFactors(
        patient_weight_g=weight_g,
        injected_dose_bq=dose_bq,
        half_life_s=half_life_s,
        decay_interval_s=decay_interval_s,
        dose_decay_factor=decay,
        decayed_dose_bq=decayed,
        suv_per_bqml=factor,
    )


def apply_suv(activity_bqml: np.ndarray, scale: SUVScaleFactors) -> np.ndarray:
    """New float64 SUV array; the input array is not modified."""
    suv = np.asarray(activity_bqml, dtype=np.float64) * scale.suv_per_bqml
    if not np.isfinite(suv).all():
        raise ValueError("non-finite SUV values")
    return suv


# --------------------------------------------------------------------------------------
# Header audit
# --------------------------------------------------------------------------------------

_CONSTANT_FIELDS: list[tuple[str, str, str | None]] = [
    ("Units", "(0054,1001)", None),
    ("DecayCorrection", "(0054,1102)", None),
    ("CorrectedImage", "(0028,0051)", None),
    ("PatientWeight", "(0010,1030)", "kg"),
    ("SeriesDate", "(0008,0021)", None),
    ("SeriesTime", "(0008,0031)", None),
    ("TimezoneOffsetFromUTC", "(0008,0201)", None),
]
_RP_FIELDS: list[tuple[str, str, str | None]] = [
    ("Radiopharmaceutical", "(0018,0031)", None),
    ("RadionuclideTotalDose", "(0018,1074)", "Bq"),
    ("RadionuclideHalfLife", "(0018,1075)", "s"),
    ("RadiopharmaceuticalStartTime", "(0018,1072)", None),
    ("RadiopharmaceuticalStartDateTime", "(0018,1078)", None),
]
_PER_SLICE_FIELDS: list[tuple[str, str, str | None]] = [
    ("AcquisitionDate", "(0008,0022)", None),
    ("AcquisitionTime", "(0008,0032)", None),
    ("AcquisitionDateTime", "(0008,002A)", None),
    ("FrameReferenceTime", "(0054,1300)", "ms"),
    ("DecayFactor", "(0054,1321)", None),
    ("ActualFrameDuration", "(0018,1242)", "ms"),
    ("RescaleSlope", "(0028,1053)", None),
    ("RescaleIntercept", "(0028,1052)", None),
]


def _raw(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list | tuple | pydicom.multival.MultiValue):
        return "\\".join(str(v) for v in value)
    s = str(value).strip()
    return s or None


def _rp_item(ds: Dataset) -> tuple[Dataset | None, int]:
    seq = _get(ds, "RadiopharmaceuticalInformationSequence")
    return (seq[0] if seq else None), (len(seq) if seq else 0)


def _field(name: str, tag: str, unit: str | None, values: list[str | None]) -> QuantField:
    present = [v for v in values if v is not None]
    distinct: list[str] = []
    for v in present:
        if v not in distinct:
            distinct.append(v)
    return QuantField(
        name=name,
        tag=tag,
        value=values[0] if values else None,
        unit=unit,
        slices_present=len(present),
        slices_total=len(values),
        distinct_values=distinct[:5],
        n_distinct=len(distinct),
    )


@dataclass
class PETHeaderAudit:
    series_uid: str
    headers: list[Dataset]
    fields: dict[str, QuantField]

    def per_slice(self, keyword: str) -> list[Any]:
        return [_get(h, keyword) for h in self.headers]

    def rp_per_slice(self, keyword: str) -> list[Any]:
        return [
            _get(item, keyword) if item is not None else None
            for item in (_rp_item(h)[0] for h in self.headers)
        ]


def audit_pet_headers(series: ImagingSeries) -> PETHeaderAudit:
    """Read every PET slice header in geometric order and summarise quantitative fields."""
    insts = ordered_instances(series)
    headers = [pydicom.dcmread(i.path, stop_before_pixels=True) for i in insts]
    fields: dict[str, QuantField] = {}
    for name, tag, unit in _CONSTANT_FIELDS + _PER_SLICE_FIELDS:
        fields[name] = _field(name, tag, unit, [_raw(_get(h, name)) for h in headers])
    for name, tag, unit in _RP_FIELDS:
        vals = []
        for h in headers:
            item, _ = _rp_item(h)
            vals.append(_raw(_get(item, name)) if item is not None else None)
        fields[name] = _field(name, tag, unit, vals)
    fields["RadiopharmaceuticalInformationSequence.items"] = _field(
        "RadiopharmaceuticalInformationSequence.items",
        "(0054,0016)",
        None,
        [str(_rp_item(h)[1]) for h in headers],
    )
    codes = []
    for h in headers:
        item, _ = _rp_item(h)
        seq = _get(item, "RadionuclideCodeSequence") if item is not None else None
        codes.append(
            f"{_str(_get(seq[0], 'CodeValue'))}|{_str(_get(seq[0], 'CodeMeaning'))}"
            if seq
            else None
        )
    fields["RadionuclideCodeSequence"] = _field(
        "RadionuclideCodeSequence", "(0054,0300)", None, codes
    )
    return PETHeaderAudit(series.series_uid, headers, fields)


# --------------------------------------------------------------------------------------
# Eligibility
# --------------------------------------------------------------------------------------


def _positive(ctx: _Ctx, name: str, raw: str | None, unit: str) -> float | None:
    if raw is None:
        ctx.refuse(name, f"MISSING_{name.upper()}", f"{name} is absent", name)
        return None
    try:
        v = float(raw)
    except ValueError:
        v = math.nan
    if not math.isfinite(v):
        ctx.refuse(name, f"INVALID_{name.upper()}", f"{name} {raw!r} is not a finite number", name)
        return None
    if v <= 0:
        ctx.refuse(name, f"NONPOSITIVE_{name.upper()}", f"{name} {raw!r} must be > 0 {unit}", name)
        return None
    return v


def _is_f18(code_field: QuantField, rp_name: str | None) -> bool | None:
    if code_field.value:
        code, _, meaning = code_field.value.partition("|")
        return code in F18_CODES or ("18" in meaning and "fluor" in meaning.lower())
    if rp_name and ("fluorodeoxyglucose" in rp_name.lower() or "fdg" in rp_name.lower()):
        return True
    return None


def validate_suv_eligibility(audit: PETHeaderAudit) -> tuple[SUVValidation, SUVInputs]:
    ctx = _Ctx([], [], [], audit.series_uid)
    f = audit.fields
    inputs = SUVInputs(fields=list(f.values()))
    n = len(audit.headers)

    # 1. Constant-per-series fields must be identical across all slices.
    must_be_constant = [
        "Units",
        "DecayCorrection",
        "CorrectedImage",
        "PatientWeight",
        "SeriesDate",
        "SeriesTime",
        "TimezoneOffsetFromUTC",
        "Radiopharmaceutical",
        "RadionuclideTotalDose",
        "RadionuclideHalfLife",
        "RadiopharmaceuticalStartTime",
        "RadiopharmaceuticalStartDateTime",
        "RadiopharmaceuticalInformationSequence.items",
        "RadionuclideCodeSequence",
    ]
    inconsistent = [
        k for k in must_be_constant if f[k].n_distinct > 1 or 0 < f[k].slices_present < n
    ]
    for k in inconsistent:
        ctx.refuse(
            "per-slice consistency",
            f"INCONSISTENT_{k.upper().replace('.', '_')}",
            f"{k} differs or is missing between slices: {f[k].distinct_values}",
            k,
        )
    if not inconsistent:
        ctx.ok(
            "per-slice consistency",
            f"{len(must_be_constant)} series-level fields identical across {n} slices",
        )

    # 2. Units.
    units = f["Units"].value
    inputs.units = units
    if units is None:
        ctx.refuse("Units", "MISSING_UNITS", "Units is absent", "Units")
    elif units != "BQML":
        ctx.refuse(
            "Units", "UNSUPPORTED_UNITS", f"Units {units!r} not supported (only BQML)", "Units"
        )
    else:
        ctx.ok("Units", "BQML")

    # 3. Decay correction state.
    dc = f["DecayCorrection"].value
    inputs.decay_correction = dc
    if dc is None:
        ctx.refuse(
            "DecayCorrection",
            "MISSING_DECAYCORRECTION",
            "DecayCorrection is absent",
            "DecayCorrection",
        )
    elif dc != "START":
        ctx.refuse(
            "DecayCorrection",
            "UNSUPPORTED_DECAY_CORRECTION",
            f"DecayCorrection {dc!r} not implemented (only START)",
            "DecayCorrection",
        )
    else:
        ctx.ok("DecayCorrection", "START")

    # 4. Corrections.
    ci = f["CorrectedImage"].value
    corrections = ci.split("\\") if ci else []
    inputs.corrected_image = corrections or None
    missing_corr = [c for c in ("ATTN", "DECY") if c not in corrections]
    if missing_corr:
        ctx.refuse(
            "CorrectedImage",
            "MISSING_CORRECTION",
            f"CorrectedImage {corrections} lacks {missing_corr}",
            "CorrectedImage",
        )
    else:
        ctx.ok("CorrectedImage", f"{corrections} includes ATTN and DECY")
        absent_opt = [c for c in ("SCAT", "RAN", "DTIM", "NORM") if c not in corrections]
        if absent_opt:
            ctx.warn("CORRECTIONS_NOT_DECLARED", f"CorrectedImage does not list {absent_opt}")

    # 5. Radiopharmaceutical item count.
    items = f["RadiopharmaceuticalInformationSequence.items"].value
    if items != "1":
        ctx.refuse(
            "Radiopharmaceutical items",
            "RADIOPHARMACEUTICAL_ITEMS",
            f"expected exactly 1 RadiopharmaceuticalInformationSequence item, got {items}",
        )
    else:
        ctx.ok("Radiopharmaceutical items", "exactly one item")

    # 6. Weight.
    w = _positive(ctx, "PatientWeight", f["PatientWeight"].value, "kg")
    if w is not None:
        if not WEIGHT_REFUSE_KG[0] <= w <= WEIGHT_REFUSE_KG[1]:
            ctx.refuse(
                "PatientWeight",
                "IMPLAUSIBLE_PATIENTWEIGHT",
                f"PatientWeight {w} kg outside {WEIGHT_REFUSE_KG} (unit error?)",
                "PatientWeight",
            )
        else:
            inputs.patient_weight_kg = w
            ctx.ok("PatientWeight", f"{w} kg")
            if not WEIGHT_WARN_KG[0] <= w <= WEIGHT_WARN_KG[1]:
                ctx.warn("UNUSUAL_PATIENTWEIGHT", f"PatientWeight {w} kg outside {WEIGHT_WARN_KG}")

    # 7. Dose.
    d = _positive(ctx, "RadionuclideTotalDose", f["RadionuclideTotalDose"].value, "Bq")
    if d is not None:
        if not DOSE_REFUSE_BQ[0] <= d <= DOSE_REFUSE_BQ[1]:
            ctx.refuse(
                "RadionuclideTotalDose",
                "IMPLAUSIBLE_RADIONUCLIDETOTALDOSE",
                f"RadionuclideTotalDose {d} Bq outside {DOSE_REFUSE_BQ} (unit error?)",
                "RadionuclideTotalDose",
            )
        else:
            inputs.radionuclide_total_dose_bq = d
            ctx.ok("RadionuclideTotalDose", f"{d} Bq")

    # 8. Half-life and radionuclide.
    t_half = _positive(ctx, "RadionuclideHalfLife", f["RadionuclideHalfLife"].value, "s")
    inputs.radionuclide = f["RadionuclideCodeSequence"].value or f["Radiopharmaceutical"].value
    if t_half is not None:
        f18 = _is_f18(f["RadionuclideCodeSequence"], f["Radiopharmaceutical"].value)
        if f18 is True and not F18_HALF_LIFE_S[0] <= t_half <= F18_HALF_LIFE_S[1]:
            ctx.refuse(
                "RadionuclideHalfLife",
                "HALF_LIFE_RADIONUCLIDE_MISMATCH",
                f"half-life {t_half} s inconsistent with F-18 {F18_HALF_LIFE_S}",
                "RadionuclideHalfLife",
            )
        else:
            inputs.radionuclide_half_life_s = t_half
            ctx.ok(
                "RadionuclideHalfLife", f"{t_half} s" + (" (consistent with F-18)" if f18 else "")
            )
            if f18 is None:
                ctx.warn(
                    "RADIONUCLIDE_UNIDENTIFIED",
                    "radionuclide not identified; half-life not cross-checked",
                )

    # 9-11. Timing.
    _validate_timing(ctx, audit, inputs, t_half)

    # 12. Per-slice rescale factors.
    slopes = [_floats(v, 1) for v in audit.per_slice("RescaleSlope")]
    inters = [_floats(v, 1) for v in audit.per_slice("RescaleIntercept")]
    bad = [k for k, (s, b) in enumerate(zip(slopes, inters, strict=True)) if s is None or b is None]
    nonpos = [k for k, s in enumerate(slopes) if s is not None and s[0] <= 0]
    if bad:
        ctx.refuse(
            "Rescale",
            "MISSING_RESCALE",
            f"RescaleSlope/Intercept absent or invalid on {len(bad)} slice(s), e.g. k={bad[:5]}",
        )
    elif nonpos:
        ctx.refuse(
            "Rescale", "NONPOSITIVE_RESCALE_SLOPE", f"RescaleSlope <= 0 on slice(s) k={nonpos[:5]}"
        )
    else:
        ctx.ok(
            "Rescale",
            f"finite slope/intercept on all {n} slices "
            f"({f['RescaleSlope'].n_distinct} distinct slopes, applied per slice)",
        )

    return SUVValidation(
        eligible=not ctx.reasons, checks=ctx.checks, reasons=ctx.reasons, warnings=ctx.warnings
    ), inputs


def _validate_timing(
    ctx: _Ctx, audit: PETHeaderAudit, inputs: SUVInputs, t_half: float | None
) -> None:
    f = audit.fields
    tz_raw = f["TimezoneOffsetFromUTC"].value
    try:
        tz = parse_utc_offset(tz_raw) if tz_raw else None
    except DicomTimeError as exc:
        ctx.refuse("Timezone", "INVALID_TIMEZONE", str(exc), "TimezoneOffsetFromUTC")
        return

    # Series reference datetime.
    try:
        series_dt = combine_da_tm(f["SeriesDate"].value, f["SeriesTime"].value)
    except DicomTimeError as exc:
        ctx.refuse(
            "Series datetime", "INVALID_SERIES_DATETIME", f"SeriesDate/Time: {exc}", "SeriesTime"
        )
        return
    inputs.series_datetime = series_dt.isoformat()

    # Earliest acquisition datetime over all slices.
    acq: list[datetime] = []
    acq_source = None
    for h in audit.headers:
        try:
            if _get(h, "AcquisitionDateTime") is not None:
                acq.append(parse_dt(_get(h, "AcquisitionDateTime")))
                acq_source = "AcquisitionDateTime (0008,002A)"
            else:
                acq.append(combine_da_tm(_get(h, "AcquisitionDate"), _get(h, "AcquisitionTime")))
                acq_source = "AcquisitionDate (0008,0022) + AcquisitionTime (0008,0032)"
        except DicomTimeError as exc:
            ctx.refuse(
                "Acquisition datetime",
                "INVALID_ACQUISITION_DATETIME",
                f"slice acquisition timing invalid: {exc}",
                "AcquisitionTime",
            )
            return
    if any(a.tzinfo is not None for a in acq):
        ctx.refuse(
            "Acquisition datetime",
            "TIMEZONE_AMBIGUOUS",
            "AcquisitionDateTime carries a UTC offset; mixed-zone timing not supported",
        )
        return
    acq_min = min(acq)
    inputs.earliest_acquisition_datetime = acq_min.isoformat()

    # Decay-correction reference (START).
    gap = (acq_min - series_dt).total_seconds()
    if abs(gap) <= SERIES_ACQ_TOLERANCE_S:
        ref, ref_src = (
            series_dt,
            (
                "SeriesDate/SeriesTime (PET decay reference for START), concordant within "
                f"{SERIES_ACQ_TOLERANCE_S:g} s with earliest {acq_source}"
            ),
        )
    elif gap < 0:
        ctx.refuse(
            "Scan reference time",
            "SERIES_TIME_AFTER_ACQUISITION",
            f"SeriesDateTime is {-gap:.3f} s after the earliest acquisition "
            "(post-processed series time?); decay reference ambiguous",
        )
        return
    else:
        if not _frame_reference_confirms(audit, series_dt, acq):
            ctx.refuse(
                "Scan reference time",
                "SCAN_REFERENCE_AMBIGUOUS",
                f"SeriesDateTime precedes the earliest acquisition by {gap:.3f} s and "
                "FrameReferenceTime does not confirm it as the decay reference",
            )
            return
        ref, ref_src = (
            series_dt,
            (
                "SeriesDate/SeriesTime (PET decay reference for START), confirmed by per-slice "
                "FrameReferenceTime offsets"
            ),
        )
        ctx.warn(
            "SERIES_PRECEDES_ACQUISITION",
            f"SeriesDateTime precedes earliest acquisition by {gap:.3f} s; "
            "accepted via FrameReferenceTime",
        )
    inputs.scan_reference_datetime = ref.isoformat()
    inputs.scan_reference_datetime_source = ref_src
    ctx.ok("Scan reference time", f"{ref.isoformat()} from {ref_src}")

    # Injection datetime.
    dt_raw = f["RadiopharmaceuticalStartDateTime"].value
    tm_raw = f["RadiopharmaceuticalStartTime"].value
    inj: datetime | None = None
    try:
        if dt_raw:
            inj = parse_dt(dt_raw)
            src = "RadiopharmaceuticalStartDateTime (0018,1078)"
            if tm_raw:
                tm = parse_tm(tm_raw)
                if tm != inj.timetz().replace(tzinfo=None):
                    ctx.refuse(
                        "Injection datetime",
                        "INJECTION_TIME_CONFLICT",
                        f"RadiopharmaceuticalStartDateTime {dt_raw} disagrees with "
                        f"RadiopharmaceuticalStartTime {tm_raw}",
                    )
                    return
                src += ", agrees with RadiopharmaceuticalStartTime (0018,1072)"
            if inj.tzinfo is not None:
                if tz is None:
                    ctx.refuse(
                        "Injection datetime",
                        "TIMEZONE_AMBIGUOUS",
                        "injection DT has a UTC offset but the series has no TimezoneOffsetFromUTC",
                    )
                    return
                inj = inj.astimezone(tz).replace(tzinfo=None)
                src += " (converted to the series timezone offset)"
        elif tm_raw:
            tm = parse_tm(tm_raw)
            inj = datetime.combine(parse_da(f["SeriesDate"].value), tm)
            src = "RadiopharmaceuticalStartTime (0018,1072) + SeriesDate (0008,0021)"
            if inj > ref:
                inj -= timedelta(days=1)
                src += "; injection moved to previous day (midnight rule)"
                ctx.warn(
                    "INJECTION_DATE_ROLLOVER",
                    "injection TM later than scan reference on SeriesDate; assumed the "
                    "previous day (documented midnight rule)",
                )
            else:
                ctx.warn(
                    "INJECTION_DATE_FROM_SERIES",
                    "RadiopharmaceuticalStartDateTime absent; injection date taken from "
                    "SeriesDate (documented rule)",
                )
        else:
            ctx.refuse(
                "Injection datetime",
                "MISSING_INJECTION_TIME",
                "neither RadiopharmaceuticalStartDateTime nor ...StartTime present",
            )
            return
    except DicomTimeError as exc:
        ctx.refuse(
            "Injection datetime", "INVALID_INJECTION_TIME", str(exc), "RadiopharmaceuticalStartTime"
        )
        return
    inputs.injection_datetime = inj.isoformat()
    inputs.injection_datetime_source = src
    ctx.ok("Injection datetime", f"{inj.isoformat()} from {src}")

    # Interval.
    delta = (ref - inj).total_seconds()
    if delta < 0:
        ctx.refuse(
            "Decay interval",
            "NEGATIVE_DECAY_INTERVAL",
            f"injection is {-delta:.3f} s after the scan reference time",
        )
        return
    if delta > MAX_DECAY_INTERVAL_S:
        ctx.refuse(
            "Decay interval",
            "IMPLAUSIBLE_DECAY_INTERVAL",
            f"decay interval {delta:.1f} s exceeds {MAX_DECAY_INTERVAL_S:.0f} s",
        )
        return
    if delta < SHORT_DECAY_INTERVAL_S:
        ctx.warn("SHORT_DECAY_INTERVAL", f"decay interval only {delta:.3f} s (dynamic scan?)")
    inputs.decay_interval_s = delta
    ctx.ok("Decay interval", f"{delta:.6f} s")

    # Optional independent check: vendor DecayFactor vs FrameReferenceTime and half-life.
    if t_half is not None:
        _check_decay_factor(ctx, audit, t_half)


def _frame_reference_confirms(
    audit: PETHeaderAudit, series_dt: datetime, acq: list[datetime]
) -> bool:
    frts = [_floats(v, 1) for v in audit.per_slice("FrameReferenceTime")]
    durs = [_floats(v, 1) for v in audit.per_slice("ActualFrameDuration")]
    if any(v is None for v in frts) or any(v is None for v in durs):
        return False
    for a, frt, dur in zip(acq, frts, durs, strict=True):
        offset = frt[0] / 1000.0 - (a - series_dt).total_seconds()  # type: ignore[index]
        if not -1.0 <= offset <= dur[0] / 1000.0 + 1.0:  # type: ignore[index]
            return False
    return True


def _check_decay_factor(ctx: _Ctx, audit: PETHeaderAudit, t_half: float) -> None:
    frts = [_floats(v, 1) for v in audit.per_slice("FrameReferenceTime")]
    dfs = [_floats(v, 1) for v in audit.per_slice("DecayFactor")]
    if any(v is None for v in frts + dfs):
        ctx.warn(
            "DECAY_FACTOR_UNVERIFIED",
            "FrameReferenceTime/DecayFactor not on every slice; vendor decay not checked",
        )
        return
    worst = max(
        abs(2 ** (fr[0] / 1000.0 / t_half) / df[0] - 1.0)  # type: ignore[index]
        for fr, df in zip(frts, dfs, strict=True)
    )
    if worst > DECAY_FACTOR_REL_TOL:
        ctx.refuse(
            "Vendor decay factor",
            "DECAY_FACTOR_INCONSISTENT",
            f"DecayFactor deviates from 2^(FrameReferenceTime/T½) by {worst:.2e} "
            "(relative); vendor decay reference or half-life differs",
        )
    else:
        ctx.ok(
            "Vendor decay factor",
            f"DecayFactor = 2^(FrameReferenceTime/T½) on every slice "
            f"(max relative deviation {worst:.2e})",
        )


# --------------------------------------------------------------------------------------
# End-to-end
# --------------------------------------------------------------------------------------


def git_state() -> tuple[str | None, bool | None]:
    try:
        sha = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            ).stdout.strip()
        )
        return sha, dirty
    except (OSError, subprocess.SubprocessError):
        return None, None


def make_provenance(
    pet_series_uid: str | None, dataset: str | None, subject: str | None
) -> QuantitativeProvenance:
    sha, dirty = git_state()
    return QuantitativeProvenance(
        calculation="SUVbw (strict DICOM BQML/START path)",
        calculation_version=CALCULATION_VERSION,
        voxeltrace_version=voxeltrace.__version__,
        git_commit=sha,
        git_dirty=dirty,
        computed_at=datetime.now(UTC).isoformat(timespec="seconds"),
        dataset=dataset,
        subject_pseudonym=subject,
        pet_series_uid=pet_series_uid,
        assumptions=list(ASSUMPTIONS),
        references=list(REFERENCES),
    )


def rescale_audit(vol: LoadedVolume) -> RescaleAudit:
    slopes = [s for s in vol.slice_rescale_slopes if s is not None]
    inters: list[float] = []
    for b in vol.slice_rescale_intercepts:
        if b is not None and b not in inters:
            inters.append(b)
    return RescaleAudit(
        n_slices=len(vol.slice_rescale_slopes),
        n_distinct_slopes=len(set(slopes)),
        slope_min=min(slopes) if slopes else None,
        slope_max=max(slopes) if slopes else None,
        n_distinct_intercepts=len(inters),
        intercepts=inters[:5],
        per_slice=[
            (k, uid, s, b)
            for k, (uid, s, b) in enumerate(
                zip(
                    vol.slice_sop_instance_uids,
                    vol.slice_rescale_slopes,
                    vol.slice_rescale_intercepts,
                    strict=True,
                )
            )
        ],
    )


@dataclass
class SUVOutcome:
    """``result`` + ``suv`` on PASS; ``refusal`` otherwise. ``activity`` is never modified."""

    audit: PETHeaderAudit
    result: SUVResult | None
    refusal: SUVRefusal | None
    suv: np.ndarray | None
    activity: LoadedVolume | None


def compute_suv_for_series(
    series: ImagingSeries, *, dataset: str | None = None, subject: str | None = None
) -> SUVOutcome:
    prov = make_provenance(series.series_uid, dataset, subject)
    if series.category != "PET":
        raise ValueError(f"series {series.series_uid} is not PET")
    try:
        audit = audit_pet_headers(series)
    except IngestError as exc:
        reason = SUVRefusalReason(code="GEOMETRY", message=str(exc))
        val = SUVValidation(eligible=False, reasons=[reason])
        return SUVOutcome(
            PETHeaderAudit(series.series_uid, [], {}),
            None,
            SUVRefusal(reasons=[reason], validation=val, inputs=SUVInputs(), provenance=prov),
            None,
            None,
        )
    validation, inputs = validate_suv_eligibility(audit)
    if not validation.eligible:
        return SUVOutcome(
            audit,
            None,
            SUVRefusal(
                reasons=validation.reasons, validation=validation, inputs=inputs, provenance=prov
            ),
            None,
            None,
        )

    def refuse(code: str, msg: str) -> SUVOutcome:
        r = SUVRefusalReason(code=code, message=msg)
        validation.eligible = False
        validation.reasons.append(r)
        return SUVOutcome(
            audit,
            None,
            SUVRefusal(
                reasons=validation.reasons, validation=validation, inputs=inputs, provenance=prov
            ),
            None,
            None,
        )

    try:
        vol = load_series_volume(series)
    except IngestError as exc:
        return refuse("PIXELS_NOT_LOADED", str(exc))
    if not vol.rescaled:
        return refuse("MISSING_RESCALE", "volume loaded without rescale on some slices")
    header_slopes = [_floats(v, 1) for v in audit.per_slice("RescaleSlope")]
    header_inters = [_floats(v, 1) for v in audit.per_slice("RescaleIntercept")]
    if [s[0] for s in header_slopes] != vol.slice_rescale_slopes or [
        b[0] for b in header_inters
    ] != vol.slice_rescale_intercepts:  # type: ignore[index]
        return refuse(
            "RESCALE_AUDIT_MISMATCH",
            "per-slice rescale factors used for pixels differ from audited headers",
        )
    assert inputs.patient_weight_kg and inputs.radionuclide_total_dose_bq
    assert inputs.radionuclide_half_life_s and inputs.decay_interval_s is not None
    try:
        scale = suv_scale_factors(
            inputs.patient_weight_kg,
            inputs.radionuclide_total_dose_bq,
            inputs.radionuclide_half_life_s,
            inputs.decay_interval_s,
        )
        suv = apply_suv(vol.array, scale)
    except ValueError as exc:
        return refuse("NONFINITE_SUV", str(exc))
    stats = compute_image_stats(suv)
    if stats.finite_min is not None and stats.finite_min < 0:
        validation.warnings.append(
            QCWarning(
                code="NEGATIVE_SUV",
                series_uid=series.series_uid,
                message=f"{int((suv < 0).sum())} voxels with SUV < 0 (reconstruction/intercept)",
            )
        )
    result = SUVResult(
        inputs=inputs,
        scale=scale,
        validation=validation,
        rescale=rescale_audit(vol),
        volume_shape_kji=suv.shape,  # type: ignore[arg-type]
        suv_stats=stats,
        provenance=prov,
    )
    return SUVOutcome(audit, result, None, suv, vol)
