# VoxelTrace: Retrospective PET Comparability Audit

*For imaging core-lab directors and sponsor imaging leads. Research software; not a medical
device. Independent external validation in progress.*

**Problem.** Quantitative PET endpoints assume the baseline and follow-up scans are
comparable: the same tracer, timing, dose handling, scanner settings and reconstruction. In
multicentre trials they often are not. When this is found late, SUV changes may be
uninterpretable, data are lost, and sites are queried months after the scan.

**Why current workflows fail.** Comparability is checked by hand or with in-house scripts,
scan by scan:
- reconstruction settings are often missing or only free text in the export;
- de-identification strips weight, height or times;
- "cannot decide" is rarely recorded as its own outcome, so it becomes a silent include or
  exclude.

**VoxelTrace solution.** It is a deterministic audit that checks every scan and every
baseline/follow-up pair against the rule set your charter names: QIBA FDG-PET/CT 1.14, EANM
FDG 2.0 or PERCIST 1.0. Every "cannot decide" is explained with a reason and a draft site
query. It runs locally, with no AI in the audit.

**What it checks.**
- SUV prerequisites (units, decay correction, dose, injection and acquisition times, weight;
  height and sex for SUL).
- Tracer and uptake windows.
- Scanner and software identity.
- Reconstruction identity.
- CT frame of reference.
- De-identification losses.
- Protocol drift by site.
- Reference-region and lesion-target review status.

**What you receive.**
- Executive summary.
- Pair verdict tables and subject × timepoint matrix.
- Site summary and drift events.
- Failure reasons with catalogued remediations.
- Draft site queries.
- PDF, CSV and JSON.
- A checksum-verified evidence bundle. A sample on demonstration data is available.

**Current validation (as of 2026-10-09).**
- 9 real public longitudinal pairs (4 collections, 6 scanner models).
- Several Siemens models validated end to end.
- GE and Philips quantification not yet validated.
- Blinded external physicist study prepared; **no agreement result yet**.

**Limitations.**
- FDG PET/CT only.
- No diagnosis, response classification, segmentation or harmonization.
- Plausible-but-wrong header values cannot be detected.
- Fasting and glucose are outside the images.
- Human review is required for reference regions and lesion targets.

**Call to action.** We are looking for a small number of design partners: a completed
multicentre FDG PET study audited locally on your data, a findings workshop with your
physicists, and your expert feedback in return. Contact: `<email>`.
