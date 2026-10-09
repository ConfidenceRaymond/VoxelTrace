# Reviewer form (one per case)

The form is a YAML file, `responses/CASE-nnn.response.yaml`. It is generated empty, and the
software never fills it in. Fields:

| Field | Values | Required |
|---|---|---|
| `case_id` | pre-filled | — |
| `reviewer_id` | your identifier, as agreed with the coordinator | yes |
| `reviewer_role` | PET_PHYSICIST, NUCLEAR_MEDICINE_PHYSICIAN, RADIOLOGIST, IMAGING_CORE_LEAD, TRIAL_QC_REVIEWER | yes |
| `independent_verdicts.<standard>` | ASSESSABLE, ASSESSABLE_WITH_WARNINGS, NOT_ASSESSABLE, INSUFFICIENT_INFORMATION | yes, one per standard |
| `confidence` | low, medium, high | yes |
| `reason` | free text: the main fact(s) behind your answer | yes |
| `missing_evidence` | free text: what would let you decide (if anything) | if relevant |
| `rules_disagreed` | list (second, unblinded round only) | no |
| `disagreement_reason` | free text (second round only) | no |
| `review_time_min` | number of minutes spent on this case | yes |
| `simulated` | must stay `false` | — |

Example of a filled answer block (illustrative format only, not a real answer):

```yaml
independent_verdicts:
  qiba-fdg-1.14: INSUFFICIENT_INFORMATION
  eanm-fdg-2.0: INSUFFICIENT_INFORMATION
  percist-1.0: INSUFFICIENT_INFORMATION
confidence: medium
reason: reconstruction parameters differ between the two exports and cannot be confirmed
missing_evidence: site confirmation of the follow-up reconstruction settings
review_time_min: 9
```

Forms without `reviewer_id` or without any answer are treated as not returned and are never
scored. Forms marked `simulated: true` are excluded from scoring.
