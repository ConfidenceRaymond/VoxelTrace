"""Reconstruction protocol evidence from standard DICOM attributes.

Order of precedence for each parameter:
1. Structured standard attributes (Enhanced PET: NumberOfIterations (0018,9739),
   NumberOfSubsets (0018,9740), TimeOfFlightInformationUsed (0018,9755),
   ReconstructionAlgorithm (0018,9315), ReconstructionType (0018,9756)), top level or in
   PETReconstructionSequence (0018,9749).
2. Documented patterns in the free-text standard attributes ReconstructionMethod (0054,1103)
   and ConvolutionKernel (0018,1210). These only ever assert POSITIVE findings:
     - ``<N>i<M>s``        -> iterations N, subsets M (e.g. Siemens "2i21s")
     - token ``TOF``       -> time-of-flight used
     - token ``PSF``/``TrueX`` -> PSF / resolution modelling used
     - ``Gauss<w>``        -> Gaussian post-filter, width w (unit/convention NOT stated:
                              PRESENT_BUT_AMBIGUOUS)
   The absence of a token never means "not used"; it means unknown (MISSING).
3. Vendor-private tags are NOT parsed. Their private creators are listed as unsupported.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from pydantic import BaseModel, Field
from pydicom.dataset import Dataset

from voxeltrace.evidence._dicom import derived, first_item, missing, private_creators, tag_field
from voxeltrace.schemas import EvidenceField, ImageGeometry

_ITER_SUBSETS = re.compile(r"(?<![A-Za-z0-9.])(\d+)\s*i\s*(\d+)\s*s(?![A-Za-z])", re.IGNORECASE)
_TOF = re.compile(r"(?<![A-Za-z])TOF(?![A-Za-z])", re.IGNORECASE)
_PSF = re.compile(r"(?<![A-Za-z])(PSF|TRUEX)(?![A-Za-z])", re.IGNORECASE)
_GAUSS = re.compile(r"Gauss(?:ian)?\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
_FAMILY = [
    (re.compile(r"(?<![A-Za-z])FBP(?![A-Za-z])", re.I), "FBP"),
    (re.compile(r"(?<![A-Za-z])(BSREM|Q\.?CLEAR)(?![A-Za-z])", re.I), "BSREM"),
    (re.compile(r"(?<![A-Za-z])(OP-)?OSEM", re.I), "OSEM"),
    (re.compile(r"RAMLA", re.I), "RAMLA"),
]

FREE_TEXT_NOTE = "parsed from free text by a documented vendor-convention pattern"


class ReconstructionProtocol(BaseModel):
    series_uid: str
    series_description: EvidenceField
    reconstruction_method: EvidenceField
    algorithm_family: EvidenceField
    reconstruction_type: EvidenceField
    iterations: EvidenceField
    subsets: EvidenceField
    time_of_flight: EvidenceField
    psf_resolution_modelling: EvidenceField
    convolution_kernel: EvidenceField
    filter_type: EvidenceField
    post_filter_gaussian_width: EvidenceField
    reconstruction_diameter_mm: EvidenceField
    matrix_rows: EvidenceField
    matrix_columns: EvidenceField
    voxel_size_mm: EvidenceField = Field(description="(i, j, k) from geometry.")
    slice_thickness_mm: EvidenceField
    spacing_between_slices_mm: EvidenceField
    software_versions: EvidenceField
    unsupported_private_metadata: list[str] = Field(
        default_factory=list,
        description="Private creators present; vendor-private parameters are not parsed.",
    )


def _structured(headers: Sequence[Dataset], keyword: str, kind: str = "str") -> EvidenceField:
    f = tag_field(headers, keyword, kind=kind)
    if f.status == "MISSING":
        f = tag_field(headers, keyword, kind=kind, item=first_item("PETReconstructionSequence"))
    return f


def _from_text(
    name: str, text: str | None, src: str, value, ambiguous: bool = False, note: str | None = None
) -> EvidenceField:
    if text is None:
        return missing(name, src, note="source text absent")
    if value is None:
        return missing(
            name, src, note="not stated in free text (absence is not evidence of absence)"
        )
    return derived(
        name,
        value,
        source=src,
        derivation="free_text_pattern",
        note=note or FREE_TEXT_NOTE,
        ambiguous=ambiguous,
    )


def parse_iterations_subsets(text: str | None) -> tuple[int, int] | None | str:
    """(iterations, subsets); None if absent; 'AMBIGUOUS' if several different matches."""
    if not text:
        return None
    found = {(int(a), int(b)) for a, b in _ITER_SUBSETS.findall(text)}
    if not found:
        return None
    if len(found) > 1:
        return "AMBIGUOUS"
    return next(iter(found))


def extract_reconstruction(
    series_uid: str, headers: Sequence[Dataset], geometry: ImageGeometry | None
) -> ReconstructionProtocol:
    method = tag_field(headers, "ReconstructionMethod")
    text = str(method.value) if method.known else None
    msrc = "(0054,1103) ReconstructionMethod"
    kernel = tag_field(headers, "ConvolutionKernel", kind="list")
    ktext = "\\".join(kernel.value) if isinstance(kernel.value, list) else None
    ksrc = "(0018,1210) ConvolutionKernel"

    # Iterations / subsets.
    it_s = _structured(headers, "NumberOfIterations", "int")
    sub_s = _structured(headers, "NumberOfSubsets", "int")
    parsed = parse_iterations_subsets(text)
    if it_s.known:
        iterations = it_s
    elif parsed == "AMBIGUOUS":
        iterations = derived(
            "iterations",
            text,
            source=msrc,
            derivation="free_text_pattern",
            ambiguous=True,
            note="several different <N>i<M>s patterns",
        )
    else:
        iterations = _from_text(
            "iterations", text, msrc, parsed[0] if isinstance(parsed, tuple) else None
        )
    if sub_s.known:
        subsets = sub_s
    elif parsed == "AMBIGUOUS":
        subsets = derived(
            "subsets",
            text,
            source=msrc,
            derivation="free_text_pattern",
            ambiguous=True,
            note="several different <N>i<M>s patterns",
        )
    else:
        subsets = _from_text(
            "subsets", text, msrc, parsed[1] if isinstance(parsed, tuple) else None
        )

    # TOF.
    tof_s = _structured(headers, "TimeOfFlightInformationUsed")
    if tof_s.known and tof_s.value in ("YES", "NO"):
        tof = derived(
            "time_of_flight",
            tof_s.value == "YES",
            source=tof_s.source or "",
            derivation="standard_tag",
        )
    else:
        tof = _from_text("time_of_flight", text, msrc, True if text and _TOF.search(text) else None)

    psf = _from_text(
        "psf_resolution_modelling", text, msrc, True if text and _PSF.search(text) else None
    )

    algo_s = _structured(headers, "ReconstructionAlgorithm")
    if algo_s.known:
        family = algo_s
    else:
        fam = sorted({label for rx, label in _FAMILY if text and rx.search(text)})
        if len(fam) > 1:
            family = derived(
                "algorithm_family",
                fam,
                source=msrc,
                derivation="free_text_pattern",
                ambiguous=True,
                note="conflicting algorithm tokens",
            )
        else:
            family = _from_text("algorithm_family", text, msrc, fam[0] if fam else None)

    g = _GAUSS.search(ktext or "")
    gauss = _from_text(
        "post_filter_gaussian_width",
        ktext,
        ksrc,
        float(g.group(1)) if g else None,
        ambiguous=True,
        note="Gaussian width parsed from free text; unit (mm?) and FWHM/sigma convention are "
        "not stated in DICOM",
    )

    if geometry is not None:
        vox = derived(
            "voxel_size_mm",
            [float(v) for v in geometry.spacing_ijk if v is not None]
            if None not in geometry.spacing_ijk
            else None,
            source="PixelSpacing + slice positions (geometry)",
            derivation="derived_from_geometry",
            unit="mm",
            note=None if None not in geometry.spacing_ijk else "non-uniform slice spacing",
        )
    else:
        vox = missing("voxel_size_mm", "geometry", note="geometry unavailable")

    return ReconstructionProtocol(
        series_uid=series_uid,
        series_description=tag_field(headers, "SeriesDescription"),
        reconstruction_method=method,
        algorithm_family=family,
        reconstruction_type=_structured(headers, "ReconstructionType"),
        iterations=iterations,
        subsets=subsets,
        time_of_flight=tof,
        psf_resolution_modelling=psf,
        convolution_kernel=kernel,
        filter_type=tag_field(headers, "FilterType"),
        post_filter_gaussian_width=gauss,
        reconstruction_diameter_mm=tag_field(
            headers, "ReconstructionDiameter", kind="float", unit="mm"
        ),
        matrix_rows=tag_field(headers, "Rows", kind="int"),
        matrix_columns=tag_field(headers, "Columns", kind="int"),
        voxel_size_mm=vox,
        slice_thickness_mm=tag_field(headers, "SliceThickness", kind="float", unit="mm"),
        spacing_between_slices_mm=tag_field(
            headers, "SpacingBetweenSlices", kind="float", unit="mm"
        ),
        software_versions=tag_field(headers, "SoftwareVersions", kind="list"),
        unsupported_private_metadata=private_creators(headers),
    )
