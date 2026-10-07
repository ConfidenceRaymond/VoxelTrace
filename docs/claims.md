# Claim gating

`src/voxeltrace/evidence/claims.py`, rules version `claims-1`.

- Claims are produced and checked by **deterministic rules. No LLM is involved.**
- In a later milestone, any claim an LLM makes must pass the same gate.

## ClaimEvidence

| Field | Meaning |
|---|---|
| `claim_id`, `claim_type`, `statement` | identity and wording |
| `status` | one of the four statuses below |
| `rule` | the rule that decided the status |
| `supporting_measurements` | measured values backing the claim |
| `supporting_protocol_evidence` | protocol facts backing the claim |
| `conflicting_evidence` | measured values or facts that contradict it |
| `missing_evidence` | evidence that would be needed but is absent |
| `assumptions` | assumptions the claim rests on |
| `limitations` | always includes "research prototype" and "validated only for the implemented SUV path" |

## Statuses

- **SUPPORTED**: the evidence directly establishes the claim under the rule.
- **PARTIALLY_SUPPORTED**: the evidence points the same way but is weaker, for example a
  protocol fact taken from vendor free text, or comparability with warnings.
- **NOT_ESTABLISHED**: required evidence is missing, or the claim type is out of scope.
- **CONTRADICTED**: a measured value or protocol fact contradicts the claim.

## Rules

| Claim | Rule |
|---|---|
| A. "SUVmax/SUVmean/SUVmedian/SUVpeak/MTV/TLG is X" | **SUPPORTED** only if SUV passed, the segment is measured, and \|measured − X\| ≤ half a unit in X's last stated decimal. **CONTRADICTED** if measured and different. **NOT_ESTABLISHED** if SUV was refused, the segment is missing, or the metric is unavailable (e.g. SUVpeak `NOT_AVAILABLE`) |
| B. "MTV is X mL" | as A. The limitation states that MTV is the volume of the supplied segmentation |
| Protocol facts (attenuation/scatter/randoms corrected, TOF, PSF) | **SUPPORTED** from a standard attribute. At most **PARTIALLY_SUPPORTED** when derived from free text. **CONTRADICTED** if the attribute says otherwise. **NOT_ESTABLISHED** if missing |
| C. "Uptake decreased/increased between A and B" | All of these are required: both scans quantified (SUV passed), the metric measured on both, target correspondence **explicitly confirmed** by the caller, and a comparability assessment. Then: **SUPPORTED** if `COMPARABLE` and the computed % change is in the claimed direction; **PARTIALLY_SUPPORTED** if `COMPARABLE_WITH_WARNINGS`; **CONTRADICTED** if the change is in the opposite direction (or zero); **NOT_ESTABLISHED** if anything is missing, or if `NOT_COMPARABLE` / `INSUFFICIENT_INFORMATION` |
| D. Treatment response | **always NOT_ESTABLISHED**. PERCIST is not implemented, and clinical context is absent |
| Diagnosis (e.g. "malignant") | **always NOT_ESTABLISHED** |
| E. "Image noise is elevated" | **NOT_ESTABLISHED**. There is no validated noise metric or reference criterion |

- **Change claims are measurement-only.** A SUPPORTED decrease means the measured value fell
  under comparable protocols. It does not establish biological change or treatment response,
  and test-retest repeatability thresholds are not applied yet.
