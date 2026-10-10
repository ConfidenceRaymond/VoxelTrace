"""Dataset validation: provenance, image integrity, leakage, identifiers, label sources."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

from voxeltrace.training.schema import GroundTruthCase, TrainingExample
from voxeltrace.training.splits import check_leakage

IDENTIFIER_KEYS = (
    "PatientName",
    "PatientID",
    "PatientBirthDate",
    "OtherPatientIDs",
    "AccessionNumber",
    "InstitutionName",
    "StationName",
    "DeviceSerialNumber",
    "ReferringPhysicianName",
)


class DatasetValidationError(RuntimeError):
    pass


def validate_dataset(
    root: Path,
    examples: list[TrainingExample],
    cases: list[GroundTruthCase],
    *,
    forbidden_strings: Iterable[str] = (),
    min_subjects_for_training: int = 20,
) -> list[str]:
    """Return a list of problems (empty = valid). Never mutates anything."""
    problems: list[str] = []
    problems += check_leakage(examples)
    subjects = {e.subject_pseudonym for e in examples}
    if len(subjects) < min_subjects_for_training and any(
        e.split != "DEVELOPMENT_ONLY" for e in examples
    ):
        problems.append("fewer subjects than required for TRAIN/VALIDATION/LOCKED_TEST splits")
    known_images = {img.sha256: img for c in cases for img in c.images}
    ids = [e.example_id for e in examples]
    if len(ids) != len(set(ids)):
        problems.append("duplicate example ids")
    for e in examples:
        for s in e.target_sources:
            if s.source_type == "MODEL_GENERATED" or not s.usable_as_target:
                problems.append(f"{e.example_id}: non-ground-truth target source {s.source_ref}")
        for img in e.images:
            p = (root / img.path).resolve()
            if root.resolve() not in p.parents:
                problems.append(f"{e.example_id}: image path escapes dataset root")
                continue
            if not p.exists():
                problems.append(f"{e.example_id}: missing image {img.path}")
                continue
            if hashlib.sha256(p.read_bytes()).hexdigest() != img.sha256:
                problems.append(f"{e.example_id}: image hash mismatch {img.path}")
            if img.sha256 not in known_images:
                problems.append(f"{e.example_id}: image not registered in ground truth")
            if p.suffix.lower() not in (".png", ".jpg", ".jpeg"):
                problems.append(f"{e.example_id}: non-PNG/JPEG image in export")
    blob = "\n".join(e.model_dump_json() for e in examples) + "\n".join(
        c.model_dump_json() for c in cases
    )
    for s in forbidden_strings:
        if s and s in blob:
            problems.append(f"forbidden identifying string present: {s[:12]}...")
    for key in IDENTIFIER_KEYS:
        if f'"{key}"' in blob:
            problems.append(f"identifier key {key} present in dataset")
    for f in sorted(root.rglob("*")):
        if f.suffix.lower() in (".dcm", ".nii", ".gz", ".nrrd", ".mha"):
            problems.append(f"medical image source file inside export: {f.name}")
    return problems


def assert_valid(*args, **kwargs) -> None:
    problems = validate_dataset(*args, **kwargs)
    if problems:
        raise DatasetValidationError("; ".join(problems[:10]))


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
