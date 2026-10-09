# Audit summary: VOXELTRACE-DEMONSTRATION-AUDIT

RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS

| Subjects | Pairs | Real pairs | Scans | Pending reference reviews |
|---|---|---|---|---|
| 9 | 7 | 0 | 16 | 4 |

## Verdicts

| Rule set | ASSESSABLE | ASSESSABLE_WITH_WARNINGS | INSUFFICIENT_INFORMATION | NOT_ASSESSABLE |
|---|---|---|---|---|
| qiba-fdg-1.14 | 1 | 0 | 2 | 4 |
| eanm-fdg-2.0 | 1 | 0 | 2 | 4 |
| percist-1.0 | 1 | 0 | 2 | 4 |

## Top blocking reasons (pairs affected, any rule set)

| Reason | Pairs | Rule sets | Site can fix | Recommendation |
|---|---|---|---|---|
| EANM-SAME-SYSTEM-SETTINGS FAIL | 3 | eanm-fdg-2.0 | NO | criterion not met (identical acquisition/reconstruction/correction settings: manufacturer, scanner_model, image_units, decay_correction, correction_state, voxel_size, reconstruction_method, iterations, subsets, time_of_flight, psf_resolution_modelling, post_filter); a re-export cannot change measured values |
| VT-PROTOCOL-IDENTITY FAIL | 3 | eanm-fdg-2.0, percist-1.0, qiba-fdg-1.14 | NO | criterion not met (identical acquisition/reconstruction/correction settings: manufacturer, scanner_model, image_units, decay_correction, correction_state, voxel_size, reconstruction_method, iterations, subsets, time_of_flight, psf_resolution_modelling, post_filter); a re-export cannot change measured values |
| AMBIGUOUS_RECONSTRUCTION | 1 | eanm-fdg-2.0, percist-1.0, qiba-fdg-1.14 | YES | provide reconstruction protocol (algorithm, iterations, subsets, TOF, PSF, filter, voxel size) from the site imaging manual or structured attributes |
| EANM-UPTAKE-DIFF FAIL | 1 | eanm-fdg-2.0 | NO | criterion not met (|follow-up - baseline| <= 10.0 min); a re-export cannot change measured values |
| EANM-UPTAKE-WINDOW FAIL | 1 | eanm-fdg-2.0 | NO | criterion not met (55.0 <= uptake <= 75.0 min at every timepoint); a re-export cannot change measured values |

## Executive summary

VOXELTRACE-DEMONSTRATION-AUDIT: 7 baseline/follow-up pair(s) from 9 subject(s), 16 scan(s); 0 pair(s) are real data.
qiba-fdg-1.14: 1 ASSESSABLE, 2 INSUFFICIENT_INFORMATION, 4 NOT_ASSESSABLE.
eanm-fdg-2.0: 1 ASSESSABLE, 2 INSUFFICIENT_INFORMATION, 4 NOT_ASSESSABLE.
percist-1.0: 1 ASSESSABLE, 2 INSUFFICIENT_INFORMATION, 4 NOT_ASSESSABLE.
1 scan(s) cannot be quantified as exported (preflight DO_NOT_QUANTIFY).
4 reference-region proposal(s) await a human decision; until then the dependent rules stay UNKNOWN.
Recommended actions, most frequent blocking reason first:
1. EANM-SAME-SYSTEM-SETTINGS FAIL (3 pair(s); site can fix: NO): criterion not met (identical acquisition/reconstruction/correction settings: manufacturer, scanner_model, image_units, decay_correction, correction_state, voxel_size, reconstruction_method, iterations, subsets, time_of_flight, psf_resolution_modelling, post_filter); a re-export cannot change measured values.
2. VT-PROTOCOL-IDENTITY FAIL (3 pair(s); site can fix: NO): criterion not met (identical acquisition/reconstruction/correction settings: manufacturer, scanner_model, image_units, decay_correction, correction_state, voxel_size, reconstruction_method, iterations, subsets, time_of_flight, psf_resolution_modelling, post_filter); a re-export cannot change measured values.
3. AMBIGUOUS_RECONSTRUCTION (1 pair(s); site can fix: YES): provide reconstruction protocol (algorithm, iterations, subsets, TOF, PSF, filter, voxel size) from the site imaging manual or structured attributes.
4. EANM-UPTAKE-DIFF FAIL (1 pair(s); site can fix: NO): criterion not met (|follow-up - baseline| <= 10.0 min); a re-export cannot change measured values.
5. EANM-UPTAKE-WINDOW FAIL (1 pair(s); site can fix: NO): criterion not met (55.0 <= uptake <= 75.0 min at every timepoint); a re-export cannot change measured values.
These recommendations are the catalogued remediations of the observed reason codes. They do not change any verdict.
