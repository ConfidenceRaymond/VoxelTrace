"""Pair construction: baseline (first in timepoint_order) vs every later timepoint."""

from __future__ import annotations

from voxeltrace.trial.schema import ScanPair


def make_pairs(subject: str, timepoints: list[str], order: list[str]) -> list[ScanPair]:
    ranked = sorted(timepoints, key=lambda t: (order.index(t) if t in order else len(order), t))
    if len(ranked) < 2:
        return []
    return [ScanPair(subject_id=subject, baseline=ranked[0], followup=t) for t in ranked[1:]]
