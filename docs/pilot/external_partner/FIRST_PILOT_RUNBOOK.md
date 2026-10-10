# First pilot runbook (operator)

Exact commands, offline, on the audit machine. `<WS>` = a working folder outside the received
data; `<TRANSFER_ID>` = the received transfer. Every output folder must be new; nothing is ever
overwritten. No AI model is used.

## 0. Environment (once)

```bash
cd <repo>                                  # VoxelTrace at tag v0.4.0-rc1 or later
git describe --tags                        # record in the pilot log
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[app,dev]" -c constraints/tested-py312-x86_64.txt
voxeltrace --version                       # record version, rule bundle sha256, schemas
python -m pytest -q                        # must pass before handling partner data
```

## 1. Receive and verify the transfer

```bash
cd <TRANSFER_ID> && sha256sum -c --quiet SHA256SUMS.txt && echo TRANSFER_OK
chmod -R a-w <TRANSFER_ID>/data            # read-only from here on
```

Fill in the transfer confirmation in [TRANSFER_CHECKLIST.md](TRANSFER_CHECKLIST.md).

## 2. First look

```bash
voxeltrace validate-input <TRANSFER_ID>/data
```

`MULTIPLE_STUDIES_IN_SCAN` / `MULTIPLE_PATIENTS_IN_SCAN` means the drop is nested
(site/subject/visit): go to step 3a. A `<subject>/<visit>` layout goes to step 3b.

## 3a. Nested drop: map, review, stage

```bash
voxeltrace intake-map <TRANSFER_ID>/data --out <WS>/intake_mapping.json \
    --stage <WS>/trial --trial-id <PILOT-ID> [--timepoint-map "Week 6=followup" ...]
```

Exit 2 = some scans are `NEEDS_REVIEW` and were not staged. Read the printed mapping, resolve
each question with the partner (mapping table, or which series to use), and map again into a
new `--stage` folder. `intake_mapping.json` stays internal (it contains source paths).

## 3b. Flat drop: configuration outside the input

`run-pilot` writes the configuration itself when given `--trial-id`. To declare sites (needed
for meaningful site summaries), write it first:

```bash
voxeltrace init-trial <TRANSFER_ID>/data --trial-id <PILOT-ID> --timepoints baseline followup
```

(this writes `trial.yaml` into the folder; if the folder is read-only, copy the subject folders
as symlinks into `<WS>/trial` first and run it there), then add `sites: {SUBJ: SITE, ...}`.

## 4. Run the pilot

```bash
voxeltrace run-pilot --input <WS>/trial --output <WS>/pilot_v1
echo "exit $?"     # 0 complete (review may be pending), 1 AUDIT_BLOCKED, 2 NEEDS_REEXPORT/usage, 3 UNSUPPORTED
cat <WS>/pilot_v1/PILOT_SUMMARY.md
```

If `AUDIT_BLOCKED`: read `blocking_reasons` in `pilot_acceptance.json`
(`pairing/pairing_audit.json` for layout problems), fix with the partner, re-run into a new folder.

## 5. Verify

```bash
voxeltrace verify-bundle <WS>/pilot_v1/audit/audit_bundle          # "status": "OK"
voxeltrace verify-delivery <WS>/pilot_v1/delivery_package          # "status": "OK", privacy CLEAN
voxeltrace list-reviews <WS>/pilot_v1/audit/audit_bundle           # pending human reviews
grep TEXT_IMPLIED <WS>/pilot_v1/delivery_package/pair_results.csv  # cases for the review packet
voxeltrace explain-pair <WS>/pilot_v1/audit/audit_bundle --subject <SUBJ>
```

## 6. Deliver

Work through [PILOT_DELIVERY_CHECKLIST.md](PILOT_DELIVERY_CHECKLIST.md), then send
`<WS>/pilot_v1/delivery_package` through the agreed channel.

## 7. After partner review

Reference-region and lesion decisions are recorded by the partner's reviewer (app pages or
`voxeltrace lesion-review ... --confirm`). Re-run into a **new** folder (`pilot_v2`) and deliver
again; earlier bundles stay unchanged.

## 8. Close

Collect the [PILOT_FEEDBACK_FORM.md](PILOT_FEEDBACK_FORM.md); execute the retention/deletion plan
and record it.
