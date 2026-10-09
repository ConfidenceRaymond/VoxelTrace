# Brain PET metadata census (OpenNeuro; metadata only, 2026-10-09)

Source: `scripts/brain_pet_census.py` -> `../data/census/openneuro_pet/brain_pet_census.json`. Read only dataset_description.json and <= 3 *_pet.json sidecars per dataset (listing capped at 3,000 keys); no image data. Categories from sidecar TracerName (else title). Planning input only: no brain rules exist.

Datasets: 37; categories: {'OTHER': 24, 'BRAIN_FDG': 6, 'AMYLOID': 1, 'TSPO': 2, 'SV2A_UCBJ': 3, 'TAU': 1}; dynamic: 20, static: 2, UNKNOWN (no sidecar read): 15; with blood data: 13; with anatomical MRI: 20; preclinical scanners: 6. Licence: CC0 except one 'not for public distribution (yet)'. All are BIDS/NIfTI: none is DICOM.

| Dataset | Category | Tracer (sidecar) | Dynamic (max frames) | Subjects | Sessions | Scanner | Blood | Anat MRI | Preclinical | Size GB |
|---|---|---|---|---|---|---|---|---|---|---|
| ds001420 | OTHER | - | UNKNOWN | 2 | 2 | - | - | yes | - | 0.61 |
| ds001421 | OTHER | SB | yes (38) | 1 | 2 | Siemens High-Resolution Research Tomograph (HRRT, CTI/Siemens) | - | yes | - | 0.31 |
| ds001705 | OTHER | LondonPride | yes (23) | 5 | 2 | Siemens Biograph mMr | - | yes | - | 3.61 |
| ds002041 | OTHER | - | UNKNOWN | 25 | 0 | - | - | - | - | 3.25 |
| ds002898 | BRAIN_FDG | FDG | yes (356) | 27 | 0 | Siemens Biograph_mMR | - | yes | - | 52.49 |
| ds003382 | BRAIN_FDG | FDG | yes (90) | 10 | 0 | SIEMENS Biograph_mMR, Siemens Biograph_mMR | yes | yes | - | 10.68 |
| ds003397 | BRAIN_FDG | FDG | yes (340) | 15 | 0 | Siemens Biograph_mMR | yes | yes | - | 76.23 |
| ds004054 | OTHER | - | UNKNOWN | 42 | 0 | - | - | yes | - | 0.46 |
| ds004230 | OTHER | [11C]PS13 | yes (33) | 16 | 2 | Siemens Biograph 64_mCT | yes | yes | - | 5.18 |
| ds004401 | OTHER | - | UNKNOWN | 1 | 0 | - | - | yes | - | 0.17 |
| ds004513 | BRAIN_FDG | FDG | yes (5) | 20 | 2 | Siemens Biograph_mMR | yes | yes | - | 44.06 |
| ds004654 | OTHER | - | UNKNOWN | 28 | 3 | - | - | - | - | 41.7 |
| ds004730 | OTHER | - | UNKNOWN | 10 | 3 | - | - | - | - | 20.11 |
| ds004731 | OTHER | - | UNKNOWN | 35 | 3 | - | - | - | - | 33.81 |
| ds004733 | OTHER | - | UNKNOWN | 18 | 4 | - | - | - | - | 54.48 |
| ds004856 | AMYLOID | AV-1451 flortaucipir, AV-45 florbetapir | no | 464 | 3 | GE Discovery MI, Siemens 962 | - | yes | - | 227.87 |
| ds004868 | OTHER | [11C]PS13 | yes (27) | 10 | 3 | Siemens petmct1 | yes | yes | - | 3.16 |
| ds004869 | OTHER | - | UNKNOWN | 27 | 4 | - | - | - | - | 8.37 |
| ds005093 | OTHER | - | UNKNOWN | 11 | 6 | - | - | - | - | 33.21 |
| ds005138 | OTHER | - | UNKNOWN | 5 | 1 | - | yes | - | - | 1.22 |
| ds005483 | OTHER | MC_1, PS_13 | yes (27) | 33 | 2 | Siemens petmct1 | yes | yes | - | 9.6 |
| ds005605 | OTHER | MC1 | yes (24) | 18 | 4 | Mediso LFER | - | - | yes | 0.38 |
| ds005619 | TSPO | - | UNKNOWN | 7 | 1 | - | - | - | - | 1.15 |
| ds005698 | OTHER | PDE4_B-PF9 | yes (33) | 25 | 4 | Siemens petmct1 | yes | yes | - | 6.72 |
| ds005895 | OTHER | PE2I | yes (16) | 25 | 4 | Molecubes NV Beta-CUBE | - | - | yes | 7.56 |
| ds006148 | OTHER | - | UNKNOWN | 266 | 3 | - | - | - | - | 2626.58 |
| ds006218 | SV2A_UCBJ | 18FSynVesT1 | yes (34) | 138 | 4 | Siemens Inveon DPET | yes | - | yes | 304.77 |
| ds006402 | SV2A_UCBJ | 18FSynVesT1, 18FUCBJ | yes (33) | 39 | 2 | Siemens Inveon DPET, Siemens Inveon MPET | yes | - | yes | 139.36 |
| ds006613 | OTHER | 11CCHDI-009R | yes (40) | 95 | 5 | Siemens Inveon MPET | yes | - | yes | 249.12 |
| ds006691 | OTHER | 18FCHDI-385 | yes (45) | 88 | 5 | Siemens Inveon MPET | yes | - | yes | 268.59 |
| ds006756 | TAU | MK6240 | yes (4) | 33 | 2 | Siemens High-Resolution Research Tomograph (HRRT) | - | yes | - | 3.29 |
| ds006917 | OTHER | PHNO | no | 7 | 2 | CPS HRRT, UIH uNeuroX | - | yes | - | 2.96 |
| ds007135 | OTHER | Martinostat | yes (7) | 25 | 0 | Siemens BrainPET Prototype Insert | - | yes | - | 5.33 |
| ds007561 | SV2A_UCBJ | UCB-J | yes (17) | 20 | 1 | Siemens Biograph Horizon | - | yes | - | 4.91 |
| ds007768 | BRAIN_FDG | - | UNKNOWN | 14 | 2 | - | - | - | - | 14.12 |
| ds007907 | TSPO | - | UNKNOWN | 147 | 0 | - | - | yes | - | 0.45 |
| ds008786 | BRAIN_FDG | FDG | yes (94) | 15 | 0 | Siemens Biograph_mMR | yes | yes | - | 10.18 |

## Top 5 future datasets (for the THEN stage; not downloaded)

1. **ds004856**: Dallas Lifespan Brain Study: amyloid (AV-45) and tau (AV-1451), human, 464 subjects, 3 sessions, GE Discovery MI; longitudinal static SUVR-type data
2. **ds006756**: [18F]MK6240 tau, human, 33 subjects, 2 sessions, HRRT, dynamic: tau tracer-specific rules and repeat sessions
3. **ds007561**: [11C]UCB-J SV2A, human, 20 subjects, Siemens Biograph Horizon, dynamic, with T1w MRI
4. **ds003382**: FDG functional PET on Siemens Biograph mMR (PET/MR), human, dynamic (90 frames), arterial blood: kinetic + PET/MR provenance
5. **ds005698**: [18F]PF-PDE4B test-retest, human, 25 subjects, 4 sessions, Siemens mCT, dynamic with blood: repeatability

Notes: tracer families are labels for planning only; amyloid/tau/TSPO/SV2A reference regions and kinetic models are tracer-specific and NOT implemented. Preclinical datasets (Inveon, Mediso, Molecubes) are out of scope for human trial audit.
