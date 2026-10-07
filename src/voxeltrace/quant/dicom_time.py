"""Strict DICOM DA / TM / DT parsing for quantitative timing.

This is the only module that turns DICOM date/time strings into ``datetime`` objects for
VoxelTrace quantification. It never guesses a date and never accepts reduced precision:

- DA must be ``YYYYMMDD``.
- TM must be ``HHMMSS`` with an optional ``.F{1,6}`` fraction. Reduced precision (``HH``,
  ``HHMM``) and the legacy ACR-NEMA ``HH:MM:SS`` form are rejected: a missing seconds field
  could hide up to a minute of decay-interval error.
- DT must be ``YYYYMMDDHHMMSS[.F{1,6}][&ZZXX]``. An optional UTC offset yields an aware
  datetime; without it the datetime is naive (local, unspecified zone).

Combining a TM with a date, or rolling over midnight, is not done here. Those are policy
decisions made by the caller (see ``voxeltrace.quant.suv``) and recorded in provenance.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone

_DA = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
_TM = re.compile(r"^(\d{2})(\d{2})(\d{2})(?:\.(\d{1,6}))?$")
_DT = re.compile(
    r"^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(?:\.(\d{1,6}))?(?:([+-])(\d{2})(\d{2}))?$"
)


class DicomTimeError(ValueError):
    """A DICOM DA/TM/DT value is absent, malformed, out of range or too imprecise."""


def _clean(value: object, vr: str) -> str:
    if value is None:
        raise DicomTimeError(f"{vr} value is absent")
    s = str(value).strip()
    if not s:
        raise DicomTimeError(f"{vr} value is empty")
    return s


def _micro(frac: str | None) -> int:
    return int(frac.ljust(6, "0")) if frac else 0


def parse_da(value: object) -> date:
    s = _clean(value, "DA")
    m = _DA.match(s)
    if not m:
        raise DicomTimeError(f"DA {s!r} is not YYYYMMDD")
    try:
        return date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError as exc:
        raise DicomTimeError(f"DA {s!r} is not a valid date: {exc}") from exc


def parse_tm(value: object) -> time:
    s = _clean(value, "TM")
    m = _TM.match(s)
    if not m:
        raise DicomTimeError(
            f"TM {s!r} is not HHMMSS[.FFFFFF] (reduced precision and colon formats rejected)"
        )
    try:
        return time(int(m[1]), int(m[2]), int(m[3]), _micro(m[4]))
    except ValueError as exc:
        raise DicomTimeError(f"TM {s!r} is not a valid time: {exc}") from exc


def parse_dt(value: object) -> datetime:
    s = _clean(value, "DT")
    m = _DT.match(s)
    if not m:
        raise DicomTimeError(f"DT {s!r} is not YYYYMMDDHHMMSS[.FFFFFF][&ZZXX]")
    tz = None
    if m[8]:
        minutes = int(m[9]) * 60 + int(m[10])
        if int(m[9]) > 14 or int(m[10]) > 59:
            raise DicomTimeError(f"DT {s!r} has an invalid UTC offset")
        tz = timezone(timedelta(minutes=minutes if m[8] == "+" else -minutes))
    try:
        return datetime(
            int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), int(m[6]), _micro(m[7]), tz
        )
    except ValueError as exc:
        raise DicomTimeError(f"DT {s!r} is not a valid datetime: {exc}") from exc


def combine_da_tm(da: object, tm: object) -> datetime:
    """Naive datetime from a DA and a TM that belong to the same attribute pair."""
    return datetime.combine(parse_da(da), parse_tm(tm))


def parse_utc_offset(value: object) -> timezone:
    """Parse TimezoneOffsetFromUTC (0008,0201), ``&ZZXX``."""
    s = _clean(value, "SH")
    m = re.match(r"^([+-])(\d{2})(\d{2})$", s)
    if not m or int(m[2]) > 14 or int(m[3]) > 59:
        raise DicomTimeError(f"TimezoneOffsetFromUTC {s!r} is not &ZZXX")
    minutes = int(m[2]) * 60 + int(m[3])
    return timezone(timedelta(minutes=minutes if m[1] == "+" else -minutes))
