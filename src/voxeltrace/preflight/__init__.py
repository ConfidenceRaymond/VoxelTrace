"""VoxelTrace Quantitative Preflight (VT-PREFLIGHT-1).

Read-only inspection of PET (and companion CT) DICOM BEFORE quantification. Preflight never
computes SUV or SUL; it runs the unchanged strict input validator and protocol extractors on
headers only and reports, per series, whether quantification may proceed:

  READY_TO_QUANTIFY / READY_WITH_WARNINGS / DO_NOT_QUANTIFY / NEEDS_REVIEW
"""

from voxeltrace.preflight.batch import preflight_batch
from voxeltrace.preflight.schema import PREFLIGHT_SCHEMA
from voxeltrace.preflight.series import preflight_series_headers
from voxeltrace.preflight.subject import preflight_scan_dir

__all__ = ["PREFLIGHT_SCHEMA", "preflight_batch", "preflight_scan_dir", "preflight_series_headers"]
