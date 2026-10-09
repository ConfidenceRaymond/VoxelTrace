"""Preflight of one series (headers only)."""

from __future__ import annotations

from collections.abc import Sequence

from pydicom.dataset import Dataset

from voxeltrace.preflight.checks import finding, pet_checks
from voxeltrace.preflight.schema import SeriesPreflight, worst_state
from voxeltrace.training.ground_truth import pseudonym


def preflight_series_headers(
    headers: Sequence[Dataset],
    *,
    subject: str | None = None,
    scan: str | None = None,
) -> SeriesPreflight:
    """Preflight one series from its (full or sampled) headers. Never computes SUV."""
    h0 = headers[0]
    uid = str(h0.get("SeriesInstanceUID", ""))
    modality = str(h0.get("Modality", ""))
    base = dict(
        subject=subject,
        scan=scan,
        series_pseudonym=pseudonym(uid, "pet"),
        modality=modality,
        n_instances=len(headers),
    )
    if modality != "PT":
        f = finding("NOT_PET_MODALITY", f"Modality {modality!r}", "object")
        return SeriesPreflight(**base, state="READY_TO_QUANTIFY", findings=[f])
    findings, facts = pet_checks(uid, headers)
    return SeriesPreflight(**base, state=worst_state(findings), findings=findings, facts=facts)
