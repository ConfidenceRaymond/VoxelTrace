# Transfer checklist

This is a practical checklist, not legal or compliance advice. The data-use agreement and your
institution's policies govern the transfer; where they differ from this list, they win.

## Before transfer

- [ ] **Data-use agreement:** `<DUA reference / status: NOT YET IN PLACE>`. Signed by
      `<partner signatory role>` and `<VoxelTrace signatory role>` on `<date>`. No data are sent
      before this box is ticked.
- [ ] Pilot scope signed off ([PILOT_SCOPE_TEMPLATE.md](PILOT_SCOPE_TEMPLATE.md)).
- [ ] Export de-identified by the partner under its own procedure; folder names are pseudonyms.
- [ ] Subject/timepoint/site mapping table prepared (no identifiers in it).
- [ ] Transfer method agreed: `<method>`.

## Encryption expectations

- In transit: an encrypted channel agreed with your IT (e.g. your institution's secure
  file-transfer service, or an encrypted archive with the password sent by a separate channel).
- At rest: encrypted storage, or an encrypted archive until it is unpacked on the audit machine.
- The audit runs **offline on a local machine**; data are not uploaded to any cloud service and
  no AI service receives them.

## Folder structure

```
<TRANSFER_ID>/
  data/<site>/<subject>/<visit>/...      (or data/<subject>/<visit>/...)
  mapping.csv                            subject,visit,role(baseline/followup),site
  documents/                             optional protocol sheets / attestations (no patient data)
  SHA256SUMS.txt                         see below
```

## Checksum procedure

Sender, before transfer (Linux/macOS):

```bash
cd <TRANSFER_ID>
find data mapping.csv documents -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt
```

Receiver, after transfer:

```bash
cd <TRANSFER_ID> && sha256sum -c --quiet SHA256SUMS.txt && echo TRANSFER_OK
```

The audit also records a sha256 over every input file (`inputs_sha256` in
`pilot_acceptance.json`), so the delivered results are bound to exactly the data received.

## Transfer confirmation (receiver fills in and returns)

| Field | Value |
|---|---|
| Transfer ID | |
| Received on (date) | |
| Files / total size | |
| `sha256sum -c` result | OK / FAILED (list) |
| Stored at (description, not a path shared outside the team) | |
| Confirmed by (role) | |

## Retention and deletion plan

| Item | Plan |
|---|---|
| Input DICOM | read-only copy on the audit machine; deleted `<n>` days after delivery, or as the DUA requires |
| Derived outputs (evidence bundle, delivery package) | contain no pixel data; retained `<period per DUA>` |
| Deletion | the operator deletes the input copy (VoxelTrace itself deletes nothing) and records date, method and person |
| Deletion confirmation | sent to the partner on request |
