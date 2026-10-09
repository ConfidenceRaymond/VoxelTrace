# Pilot SOP: VoxelTrace Retrospective PET Comparability Audit

**Audience:** an operator other than the developer.

**Prerequisites:**
- Python 3.11 or 3.12;
- the installation in [deployment.md](deployment.md);
- a de-identified trial folder per [data_requirements.md](data_requirements.md).

RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS. The audit assesses comparability and
assessability only, never treatment response.

## 1. Receive data

1. Receive a de-identified copy under a data-use agreement. Record the source, date and
   transfer checksum.
2. Place it read-only (`chmod -R a-w <trial>`). VoxelTrace never writes into the input.
3. Check that subject folders are pseudonyms. Rename before use if they are not, and record
   the mapping outside VoxelTrace.

## 2. Inspect and preflight

```bash
voxeltrace inspect <trial>/<subject>/<timepoint>          # what series are there
voxeltrace preflight <trial> --out <work>/preflight          # READY / WARNINGS / DO_NOT_QUANTIFY / NEEDS_REVIEW
```

- Review `preflight.csv`. For **DO_NOT_QUANTIFY** scans, decide whether to request
  re-exports before the audit; the reason codes carry remediation text.
- **NEEDS_REVIEW** (e.g. several PET series) means selecting the AC PET series and supplying
  only that.

## 3. Audit

```bash
voxeltrace audit --input <trial> [--config <cfg>/trial.yaml] --output <work>/audit_v1 --qc-images
voxeltrace verify-bundle <work>/audit_v1/audit_bundle
voxeltrace summarize <work>/audit_v1/audit_bundle
```

Each run writes a **new** output directory; bundles are never overwritten.

## 4. Human review (required for PERCIST)

1. Run `voxeltrace list-reviews <bundle>` to list the pending liver / blood-pool proposals.
2. A qualified reviewer opens the app's **Reference Review** page
   (`scripts/run_app.sh`, page 4). They inspect each proposal's QC image and record
   ACCEPT / ADJUST / REJECT with their identifier.
   - Decisions are written to the trial's `reference_review.yaml`, bound to the proposal hash.
   - Software never records a decision.
3. Re-run the audit into a new output directory.

## 5. Site queries and attestations

1. Open `reports/site_queries.md`. Every query is a **DRAFT SITE QUERY**.
2. Edit, approve and send it through the sponsor's channel. VoxelTrace sends nothing.
3. For missing reconstruction parameters, **QIBA only**, follow
   [attestation_workflow.md](attestation_workflow.md):
   - `attestation-template`;
   - the site completes and signs it;
   - `validate-attestations`;
   - re-audit with `--attestations`.

## 6. Adjudication (optional, human only)

A qualified reviewer may record CONFIRM / OVERRIDE_WITH_EVIDENCE / REQUEST_SITE_INFORMATION /
UNRESOLVED for a pair:

```bash
voxeltrace adjudicate --log <work>/adjudications.jsonl --id ADJ-001 --subject ... \
  --result-sha256 <sha256 of the automated pair result> ... --reviewer <id> --role PET_PHYSICIST --confirm
```

- The automated verdict is never changed.
- Pass the log to the next audit with `--adjudications`.

## 7. Deliver

Deliver the bundle directory:
- `reports/AUDIT_PACKAGE_REPORT.md`;
- `pair_verdicts/`;
- `preflight/`;
- `protocol/drift_events.csv`;
- `reports/site_queries.md`;
- `manifest.json` and `checksums.sha256`.

The recipient runs `voxeltrace verify-bundle` on receipt.

## 8. Retention / deletion

- Follow the data-use agreement.
- Bundles contain no pixel data. Input data deletion is the operator's action; VoxelTrace
  deletes nothing.
- Record the deletion date in the pilot log.

## Report outputs (`reports/` in the bundle)

| File | Content |
|---|---|
| `EXECUTIVE_SUMMARY.md`, `executive_summary.json` | Top page: subject, pair, scan and pending-review counts; verdicts per rule set; the 5 most frequent blocking reasons (pairs affected) with their catalogued remediation; fixed-template summary sentences |
| `AUDIT_PACKAGE_REPORT.md` | The top page, followed by the full per-rule-set report |
| `AUDIT_PACKAGE_REPORT.pdf` | The same text as a PDF without timestamps or random IDs: identical audits give identical bytes |

Recommendations are not written freely. Each one is the `remediation` text from the reason
catalogue (`trial/reasons.py`, then `preflight/reasons.py`) of a reason code that occurred.
They never change a verdict. `voxeltrace summarize <bundle>` prints the executive summary.
