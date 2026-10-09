# VoxelTrace Retrospective PET Comparability Audit: pilot one-pager

**What it is.** Software that checks, for every subject in a multicentre PET trial, whether
baseline and follow-up PET scans can be quantitatively compared. It applies explicit,
versioned rules (QIBA FDG-PET/CT 1.14, EANM FDG 2.0, PERCIST 1.0 plus engineering
prerequisites). It explains every "cannot decide" with a reason code and a draft site query.
Deterministic; no AI in the audit; every result ships in a checksum-verified evidence bundle.

**What a pilot delivers** (on de-identified retrospective data supplied by the partner):
- per-scan quantitative preflight (READY / WARNINGS / DO_NOT_QUANTIFY / NEEDS_REVIEW);
- per-pair verdicts under each standard, with blocking reasons;
- site/scanner protocol drift timeline;
- draft site queries for missing evidence;
- human review tasks (reference regions);
- an immutable evidence bundle.

**What it is not.** Not a diagnostic device. No response assessment. No regulatory clearance.
Research prototype.

**Current evidence** (see `docs/external_validation_v1.md`):
- 8 real public longitudinal pairs analysed;
- 2 reach a QIBA ASSESSABLE verdict and 1 a decided NOT_ASSESSABLE;
- the census of 43 public PET collections shows most open data cannot be decided, mainly
  because of missing reconstruction metadata, tracer coding or decay-timing inconsistencies.
