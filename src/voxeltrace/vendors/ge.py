"""GE PET private attributes with verified provenance."""

from voxeltrace.vendors.base import PrivateField, VendorParser

QIBA = (
    "QIBA SUV vendor-neutral pseudo-code 2018-06-26 "
    "(https://qibawiki.rsna.org/images/8/86/SUV_vendorneutral_pseudocode_20180626_DAC.pdf): "
    "'GE private scan Date and Time (0x0009,0x100d,\"GEMS_PETD_01\")'"
)
DICTS = (
    "GDCM gdcmPrivateDefaultDicts.cxx L4830-4877 and pydicom _private_dict.py "
    "(GEMS_PETD_01 (0009,xx3B) 'PET admin_datetime'); GE conformance statement not read"
)


class GEParser(VendorParser):
    vendor = "GE"
    fields = (
        PrivateField(
            vendor="GE",
            group=0x0009,
            element_offset=0x0D,
            creator="GEMS_PETD_01",
            name="scan_datetime",
            meaning="GE PET scan date/time (decay reference)",
            value_kind="DT",
            source=QIBA,
        ),
        # Secondary sources only (toolkit dictionaries): reported, never interpreted.
        PrivateField(
            vendor="GE",
            group=0x0009,
            element_offset=0x3B,
            creator=None,
            name="admin_datetime",
            meaning="GE PET administration date/time",
            value_kind="DT",
            source=DICTS + " -> UNSUPPORTED (secondary only)",
        ),
    )

    def matches(self, manufacturer: str | None) -> bool:
        m = (manufacturer or "").upper()
        return m.startswith("GE") or "GENERAL ELECTRIC" in m
