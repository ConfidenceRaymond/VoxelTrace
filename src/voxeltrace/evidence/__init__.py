"""Protocol, reconstruction and correction evidence; comparability; deterministic claims.

Header-only (no pixels), standard DICOM attributes only (vendor-private tags not parsed),
no AI. Missing values are reported as MISSING, never inferred.
"""

from voxeltrace.evidence.acquisition import AcquisitionProtocol, extract_acquisition
from voxeltrace.evidence.claims import (
    ClaimEvidence,
    claim_diagnosis,
    claim_image_noise,
    claim_protocol_fact,
    claim_quantity,
    claim_treatment_response,
    claim_uptake_change,
    default_case_claims,
)
from voxeltrace.evidence.comparability import ComparabilityAssessment, compare_protocols
from voxeltrace.evidence.corrections import CorrectionEvidence, extract_corrections
from voxeltrace.evidence.protocol import (
    ProtocolEvidence,
    ProtocolQC,
    assess_protocol_qc,
    extract_protocol,
)
from voxeltrace.evidence.reconstruction import ReconstructionProtocol, extract_reconstruction
from voxeltrace.evidence.scanner import ScannerEvidence, extract_scanner

__all__ = [
    "AcquisitionProtocol",
    "ClaimEvidence",
    "ComparabilityAssessment",
    "CorrectionEvidence",
    "ProtocolEvidence",
    "ProtocolQC",
    "ReconstructionProtocol",
    "ScannerEvidence",
    "assess_protocol_qc",
    "claim_diagnosis",
    "claim_image_noise",
    "claim_protocol_fact",
    "claim_quantity",
    "claim_treatment_response",
    "claim_uptake_change",
    "compare_protocols",
    "default_case_claims",
    "extract_acquisition",
    "extract_corrections",
    "extract_protocol",
    "extract_reconstruction",
    "extract_scanner",
]
