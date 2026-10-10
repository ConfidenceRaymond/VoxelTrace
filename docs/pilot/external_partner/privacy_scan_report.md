# Privacy / security scan report (2026-10-10)

Tool: `voxeltrace.privacy_scan` (VT-PRIVACY-SCAN-1). It looks for DICOM identifier attributes
and tags (PatientName, PatientID, AccessionNumber, birth date, …), raw DICOM UIDs, local paths
(`/home/…`, `/Users/…`, `C:\Users\…`, `~/`), the development workspace name, the current
user and host names, e-mail addresses, API keys, tokens, private keys and password
assignments, hidden files and DICOM files. **This is a conservative pattern scan, not a
de-identification method and not a HIPAA, GDPR or other compliance determination.**
Raw results: `<workspace>/outputs/privacy_scan_20261010.json`.

## Shareable artefacts

| Artefact | Files | Result | Date values present |
|---|---|---|---|
| Partner starter kit folder | 97 | CLEAN | 103 (shifted public-dataset dates in the demonstration sample) |
| Starter kit ZIP: entry names | 97 entries | no hidden entries, no DICOM/image entries; all timestamps fixed at 1980-01-01 | — |
| Starter kit manifest and `.sha256` | 2 | CLEAN | — |
| Demonstration delivery package | 82 | CLEAN | 103 |
| Dry-run delivery package (public multi-site drop) | 81 | CLEAN | 303 |
| 9-pair release-check delivery package | 81 | CLEAN | 785 |
| Repository sample audit (`docs/commercialization/sample_audit`) | 12 | CLEAN | 28 |
| Repository partner packet (`docs/pilot/external_partner`) | 13 | CLEAN | 2 |

**Dates.** Dates are reported, not failed: the public datasets carry dates that were shifted by
their curators. Partner data may contain real or shifted study dates; whether they may be shared
is governed by the data-use agreement, and an operator must confirm this before delivery.

## Repository (all 461 tracked text files): secrets and e-mail addresses

| Category | Hits | Assessment |
|---|---|---|
| SECRET | 3 | not secrets: one `api_key = settings…get_secret_value()` assignment in the optional AI client (reads an optional local setting; no key stored), and two deliberate test inputs for the scanner itself |
| EMAIL | 4 | GE's published interoperability contact in two research notes (public vendor address), and two fictitious test inputs (`hospital.org`) |

No credential, token or private key is present in the repository; the `.env` file is git-ignored
and `.env.example` holds placeholders only.

## Earlier findings fixed in this release series

- Segmentation file names that were DICOM SOP Instance UIDs were written into audit outputs;
  they are now hashed unless `--input-paths-in-clear` is used.
- Runtime and template files no longer contain developer home paths (`tests/test_portability.py`).

## Operator duty

Before each delivery: `voxeltrace verify-delivery <package>` must report `"privacy_scan": "CLEAN"`;
then read the executive summary and a sample of the CSV files yourself. The scan is a safety net.
