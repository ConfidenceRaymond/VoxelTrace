"""Numeric extraction and matching against evidence (deterministic)."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import Any

# Numbers not glued to identifiers (e.g. "seg1", "PETCT_0011f3deaf", "F18" are not numbers).
NUMBER_RE = re.compile(r"(?<![\w.])[-+]?(?:\d+\.\d+|\d+|\.\d+)(?:[eE][-+]?\d+)?(?![\w.])")
REL_TOL = 1e-3


def extract_numbers(text: str) -> list[str]:
    return [m.group(0) for m in NUMBER_RE.finditer(text)]


def numeric_leaves(obj: Any, path: str = "") -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    if isinstance(obj, bool) or obj is None:
        return out
    if isinstance(obj, int | float):
        if math.isfinite(obj):
            out.append((path, float(obj)))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out += numeric_leaves(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list | tuple):
        for i, v in enumerate(obj):
            out += numeric_leaves(v, f"{path}[{i}]")
    return out


def half_unit(text: str) -> float:
    try:
        exp = Decimal(text).as_tuple().exponent
    except InvalidOperation:
        return 0.0
    return 0.5 * 10.0 ** int(exp) if isinstance(exp, int) and exp < 0 else 0.5


def exact_match(text: str, reference: float) -> bool:
    """The stated number equals the reference rounded to the stated precision."""
    try:
        v = float(text)
    except ValueError:
        return False
    return v == reference or abs(v - reference) <= half_unit(text) * (1 + 1e-12)


def tolerance_match(value: float, reference: float, rel_tol: float = REL_TOL) -> bool:
    return abs(value - reference) <= rel_tol * max(abs(reference), 1e-12)


def invented_numbers(text: str, allowed: Iterable[float], *, rel_tol: float = REL_TOL) -> list[str]:
    """Numbers in ``text`` that match no allowed value (exactly at stated precision or within
    rel_tol). Integers 0-10 used as counts/indices are tolerated only if allowed explicitly."""
    refs = list(allowed)
    bad = []
    for s in extract_numbers(text):
        v = float(s)
        if not any(exact_match(s, r) or tolerance_match(v, r, rel_tol) for r in refs):
            bad.append(s)
    return bad


def _strings(obj: Any) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [x for v in obj.values() for x in _strings(v)] + [str(k) for k in obj]
    if isinstance(obj, list | tuple):
        return [x for v in obj for x in _strings(v)]
    return []


def allowed_numbers(*sources: Any) -> list[float]:
    """All numbers present in the supplied evidence/question/target (numeric leaves and
    numbers written inside strings)."""
    vals: list[float] = []
    for src in sources:
        vals += [v for _, v in numeric_leaves(src)]
        vals += [float(x) for s in _strings(src) for x in extract_numbers(s)]
    return vals
