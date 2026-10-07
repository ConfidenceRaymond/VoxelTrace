"""Strict SUL (SUV normalised to lean body mass). SUVbw is NOT modified.

SUL = C_PET[Bq/mL] × LBM[g] / D_ref[Bq]  (D_ref = decay-corrected dose from strict SUVbw)
    = SUVbw × LBM / W

The LBM formula is chosen explicitly (DICOM SUV Type codes, PS3.3 C.8.9.1):
  LBMJAMES128  James, male multiplier 128 (QIBA FDG-PET/CT Profile v1.14 §4.4.2;
               Practical PERCIST, Radiology 2016;280:576):
                 male   = 1.10·W − 128·(W/H)²,  female = 1.07·W − 148·(W/H)²   (W kg, H cm)
               Undefined beyond its maximum (dLBM/dW = 0 at W* = a·H²/(2b)); refused there
               (Tahari et al. J Nucl Med 2014;55:1481: the formula peaks at BMI ≈ 43 / 37).
  LBMJANMA     Janmahasatian (EANM FDG guideline v2.0, EJNMMI 2015;42:328; Tahari 2014):
                 male   = 9270·W / (6680 + 216·BMI),  female = 9270·W / (8780 + 244·BMI)
               BMI = W / H²  (W kg, H m)
Inputs (DICOM PS3.3 C.7.2.2 / C.7.1.1): PatientSex (0010,0040) M|F, PatientSize (0010,1020)
in METRES, PatientWeight (0010,1030) kg. Missing or ambiguous inputs are REFUSED, never guessed
(e.g. a PatientSize > 3 is NOT reinterpreted as centimetres).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field
from pydicom.dataset import Dataset

from voxeltrace.ingest.dicom import _get
from voxeltrace.schemas import SUVResult

LBMFormula = Literal["LBMJAMES128", "LBMJANMA"]
FORMULA_SOURCES = {
    "LBMJAMES128": "James (male 128): QIBA FDG-PET/CT Profile v1.14 §4.4.2; Practical PERCIST "
    "(O, Lodge, Wahl. Radiology 2016;280:576-584)",
    "LBMJANMA": "Janmahasatian: EANM FDG PET/CT guideline v2.0 (Boellaard et al. EJNMMI "
    "2015;42:328-354); Tahari et al. J Nucl Med 2014;55:1481-4",
}
JAMES = {"M": (1.10, 128.0), "F": (1.07, 148.0)}
JANMA = {"M": (6680.0, 216.0), "F": (8780.0, 244.0)}


class SULRefusal(BaseModel):
    code: str
    message: str


class SULResult(BaseModel):
    status: Literal["PASS", "REFUSED"]
    formula: LBMFormula
    formula_source: str
    sex: str | None = None
    sex_source: str = "(0010,0040) PatientSex"
    height_m: float | None = None
    height_source: str = "(0010,1020) PatientSize [m]"
    weight_kg: float | None = None
    weight_source: str = "(0010,1030) PatientWeight [kg] (validated by strict SUVbw)"
    bmi: float | None = None
    lbm_kg: float | None = None
    sul_per_bqml: float | None = Field(default=None, description="g/Bq: LBM[g] / D_ref[Bq]")
    refusals: list[SULRefusal] = Field(default_factory=list)


def lbm_kg(formula: LBMFormula, sex: str, weight_kg: float, height_m: float) -> float:
    """Lean body mass in kg. Raises ValueError where the formula is invalid."""
    if sex not in ("M", "F"):
        raise ValueError("sex must be M or F")
    if formula == "LBMJAMES128":
        a, b = JAMES[sex]
        h_cm = height_m * 100.0
        w_peak = a * h_cm**2 / (2.0 * b)
        if weight_kg >= w_peak:
            raise ValueError(
                f"James formula invalid: weight {weight_kg} kg >= its maximum "
                f"{w_peak:.1f} kg for height {h_cm:.1f} cm"
            )
        lbm = a * weight_kg - b * (weight_kg / h_cm) ** 2
    else:
        c, d = JANMA[sex]
        bmi = weight_kg / height_m**2
        lbm = 9270.0 * weight_kg / (c + d * bmi)
    if not math.isfinite(lbm) or lbm <= 0:
        raise ValueError(f"non-positive LBM {lbm}")
    return lbm


def _consistent(headers: Sequence[Dataset], kw: str) -> tuple[str | None, bool]:
    vals = {str(_get(h, kw)).strip() for h in headers if _get(h, kw) is not None}
    vals.discard("")
    if not vals:
        return None, True
    return (next(iter(vals)) if len(vals) == 1 else None), len(vals) == 1


def compute_sul(suv: SUVResult, headers: Sequence[Dataset], formula: LBMFormula) -> SULResult:
    res = SULResult(
        status="REFUSED",
        formula=formula,
        formula_source=FORMULA_SOURCES[formula],
        weight_kg=suv.inputs.patient_weight_kg,
    )

    def refuse(code: str, msg: str) -> SULResult:
        res.refusals.append(SULRefusal(code=code, message=msg))
        return res

    sex, ok_sex = _consistent(headers, "PatientSex")
    size, ok_size = _consistent(headers, "PatientSize")
    if not ok_sex or not ok_size:
        return refuse("INCONSISTENT_ANTHROPOMETRICS", "sex or height differs between slices")
    if sex is None:
        return refuse("MISSING_PATIENTSEX", "PatientSex absent or empty")
    if sex not in ("M", "F"):
        return refuse("UNSUPPORTED_PATIENTSEX", f"PatientSex {sex!r}: formulas defined for M/F")
    res.sex = sex
    if size is None:
        return refuse("MISSING_PATIENTSIZE", "PatientSize (height) absent or empty")
    try:
        h = float(size)
    except ValueError:
        return refuse("INVALID_PATIENTSIZE", f"PatientSize {size!r} is not numeric")
    if not math.isfinite(h) or h <= 0:
        return refuse("INVALID_PATIENTSIZE", f"PatientSize {size!r} must be finite and > 0")
    if h > 3.0:
        return refuse(
            "AMBIGUOUS_PATIENTSIZE_UNIT",
            f"PatientSize {h} > 3: DICOM requires metres; not reinterpreted as cm",
        )
    if h < 0.5:
        return refuse("IMPLAUSIBLE_PATIENTSIZE", f"PatientSize {h} m < 0.5 m")
    res.height_m = h
    w = suv.inputs.patient_weight_kg
    if w is None:
        return refuse("MISSING_PATIENTWEIGHT", "validated weight unavailable")
    res.bmi = w / h**2
    try:
        res.lbm_kg = lbm_kg(formula, sex, w, h)
    except ValueError as exc:
        return refuse("LBM_FORMULA_INVALID", str(exc))
    res.sul_per_bqml = res.lbm_kg * 1000.0 / suv.scale.decayed_dose_bq
    res.status = "PASS"
    return res


def apply_sul(activity_bqml: np.ndarray, sul: SULResult) -> np.ndarray:
    if sul.status != "PASS" or sul.sul_per_bqml is None:
        raise ValueError("SUL refused")
    out = np.asarray(activity_bqml, dtype=np.float64) * sul.sul_per_bqml
    if not np.isfinite(out).all():
        raise ValueError("non-finite SUL")
    return out
