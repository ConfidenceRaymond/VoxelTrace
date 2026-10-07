"""Vendor parsers: documented private attributes only, read-only, creator-checked."""

from voxeltrace.vendors.base import PrivateEvidence, VendorParser, read_private
from voxeltrace.vendors.ge import GEParser
from voxeltrace.vendors.philips import PhilipsParser
from voxeltrace.vendors.siemens import SiemensParser

PARSERS: tuple[VendorParser, ...] = (SiemensParser(), GEParser(), PhilipsParser())


def parser_for(manufacturer: str | None) -> VendorParser | None:
    return next((p for p in PARSERS if p.matches(manufacturer)), None)


__all__ = ["PARSERS", "PrivateEvidence", "VendorParser", "parser_for", "read_private"]
