# Trial rule library (versioned, source-cited)

Code: `src/voxeltrace/rules/`. Sources were read in the primary texts on 2026-10-07. Each rule
records its citation, locator, quoted text and verification level (`PRIMARY_TEXT` or
`PRIMARY_TEXT_VIA_FETCH`).

## Principles

- **One standard per rule set**, plus explicit **VOXELTRACE** engineering prerequisites.
  `get_ruleset` refuses any rule set that mixes standards.
- Standards are mixed only through an explicit, justified trial override.
- The VoxelTrace prerequisites deliberately **exclude** uptake time and dose, whose limits are
  standard-specific.
- Overrides come from YAML/JSON (`TrialConfig`):
  - parameter changes must name existing parameters;
  - disabling a rule needs a written justification;
  - every override is recorded in the rule-set version (`+<trial_id>`).
  - Overrides are never parsed from free text.
- Only rules with verified text are implemented. Anything else is listed under
  `DOCUMENTED_NOT_IMPLEMENTED`.

## Rule sets

### `qiba-fdg-1.14`: QIBA FDG-PET/CT Profile v1.14 (2016, updated 2023)

| Rule | Logic | Impact | Source |
|---|---|---|---|
| QIBA-UPTAKE-WINDOW | 55 ≤ uptake ≤ 75 min at each timepoint | blocking | §3.2.1.1 |
| QIBA-UPTAKE-DIFF | \|Δ\| ≤ 10 min, no scan before 55 min | blocking | §3.2.1.1 |
| QIBA-SAME-SYSTEM | same scanner model and software ("strongly recommended") | warning | longitudinal recommendation |

Not implemented:
- the Claim (wCV 10–12 %; −28 %/+39 %), which is response-level;
- a liver limit (the Profile sets no numeric value);
- glucose, which is study-specified.

### `percist-1.0`: PERCIST 1.0 (Wahl 2009), boundaries from Practical PERCIST (2016)

| Rule | Logic | Impact | Source |
|---|---|---|---|
| PERCIST-UPTAKE-WINDOW | 50–70 min at each timepoint | warning | Practical PERCIST |
| PERCIST-UPTAKE-DIFF | \|Δ\| ≤ 15 min, every scan ≥ 50 min ("to be assessable") | blocking | PERCIST 1.0 Table |
| PERCIST-LIVER-SUL-STABILITY | \|Δ liver SULmean\| ≤ 20 % of the larger **and** ≤ 0.3 SUL | blocking | PERCIST Table; Practical PERCIST |
| PERCIST-DOSE-DIFF | \|Δ\|/baseline ≤ 20 % | warning | Practical PERCIST (assumption: relative to baseline) |
| PERCIST-SAME-SCANNER-SOFTWARE | same model and software ("should") | warning | PERCIST Table |
| PERCIST-BASELINE-MEASURABLE | SULpeak ≥ 1.5 × liver SULmean + 2 SD | blocking | PERCIST 1.0 text and Fig. 3 |

- **SUL formula:** `LBMJAMES128`, as suggested by Practical PERCIST. PERCIST 1.0 itself gives
  no equation.
- **Not implemented:**
  - the blood-pool fallback (PERCIST 1.0 text and table disagree on the +2 SD term);
  - fasting and glucose;
  - response categories.
- **Numerical tolerance:** inclusive boundaries are compared with a 1e-9 tolerance. This covers
  floating-point representation only; it does not change the criterion.

### `eanm-fdg-2.0`: EANM FDG PET/CT procedure guideline v2.0 (Boellaard 2015)

| Rule | Logic | Impact | Source |
|---|---|---|---|
| EANM-UPTAKE-WINDOW | 55–75 min | blocking | preparation/administration section |
| EANM-UPTAKE-DIFF | same uptake interval within 10 min | blocking | same section ("essential") |
| EANM-SAME-SYSTEM-SETTINGS | same system and identical acquisition/reconstruction | blocking | same section |
| EANM-EARL-RECON | EARL-approved reconstruction (from the trial configuration; not in DICOM) | warning | "PET image reconstruction" |

- **SUL formula:** `LBMJANMA`, when SUL is needed.
- **Limited view:** the 5-minute rule for limited-view imaging is not modelled.

### VOXELTRACE prerequisites (in every rule set; not a published standard)

| Rule | Logic |
|---|---|
| `VT-SUV-BOTH` | strict SUVbw PASS at both timepoints |
| `VT-TRACER-SAME` | same tracer |
| `VT-PROTOCOL-IDENTITY` | scanner, units, decay correction, correction state, voxel size and reconstruction parameters identical |

All three are blocking.

## Verdicts

Rules are applied in this order:

1. **NOT_ASSESSABLE**: any blocking check FAILs.
2. **INSUFFICIENT_INFORMATION**: any blocking check is UNKNOWN.
3. **ASSESSABLE_WITH_WARNINGS**: any warning-level check FAILs or is UNKNOWN.
4. **ASSESSABLE**: none of the above.

Every check records the rule, the observed value, the expected condition, PASS/FAIL/UNKNOWN,
the source, and actionable reason codes.

## Lean body mass (`quant/sul.py`)

| Code | Formula | Units | Sources |
|---|---|---|---|
| LBMJAMES128 | M: 1.10·W − 128·(W/H)²; F: 1.07·W − 148·(W/H)² | W kg, H cm | QIBA v1.14 §4.4.2; Practical PERCIST |
| LBMJANMA | M: 9270·W/(6680 + 216·BMI); F: 9270·W/(8780 + 244·BMI) | BMI = W/H², H in m | EANM v2.0; Tahari 2014 |

- James is refused beyond its maximum (W* = a·H²/2b).
- QIBA Appendix H prints the Janmahasatian formula with a typo ("/" instead of "+"); it was not
  used.
- The incorrect male coefficient 120 (DICOM SUV Type "LBM") is not implemented.
