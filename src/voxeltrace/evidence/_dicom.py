"""Shared helpers: read standard DICOM attributes into EvidenceFields. No private tags."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import pydicom
from pydicom.datadict import tag_for_keyword
from pydicom.dataset import Dataset

from voxeltrace.ingest.dicom import _get
from voxeltrace.schemas import Derivation, EvidenceField, ImagingSeries


def read_headers(series: ImagingSeries) -> list[Dataset]:
    return [pydicom.dcmread(i.path, stop_before_pixels=True) for i in series.instances]


def tag_label(keyword: str) -> str:
    t = tag_for_keyword(keyword)
    return f"({t >> 16:04X},{t & 0xFFFF:04X}) {keyword}" if t is not None else keyword


def _raw(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, list | tuple | pydicom.multival.MultiValue):
        s = "\\".join(str(x) for x in v)
    else:
        s = str(v)
    s = s.strip()
    return s or None


def _to_int(s: str) -> int:
    f = float(s)
    if not f.is_integer():
        raise ValueError(s)
    return int(f)


KINDS: dict[str, Callable[[str], Any]] = {
    "str": str,
    "float": float,
    "int": _to_int,
    "list": lambda s: [x for x in s.split("\\") if x],
    "floatlist": lambda s: [float(x) for x in s.split("\\") if x],
}


def tag_field(
    headers: Sequence[Dataset],
    keyword: str,
    *,
    name: str | None = None,
    kind: str = "str",
    unit: str | None = None,
    varies_ok: bool = False,
    note: str | None = None,
    item: Callable[[Dataset], Dataset | None] | None = None,
) -> EvidenceField:
    """Collect a standard attribute over all slices.

    - absent or empty on every slice: MISSING;
    - not convertible, partially present, or varying when it should be constant:
      PRESENT_BUT_AMBIGUOUS (first raw value kept, reason in ``note``);
    - otherwise PRESENT.
    ``item`` selects a nested dataset (e.g. the first radiopharmaceutical item).
    """
    label = name or keyword
    srcs = [item(h) if item else h for h in headers]
    raws = [_raw(_get(s, keyword)) if s is not None else None for s in srcs]
    present = [r for r in raws if r is not None]
    distinct = list(dict.fromkeys(present))
    base: dict[str, Any] = {
        "name": label,
        "unit": unit,
        "source": tag_label(keyword),
        "derivation": "standard_tag",
        "note": note,
    }
    if not present:
        return EvidenceField(status="MISSING", **base)
    base["n_distinct_across_slices"] = len(distinct)
    try:
        value = KINDS[kind](distinct[0])
    except (TypeError, ValueError):
        base["note"] = f"value {distinct[0]!r} is not a valid {kind}"
        return EvidenceField(status="PRESENT_BUT_AMBIGUOUS", value=distinct[0], **base)
    problems = []
    if len(present) < len(raws):
        problems.append(f"present on {len(present)}/{len(raws)} slices")
    if len(distinct) > 1 and not varies_ok:
        problems.append(f"{len(distinct)} distinct values across slices")
    if problems:
        base["note"] = "; ".join(problems)
        return EvidenceField(status="PRESENT_BUT_AMBIGUOUS", value=value, **base)
    if len(distinct) > 1:
        base["note"] = (note + "; " if note else "") + (
            f"varies per slice ({len(distinct)} values); first-slice value shown"
        )
    return EvidenceField(status="PRESENT", value=value, **base)


def derived(
    name: str,
    value: Any,
    *,
    source: str,
    derivation: Derivation,
    unit: str | None = None,
    note: str | None = None,
    ambiguous: bool = False,
) -> EvidenceField:
    if value is None:
        return EvidenceField(
            name=name,
            status="MISSING",
            source=source,
            derivation=derivation,
            unit=unit,
            note=note,
        )
    return EvidenceField(
        name=name,
        status="PRESENT_BUT_AMBIGUOUS" if ambiguous else "PRESENT",
        value=value,
        unit=unit,
        source=source,
        derivation=derivation,
        note=note,
    )


def missing(name: str, source: str, note: str | None = None) -> EvidenceField:
    return EvidenceField(name=name, status="MISSING", source=source, note=note)


def first_item(seq_keyword: str) -> Callable[[Dataset], Dataset | None]:
    def pick(ds: Dataset) -> Dataset | None:
        seq = _get(ds, seq_keyword)
        return seq[0] if seq else None

    return pick


def private_creators(headers: Sequence[Dataset]) -> list[str]:
    """Private creator strings of the first slice (never private element values)."""
    found: list[str] = []
    if not headers:
        return found
    for e in headers[0]:
        if e.tag.is_private and 0x10 <= e.tag.element <= 0xFF:
            s = f"({e.tag.group:04X}) {str(e.value).strip()}"
            if s not in found:
                found.append(s)
    return found
