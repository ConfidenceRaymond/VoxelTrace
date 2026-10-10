"""Reference regions for SYNTHETIC TEST FIXTURES: inheritance from the parent baseline.

A synthetic follow-up (``trial/perturb.py``, built with ``with_ct=True``) is a controlled
perturbation of one real baseline. Its CT is a copy of the baseline CT, pixel data and geometry
unchanged, labelled ``SYNTHETIC_PERTURBATION`` and ``CT_COPIED_UNCHANGED_FROM_BASELINE``.

No human reviews the synthetic follow-up, and none is fabricated. Instead the follow-up may
INHERIT the parent baseline's human-accepted reference geometry, unchanged, when ALL hold:

  1. the scan is declared synthetic in trial.yaml (``synthetic_perturbations``), its PET
     carries the SYNTHETIC_PERTURBATION DICOM label, and its fixture manifest
     (``synthetic_fixture.json``) is present and labelled;
  2. trial.yaml declares the inheritance (``synthetic_reference_inheritance``) and the parent
     named there is the parent recorded in the fixture manifest;
  3. the parent PET content hash equals the fixture's recorded parent hash;
  4. the follow-up CT geometry AND pixel hashes equal the parent CT's and the fixture's;
  5. the parent region is COMPUTED from a valid human review (ACCEPT/ADJUST) or was supplied.

The result is ``SYNTHETIC_INHERITED_REFERENCE`` (never ``COMPUTED``, never "ACCEPTED"). It is
measured on the synthetic follow-up PET at the parent's exact geometry, and records the
source review hash. Rules may use it ONLY on a synthetic pair; on any real scan inheritance is
refused (``INHERITANCE_REFUSED``) and reference_reason() rejects such a region.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel

from voxeltrace.quant.reference_region import ReferenceRegionResult, ReferenceRegionSpec, Region
from voxeltrace.schemas import ImageGeometry

FIXTURE_SCHEMA = "voxeltrace.synthetic-fixture/1"
FIXTURE_FILE = "synthetic_fixture.json"
LABELS = ("SYNTHETIC_PERTURBATION", "CT_COPIED_UNCHANGED_FROM_BASELINE")


def geometry_sha256(g: ImageGeometry) -> str:
    keys = ("coordinate_system", "shape_ijk", "spacing_ijk", "origin", "direction", "affine")
    d = {k: getattr(g, k) for k in keys}
    return hashlib.sha256(json.dumps(d, sort_keys=True, default=list).encode()).hexdigest()


def volume_sha256(array: np.ndarray, g: ImageGeometry) -> str:
    """Content hash of a loaded volume: geometry + float64 voxel values (modality LUT
    applied), so it is independent of file names and UIDs."""
    h = hashlib.sha256(geometry_sha256(g).encode())
    h.update(str(array.shape).encode())
    h.update(np.ascontiguousarray(array, dtype=np.float64).tobytes())
    return h.hexdigest()


class SyntheticFixtureManifest(BaseModel):
    schema_id: Literal["voxeltrace.synthetic-fixture/1"] = FIXTURE_SCHEMA
    labels: list[str]
    perturbation: str
    parent_case_dir: str
    parent_pet_content_sha256: str
    ct_copied_unchanged: bool
    ct_geometry_sha256: str | None = None
    ct_pixel_sha256: str | None = None
    note: str = (
        "SYNTHETIC TEST FIXTURE. Derived from a real public series; NOT a real follow-up "
        "scan. The CT is the baseline CT copied unchanged."
    )

    @classmethod
    def load(cls, case_dir: str | Path) -> SyntheticFixtureManifest | None:
        p = Path(case_dir) / FIXTURE_FILE
        return cls.model_validate_json(p.read_text()) if p.exists() else None


class InheritanceRequest(BaseModel):
    """What the audit knows when a synthetic follow-up asks to inherit (built per scan)."""

    child_key: str
    parent_key: str
    declared_synthetic: bool
    dicom_synthetic_label: bool
    fixture: SyntheticFixtureManifest | None
    parent_pet_content_sha256: str | None
    parent_ct_geometry_sha256: str | None
    parent_ct_pixel_sha256: str | None
    child_ct_geometry_sha256: str | None
    child_ct_pixel_sha256: str | None
    parent_fixture_match: bool


def same_case_dir(
    recorded: str | Path, actual: str | Path, workspace: str | Path | None = None
) -> bool:
    """Is the fixture's recorded parent directory the actual parent directory?

    Identical resolved paths match. Fixture manifests store absolute paths, so after the
    workspace moves to another machine or home directory, the same directory is also
    accepted when the recorded path ENDS WITH the actual directory's path relative to the
    current workspace (same location inside the workspace, different workspace root). Content
    and CT hashes are still checked separately; this never matches a different relative path."""
    from voxeltrace.config import workspace_root

    rec, act = Path(recorded), Path(actual).resolve()
    if rec.resolve() == act:
        return True
    ws = Path(workspace).resolve() if workspace else workspace_root()
    try:
        rel = act.relative_to(ws).parts
    except ValueError:
        return False
    return len(rel) >= 2 and rec.parts[-len(rel) :] == rel


def refusal_reason(req: InheritanceRequest) -> str | None:
    """None if inheritance is allowed, else why not (checks 1-4 of the module doc)."""
    if not req.declared_synthetic:
        return "scan is not declared SYNTHETIC_PERTURBATION in trial.yaml (real data)"
    if not req.dicom_synthetic_label:
        return "PET does not carry the SYNTHETIC_PERTURBATION DICOM label"
    f = req.fixture
    if f is None:
        return f"no {FIXTURE_FILE} fixture manifest in the synthetic case"
    if not set(LABELS) <= set(f.labels) or not f.ct_copied_unchanged:
        return "fixture manifest lacks the SYNTHETIC_PERTURBATION / CT_COPIED labels"
    if not req.parent_fixture_match:
        return "trial.yaml parent is not the parent recorded in the fixture manifest"
    if not req.parent_pet_content_sha256 or (
        req.parent_pet_content_sha256 != f.parent_pet_content_sha256
    ):
        return "parent PET content hash does not match the fixture's recorded parent"
    if not (req.child_ct_geometry_sha256 and req.parent_ct_geometry_sha256):
        return "CT unavailable for the parent or the synthetic follow-up"
    if not (req.child_ct_geometry_sha256 == req.parent_ct_geometry_sha256 == f.ct_geometry_sha256):
        return "synthetic CT geometry differs from the parent CT"
    if not (req.child_ct_pixel_sha256 == req.parent_ct_pixel_sha256 == f.ct_pixel_sha256):
        return "synthetic CT pixel data differ from the parent CT"
    return None


def inherit_region(
    region: Region,
    req: InheritanceRequest,
    parent: ReferenceRegionResult | None,
    parent_review_sha256: str | None,
    measure,
) -> ReferenceRegionResult:
    why = refusal_reason(req)
    if why is None:
        if parent is None or parent.status != "COMPUTED":
            why = "parent region is not COMPUTED (no accepted or supplied reference)"
        elif parent.source == "AUTO_PROPOSAL" and (
            parent.review_decision not in ("ACCEPT", "ADJUST") or not parent_review_sha256
        ):
            why = "parent region has no valid human review"
        elif parent.method == "SUPPLIED_MASK" or parent.centre_patient_mm is None:
            why = "only sphere/cylinder parent regions can be inherited"
    if why is not None:
        return ReferenceRegionResult(
            status="INHERITANCE_REFUSED", region=region, refusal=why, source="SYNTHETIC_INHERITED"
        )
    assert parent is not None
    spec = ReferenceRegionSpec(
        region=region,
        method=parent.method,  # type: ignore[arg-type]
        centre_patient_mm=parent.centre_patient_mm,
        diameter_mm=parent.diameter_mm,
        length_mm=parent.length_mm,
        provenance=f"SYNTHETIC TEST FIXTURE: geometry inherited unchanged from {req.parent_key}",
    )
    res = measure(spec)
    inherited: dict[str, Any] = {
        "parent_key": req.parent_key,
        "parent_status": parent.status,
        "parent_source": parent.source,
        "parent_review_decision": parent.review_decision,
        "parent_reviewer": parent.reviewer,
        "source_review_sha256": parent_review_sha256,
        "parent_proposal_sha256": parent.proposal_sha256,
        "parent_pet_content_sha256": req.parent_pet_content_sha256,
        "ct_geometry_sha256": req.child_ct_geometry_sha256,
        "ct_pixel_sha256": req.child_ct_pixel_sha256,
        "geometry": spec.model_dump(exclude={"provenance"}),
        "fixture_labels": list(req.fixture.labels) if req.fixture else [],
    }
    res.source = "SYNTHETIC_INHERITED"
    res.inherited_from = inherited
    if res.status == "COMPUTED":
        res.status = "SYNTHETIC_INHERITED_REFERENCE"
    return res
