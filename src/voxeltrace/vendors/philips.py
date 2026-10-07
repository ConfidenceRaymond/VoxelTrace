"""Philips PET private attributes with verified provenance."""

from voxeltrace.vendors.base import PrivateField, VendorParser

QIBA = (
    "QIBA SUV vendor-neutral pseudo-code 2018-06-26 "
    "(https://qibawiki.rsna.org/images/8/86/SUV_vendorneutral_pseudocode_20180626_DAC.pdf): "
    "(0x7053,0x1000,'Philips PET Private Group') SUV scale factor; (7053,1009) x Rescale "
    "Slope -> Bq/ml; also Z-Rad 26.9.0 pet_suv.py L1450-1457"
)


class PhilipsParser(VendorParser):
    vendor = "PHILIPS"
    manufacturer_tokens = ("PHILIPS",)
    fields = (
        PrivateField(
            vendor="PHILIPS",
            group=0x7053,
            element_offset=0x00,
            creator="Philips PET Private Group",
            name="suv_scale_factor",
            meaning="scale factor stored value -> SUV (Units CNTS)",
            value_kind="DS",
            source=QIBA,
        ),
        PrivateField(
            vendor="PHILIPS",
            group=0x7053,
            element_offset=0x09,
            creator="Philips PET Private Group",
            name="bqml_scale_factor",
            meaning="activity scale factor (x RescaleSlope -> Bq/ml) (Units CNTS)",
            value_kind="DS",
            source=QIBA,
        ),
    )
