"""Patient-level splits and leakage detection.

The unit of splitting is the SUBJECT: every study (incl. longitudinal repeats), series,
slice, rendered image and example derived from one subject lands in exactly one split.
With fewer than ``MIN_SUBJECTS_FOR_SPLITS`` subjects everything is DEVELOPMENT_ONLY:
such data are for pipeline testing, not for training or statistical evaluation.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable

from voxeltrace.training.schema import DatasetSplit, SplitName, TrainingExample

MIN_SUBJECTS_FOR_SPLITS = 20
SPLIT_SALT = "voxeltrace-split-v1"


def assign_patient_splits(
    subjects: Iterable[str],
    *,
    fractions: tuple[float, float, float] = (0.7, 0.15, 0.15),
    min_subjects: int = MIN_SUBJECTS_FOR_SPLITS,
) -> dict[str, SplitName]:
    """Deterministic subject -> split (salted hash order; independent of input order)."""
    subs = sorted(set(subjects))
    if len(subs) < min_subjects:
        return dict.fromkeys(subs, "DEVELOPMENT_ONLY")
    if abs(sum(fractions) - 1.0) > 1e-9:
        raise ValueError("split fractions must sum to 1")
    order = sorted(subs, key=lambda s: hashlib.sha256(f"{SPLIT_SALT}:{s}".encode()).hexdigest())
    n = len(order)
    n_train = int(round(fractions[0] * n))
    n_val = int(round(fractions[1] * n))
    out: dict[str, SplitName] = {}
    for i, s in enumerate(order):
        out[s] = "TRAIN" if i < n_train else "VALIDATION" if i < n_train + n_val else "LOCKED_TEST"
    return out


def check_leakage(examples: Iterable[TrainingExample]) -> list[str]:
    """Return human-readable leakage violations (empty list = no leakage)."""
    ex = list(examples)
    problems: list[str] = []
    by_subject: dict[str, set[str]] = defaultdict(set)
    study_subject: dict[str, set[str]] = defaultdict(set)
    study_split: dict[str, set[str]] = defaultdict(set)
    image_split: dict[str, set[str]] = defaultdict(set)
    image_subject: dict[str, set[str]] = defaultdict(set)
    for e in ex:
        by_subject[e.subject_pseudonym].add(e.split)
        study_subject[e.study_pseudonym].add(e.subject_pseudonym)
        study_split[e.study_pseudonym].add(e.split)
        for img in e.images:
            image_split[img.sha256].add(e.split)
            image_subject[img.sha256].add(e.subject_pseudonym)
    for s, splits in by_subject.items():
        if len(splits) > 1:
            problems.append(f"subject {s} appears in several splits: {sorted(splits)}")
    for st, subs in study_subject.items():
        if len(subs) > 1:
            problems.append(f"study {st} attributed to several subjects: {sorted(subs)}")
    for st, splits in study_split.items():
        if len(splits) > 1:
            problems.append(f"study {st} (incl. longitudinal) crosses splits: {sorted(splits)}")
    for h, splits in image_split.items():
        if len(splits) > 1:
            problems.append(f"image {h[:12]} (derived image) crosses splits: {sorted(splits)}")
    for h, subs in image_subject.items():
        if len(subs) > 1:
            problems.append(f"image {h[:12]} shared by several subjects: {sorted(subs)}")
    dev = {e.split for e in ex} & {"DEVELOPMENT_ONLY"}
    if dev and len({e.split for e in ex}) > 1:
        problems.append("DEVELOPMENT_ONLY examples mixed with TRAIN/VALIDATION/LOCKED_TEST")
    return problems


def summarize_splits(examples: Iterable[TrainingExample]) -> list[DatasetSplit]:
    subs: dict[str, set[str]] = defaultdict(set)
    counts: dict[str, int] = defaultdict(int)
    for e in examples:
        subs[e.split].add(e.subject_pseudonym)
        counts[e.split] += 1
    return [
        DatasetSplit(name=k, subjects=sorted(v), n_examples=counts[k])  # type: ignore[arg-type]
        for k, v in sorted(subs.items())
    ]
