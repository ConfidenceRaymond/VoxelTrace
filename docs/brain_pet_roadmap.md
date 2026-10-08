# Brain PET roadmap (future workstream; planning only)

RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS.

**Planning only:**
- No OpenNeuro data has been downloaded.
- No brain rule has been implemented.
- The current whole-body rules (QIBA FDG, EANM FDG, PERCIST, VT-*) are unchanged.

## Order

| Stage | Workstream |
|---|---|
| CURRENT | multi-vendor longitudinal PET/CT validation (ACRIN-NSCLC-FDG-PET; see `docs/next_candidates_acrin.md`) |
| NEXT | multi-tracer PET/CT (whole-body, non-FDG tracers; census of other collections) |
| THEN | **Brain PET + OpenNeuro metadata census** (this document) |
| LATER | PET/MR |

## Principles

1. **PERCIST liver/blood-pool rules do not apply to brain PET.**
   - PERCIST-LIVER-SUL-STABILITY, PERCIST-BASELINE-MEASURABLE and the liver/aorta reference
     proposer are whole-body FDG oncology concepts.
   - A brain rule set must never inherit them, and the rule registry must refuse a whole-body
     rule set on a brain study.
2. **Reference regions are tracer- and task-specific.** Each brain rule set names its own
   reference region, cites its source, and goes through the same human review gate
   (proposal → ACCEPT/ADJUST/REJECT; never automatic). Typical choices, still to be confirmed
   against each tracer's published method:

   | Tracer / task | Typical reference | Caveat |
   |---|---|---|
   | Amyloid | whole cerebellum, cerebellar grey or pons (e.g. Centiloid pipelines) | |
   | Tau | inferior cerebellar grey matter | |
   | Brain FDG | pons, or global/whole-brain normalisation | |
   | TSPO | often **no valid reference region** | arterial input or explicitly labelled pseudo-reference methods |
   | SV2A (e.g. [11C]UCB-J) | centrum semiovale (white matter) used as a pseudo-reference | known bias, documented |

3. **Common core is reused, not forked.** Ingestion, slice ordering, provenance manifests,
   anonymisation audit, strict activity/SUV validation where applicable, the
   comparability/assessability layers, the reconstruction evidence trust model and the
   review gates are shared. Brain-specific pieces sit beside them as new, versioned rule sets
   and extractors.
4. **Missing evidence is never identity.** The UNKNOWN / INSUFFICIENT_INFORMATION semantics of
   the whole-body work carry over unchanged.

## Scope by modality / task (future)

| Area | What VoxelTrace would need | Notes |
|---|---|---|
| Brain FDG | static SUV/SUVR; reference-region rules; same-scanner/reconstruction identity | dementia vs epilepsy tasks differ |
| Amyloid | SUVR and Centiloid-style scaling; tracer-specific uptake windows; reference region | tracer windows from tracer labelling / QIBA amyloid profile (to be read) |
| Tau | SUVR; tracer-specific windows; off-target binding caveats | |
| TSPO / neuroinflammation | genotype (binding affinity) as a required covariate; arterial input or explicit pseudo-reference | refuse SUVR "by default" |
| SV2A / UCB-J | dynamic acquisition; pseudo-reference choice explicit | |
| Dynamic PET | frame timing validation (FrameReferenceTime, ActualFrameDuration per frame); decay correction per frame; motion | extends the decay-timing lessons from `vendor_decay_timing.md` |
| Kinetic modelling | input function provenance (arterial / image-derived / reference tissue); model identity (e.g. Patlak, SRTM, Logan) as part of protocol identity | model and input are first-class provenance |
| PET/MR | MR-based attenuation correction method as a reconstruction parameter; different DICOM conventions | LATER stage |

## OpenNeuro metadata census (future, THEN stage)

- **Read-only metadata first.** Read the PET-BIDS `*_pet.json` sidecars and
  `participants.tsv` only. No image download in the first pass.
- **PET-BIDS fields to census:**
  - tracer: TracerName, TracerRadionuclide;
  - injection: InjectedRadioactivity, InjectedMass, ModeOfAdministration;
  - timing: TimeZero, ScanStart, InjectionStart, FrameTimesStart, FrameDuration;
  - reconstruction: ReconMethodName, ReconMethodParameterLabels/Units/Values,
    ReconFilterType/Size, AttenuationCorrection;
  - scanner: Manufacturer, ManufacturersModelName, SoftwareVersions.
- **Trust level.** BIDS sidecar values are converter or curator output, not scanner DICOM.
  Their trust level must be decided before use. They are **not** LEVEL_A by default.
- **Outputs:** completeness by tracer and by field, longitudinal/test-retest subsets, and
  candidate datasets ranked by decidability, as done for ACRIN.

## OpenNeuro metadata snapshot (2026-10-08; metadata only)

**Query:** one OpenNeuro GraphQL query for datasets with modality `pet`. No files were
downloaded. The raw response is stored at
`../data/census/openneuro_pet/graphql_pet_datasets_2026-10-08.json`.

**Result:** 37 datasets. The tracer and topic grouping below is **from dataset titles only**.
Tracer, species, static/dynamic and scanner must be confirmed from the `*_pet.json` sidecars in
the future census step.

| Group (by title) | Datasets | Notes |
|---|---|---|
| FDG / glucose metabolism, incl. functional PET (fPET) | ds002898, ds003382, ds003397 (Monash, PET/MR), ds004054, ds004513, ds006148, ds007768, ds008786 | fPET datasets are dynamic; several PET/MR |
| Amyloid / tau | ds004856 (Dallas Lifespan Brain Study, 464 subjects, 3 sessions), ds006756 ([18F]MK6240 tau) | longitudinal sessions present in ds004856 |
| TSPO / neuroinflammation | ds005619 ([18F]SF51), ds007907 (TSPO in skull marrow), ds005093 (microglia activation markers) | reference-region caveats apply |
| SV2A / synaptic density | ds006402 ([18F]SynVesT-1, [18F]UCB-J), ds007561 (UCB-J), ds006218 (SynVesT-1, longitudinal) | some may be preclinical: verify |
| Serotonin / dopamine receptor ligands | ds001420 ([11C]DASB), ds001421 ([11C]SB207145), ds001705 (NRM2018 challenge), ds002041 (D2), ds005895 | kinetic modelling datasets |
| COX-1 ([11C]PS13 etc.) | ds004230, ds004401, ds004868, ds005483, ds005605 (rodents) | |
| Cerebral protein synthesis | ds004654, ds004730, ds004731, ds004733 | dynamic, arterial input likely |
| Test-retest / methods | ds005698 (test-retest), ds004869, ds005138 (motion benchmark), ds006613, ds006691 (CHDI ligands) | test-retest suits repeatability work |
| Dedicated brain scanner | ds006917 (NeuroEXPLORER) | ultra-high-resolution brain PET; scanner metadata to be checked |

**Implications for the roadmap:**
- **No DICOM.** OpenNeuro holds BIDS (NIfTI + JSON). The strict DICOM SUV path does not apply;
  a separate, explicitly lower-trust BIDS-sidecar evidence path would be needed.
- **Mostly not oncology SUV studies.** Most datasets are dynamic research PET for kinetic
  modelling, which confirms that brain support needs dynamic and kinetic provenance first.
- **Longitudinal data exists.** Some datasets have several sessions (ds004856, ds006218,
  ds006613, ds006691), which suits a future repeatability or longitudinal census.
- **PET/MR and NeuroEXPLORER** appear (ds002898/ds003382/ds003397, ds006917). They feed the
  LATER PET/MR stage and United Imaging-adjacent tracking, but only as NIfTI.

## User-supplied brain studies

These first undergo a **read-only inventory**, the same as `inventory_recon_metadata.py`:
- all standard and private fields;
- trust levels;
- missing items;
- what the site should provide.

That happens before any quantification or rule evaluation.

## Not in scope now

- Brain rules, brain reference-region proposers, and kinetic modelling code.
- OpenNeuro downloads.
- Any change to whole-body rules or thresholds.
