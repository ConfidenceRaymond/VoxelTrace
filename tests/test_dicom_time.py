from datetime import date, datetime, time, timedelta, timezone

import pytest

from voxeltrace.quant.dicom_time import (
    DicomTimeError,
    combine_da_tm,
    parse_da,
    parse_dt,
    parse_tm,
    parse_utc_offset,
)


def test_da_tm_dt_basic():
    assert parse_da("20030323") == date(2003, 3, 23)
    assert parse_tm("121000") == time(12, 10, 0)
    assert parse_dt("20030323121000") == datetime(2003, 3, 23, 12, 10, 0)


@pytest.mark.parametrize(
    ("tm", "micro"), [("121000.5", 500000), ("121000.000001", 1), ("121000.123456", 123456)]
)
def test_fractional_seconds(tm, micro):
    assert parse_tm(tm).microsecond == micro
    assert parse_dt("20030323" + tm).microsecond == micro


def test_dt_with_offset_is_aware():
    v = parse_dt("20200101101500.25+0130")
    assert v.utcoffset() == timedelta(hours=1, minutes=30)
    assert v.microsecond == 250000
    assert parse_utc_offset("-0500") == timezone(timedelta(hours=-5))


def test_combine_and_padding():
    assert combine_da_tm(" 20200101 ", "235959.999999 ") == datetime(2020, 1, 1, 23, 59, 59, 999999)


@pytest.mark.parametrize(
    "bad",
    [None, "", "   ", "1210", "12", "12:10:00", "121060", "250000", "121000.1234567", "abc"],
)
def test_tm_rejected(bad):
    with pytest.raises(DicomTimeError):
        parse_tm(bad)


@pytest.mark.parametrize("bad", ["2003032", "20031323", "20030230", "2003-03-23", None])
def test_da_rejected(bad):
    with pytest.raises(DicomTimeError):
        parse_da(bad)


@pytest.mark.parametrize("bad", ["200303231210", "20030323121000+2500", "20030323T121000"])
def test_dt_rejected(bad):
    with pytest.raises(DicomTimeError):
        parse_dt(bad)
