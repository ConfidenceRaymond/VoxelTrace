# Pilot scope: <PILOT ID> (template)

No pricing in this document. Replace every `<...>`. Leave nothing implied.

| Item | Entry |
|---|---|
| Sponsor / core lab | `<organisation, department>` |
| Customer contacts | `<scientific lead>`, `<data/privacy contact>`, `<QA contact>` |
| Trial | `<trial name / protocol number or internal code>`; phase `<…>`; status `<completed / ongoing>` |
| Subjects | `<n>` (pseudonymous codes only) |
| Timepoints | `<names and order, e.g. baseline, interim, end-of-treatment>`; expected pairs `<n>` |
| Sites | `<n>`; site map supplied by `<customer>` |
| Vendors / scanners | `<manufacturer, model, software versions as known>`. Matrix state today (`docs/vendor_validation_matrix.md`): `<PAIR_VALIDATED / INGESTION_VALIDATED / METADATA_ONLY / NOT_TESTED>` |
| Tracers | FDG only. Other tracers: `<excluded>` |
| Rule sets | `<QIBA FDG-PET/CT 1.14 / EANM FDG 2.0 / PERCIST 1.0>`; charter-specific overrides: `<none / list>` |
| Optional inputs | lesion SEGs `<yes/no>`; attestations `<yes/no>`; imaging manuals `<yes/no>` |
| Deployment | `<customer-local (default) / agreed workstation>` |
| Expected outputs | executive summary, pair verdicts per rule set, subject × timepoint matrix, site summary, failure reasons, drift events, draft site queries, PDF, CSV/JSON, evidence bundle and verification report |
| Turnaround target | `<n working days from accepted data>`. A target, not a guarantee; human-review time is excluded |
| Responsibilities: customer | de-identification; data delivery; site map; nominating reviewers for reference, lesion and adjudication decisions; deciding which site queries to send |
| Responsibilities: VoxelTrace | intake report, configuration, audit runs, bundle verification, report walkthrough, issue log |
| Exclusions | diagnosis; response classification; segmentation; image harmonization; clinical use; non-FDG tracers; `<other>` |
| Validation status (verbatim) | "VoxelTrace is research software. Independent external expert validation is pending. Results are a comparability and data-quality audit, not a clinical or regulatory determination." |
| Known limitations accepted | `<link to docs/known_limitations.md at the tagged version>` |
| Software version | `<tag>` / `<commit>`; rule-bundle sha256 `<…>` |
| Data-retention period | `<n days after final delivery>`, then deletion confirmed in writing |
| Aggregate statistics use | `<not permitted / permitted for: …>` (opt-in only) |
| Acceptance criteria | `<e.g. bundle verifies; every pair has a verdict with reasons; report walkthrough held>` |
| Sign-off | `<names, dates>` |
