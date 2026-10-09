# Technical debt audit (2026-10-09)

## Fixed in this session

| Item | Fix |
|---|---|
| Pillow imported but not declared (fresh installs failed) | declared in `pyproject.toml`; fresh-venv install and full test suite verified |
| `pseudonym()` lived in the training package but was used by the audit path | moved to `voxeltrace/ids.py` (same salt, byte-identical pseudonyms), re-exported |
| Hard-coded `/home/dell/...` defaults in app pages 1–3 | derived from `REPO_ROOT` |
| Site queries mixed reason details across codes | one item per reason; lesion-target wording separated |
| External download plans picked the smallest CT (a localizer) | require ≥ 20 instances (frozen plans untouched) |
| Input file paths in bundles could carry identifiers | sha256 of paths by default |

## Remaining (recorded, not changed: validated code paths)

| Debt | Impact | Plan |
|---|---|---|
| Full audit re-runs ingestion/SUV/proposals for each rule set | about 3× runtime | compute timepoints once and assess with several rule sets; needs a byte-identity regression on existing audits |
| Memory grows with subject count (about 2.4 GB at 8 subjects) | large trials | release volumes after timepoint construction; batch by site |
| A SEG in a scan folder is measured as a lesion without review | PERCIST could use an unreviewed lesion | lesion review gate (analogous to the reference review gate); until then, withhold SEGs (as in the external validation) |
| DICOM discovery does not follow directory symlinks nested in scan folders | staging with dir links finds no series | follow links or document file-level links (current practice) |
| Census v2 excluded DERIVED CTs; the pipeline does not | census v2 (ACRIN) CT-in-frame counts may be pessimistic | census v3 mirrors the pipeline; v2 left as published |
| Census does not model PatientSex for SUL | 1 miss in 30 crosscheck fields | add sex to the SUL prediction in a census v4 |
| `scripts/` holds 40+ one-off research scripts | discoverability | product commands live in `voxeltrace` CLI; scripts are research provenance (kept) |
| No PDF report | delivery format | render Markdown to PDF only with a reproducible, pinned tool |
| Bundles not signed | authenticity | optional detached signature (e.g. minisign/GPG) over `checksums.sha256` |
| Catalog reason codes never emitted (PRIVATE_TAG_NOT_AVAILABLE, UNSUPPORTED_SOFTWARE_VERSION, UNSUPPORTED_VENDOR) | dead entries | keep for future vendor modules; listed as CATALOG_ONLY in the coverage matrix |
