"""Siemens PET private attributes with verified provenance."""

from voxeltrace.vendors.base import PrivateField, VendorParser

CONFORMANCE = (
    "Siemens Biograph TruePoint 6.7 DICOM Conformance Statement: private creator "
    "'SIEMENS MED PT' at (0071,0010); '>Decay Correction DateTime (0071,1022) DT The date and "
    "time to which the image was decay corrected. Also refer to (0054,1102)' "
    "(https://marketing.webassets.siemens-healthineers.com/1800000002980648/0c67c9728a42/"
    "PET_CT_Biograph_TruePoint_6_7_DICOM_Conformance_Statement.pdf); also used by Z-Rad 26.9.0 "
    "pet_suv.py L210-228 and MIRP dicom_file.py L624-645"
)


class SiemensParser(VendorParser):
    vendor = "SIEMENS"
    manufacturer_tokens = ("SIEMENS", "CPS", "CTI")
    fields = (
        PrivateField(
            vendor="SIEMENS",
            group=0x0071,
            element_offset=0x22,
            creator="SIEMENS MED PT",
            name="acquisition_start_datetime",
            meaning="Decay Correction DateTime: date/time to which the image was decay corrected",
            value_kind="DT",
            source=CONFORMANCE,
        ),
    )
