"""Claim-status parsing and accuracy."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

LABELS = (
    "PARTIALLY_SUPPORTED",
    "NOT_ESTABLISHED",
    "CONTRADICTED",
    "SUPPORTED",
    "INSUFFICIENT_INFORMATION",
    "COMPARABLE_WITH_WARNINGS",
    "NOT_COMPARABLE",
    "COMPARABLE",
)
_LABEL_RE = re.compile(
    r"(?<![A-Z])(" + "|".join(lab.replace("_", r"[ _-]") for lab in LABELS) + r")(?![A-Z])"
)


def parse_label(response: Any, key: str = "status") -> str | None:
    """Label from a JSON response (``key``) or the FIRST label token in free text."""
    if isinstance(response, dict):
        v = (
            response.get(key)
            or response.get("status")
            or response.get("answer")
            or response.get("category")
        )
        return str(v).upper() if v else None
    m = _LABEL_RE.search(str(response).upper())
    return re.sub(r"[ -]", "_", m.group(1)) if m else None


def confusion(pairs: list[tuple[str, str | None]]) -> dict[str, dict[str, int]]:
    out: dict[str, Counter] = {}
    for truth, pred in pairs:
        out.setdefault(truth, Counter())[pred or "UNPARSEABLE"] += 1
    return {k: dict(v) for k, v in out.items()}
