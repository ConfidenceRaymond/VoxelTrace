"""Vendor private-attribute framework (read-only evidence; never used by strict SUV).

Each supported private attribute must have:
  - a verified provenance (conformance statement, published method, or a verified line in an
    established open-source implementation), recorded in ``source``;
  - a private creator check: the element is interpreted ONLY if the creator string reserved
    for its block matches ``creator`` exactly. Otherwise -> UNSUPPORTED_PRIVATE_TAG.
Values are reported for cross-checks (e.g. timing consistency), never silently applied.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel
from pydicom.dataset import Dataset
from pydicom.tag import Tag

Status = Literal[
    "SUPPORTED_READ_ONLY", "UNSUPPORTED_PRIVATE_TAG", "NOT_PRESENT", "CREATOR_MISMATCH"
]


@dataclass(frozen=True)
class PrivateField:
    vendor: str
    group: int
    element_offset: int  # low byte within the creator's block, e.g. 0x22 for (0071,1022)
    creator: str | None  # None = creator string not verified -> never interpreted
    name: str
    meaning: str
    value_kind: str
    source: str


class PrivateEvidence(BaseModel):
    vendor: str
    name: str
    tag: str
    creator_expected: str | None
    creator_found: str | None
    status: Status
    value: Any = None
    meaning: str
    source: str


def _creator_block(ds: Dataset, group: int, creator: str) -> int | None:
    for block in range(0x10, 0x100):
        t = Tag(group, block)
        if t in ds and str(ds[t].value).strip() == creator:
            return block
    return None


def read_private(ds: Dataset, f: PrivateField) -> PrivateEvidence:
    tag_txt = f"({f.group:04X},xx{f.element_offset:02X})"
    base = dict(
        vendor=f.vendor,
        name=f.name,
        tag=tag_txt,
        creator_expected=f.creator,
        meaning=f.meaning,
        source=f.source,
    )
    if f.creator is None:
        return PrivateEvidence(creator_found=None, status="UNSUPPORTED_PRIVATE_TAG", **base)
    block = _creator_block(ds, f.group, f.creator)
    if block is None:
        found = [
            str(ds[Tag(f.group, b)].value) for b in range(0x10, 0x100) if Tag(f.group, b) in ds
        ]
        return PrivateEvidence(
            creator_found=", ".join(found) or None,
            status="CREATOR_MISMATCH" if found else "NOT_PRESENT",
            **base,
        )
    t = Tag(f.group, (block << 8) | f.element_offset)
    if t not in ds:
        return PrivateEvidence(creator_found=f.creator, status="NOT_PRESENT", **base)
    v = ds[t].value
    if isinstance(v, bytes):
        v = v.decode(errors="replace").strip("\x00 ")
    return PrivateEvidence(
        creator_found=f.creator,
        status="SUPPORTED_READ_ONLY",
        value=str(v).strip(),
        **{**base, "tag": f"({t.group:04X},{t.element:04X})"},
    )


class VendorParser:
    vendor = "GENERIC"
    manufacturer_tokens: tuple[str, ...] = ()
    fields: tuple[PrivateField, ...] = ()

    def matches(self, manufacturer: str | None) -> bool:
        m = (manufacturer or "").upper()
        return any(t in m for t in self.manufacturer_tokens)

    def read(self, ds: Dataset) -> list[PrivateEvidence]:
        return [read_private(ds, f) for f in self.fields]
