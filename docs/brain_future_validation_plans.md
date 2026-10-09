# Brain PET: top-3 future validation candidates per category (plans only)

Status 2026-10-09:

- **Nothing has been downloaded, and nothing will be under this plan.** Selection uses only
  the existing 37-dataset OpenNeuro metadata census (`docs/brain_pet_census.md`,
  `../data/census/openneuro_pet/brain_pet_census.json`).
- **No brain quantification is implemented.** VoxelTrace's only brain capability is the
  read-only intake `voxeltrace inspect-brain` (VT-BRAIN-INTAKE-1).
- **No PET/MR implementation is added.** For PET/MR datasets only BIDS provenance is
  inventoried, for example MR-based attenuation correction.

All eight selected datasets declare **CC0** in the census. The licence must be re-read from
each dataset's `dataset_description.json` at the pinned version before any future use.

## Selection

| Category | Rank | Dataset (version) | Why | Size | Key metadata (census) |
|---|---|---|---|---|---|
| Brain FDG | 1 | ds004513 (1.0.6) | FDG with **2 sessions** (repeatability-style), blood data, 20 subjects | 44.1 GB | Siemens Biograph mMR (PET/MR); OP-OSEM + MoCo + 6 mm smoothing; pseudo-CT AC; 5 frames; derivatives present |
| Brain FDG | 2 | ds008786 (1.0.1) | smallest FDG set with blood and a fully structured recon string | 10.2 GB | mMR; `OP-OSEM4i21s`; measured AC; 94 frames |
| Brain FDG | 3 | ds003382 (1.5.0) | dynamic FDG with arterial blood; UTE-based AC (a provenance stress test) | 10.7 GB | mMR; PSF-OP-OSEM; 90 frames; no derivatives |
| Amyloid / tau | 1 | ds004856 (1.3.0) | amyloid (florbetapir) and tau (flortaucipir), 464 subjects, 3 waves, **two vendors** (GE Discovery MI, Siemens) | 227.9 GB (listing truncated) | static (1 frame); VPHD / back-projection; CT AC; derivatives present |
| Amyloid / tau | 2 | ds006756 (1.0.0) | [18F]MK6240 tau, 2 sessions, small | 3.3 GB | Siemens HRRT; 3D-OP-OSEM; transmission AC; 4 frames |
| Amyloid / tau | 3 | none | the census holds no third amyloid or tau dataset; a broader OpenNeuro search is needed | — | — |
| Dynamic / kinetic | 1 | ds005698 (1.0.0) | [18F]PF-06445974 **test-retest**, 4 sessions, blood | 6.7 GB | Siemens mCT; PSF + TOF; 33 frames; derivatives present |
| Dynamic / kinetic | 2 | ds004230 (3.0.0) | [11C]PS13, 2 sessions, arterial blood | 5.2 GB | Siemens Biograph 64 mCT; PSF + TOF; 33 frames |
| Dynamic / kinetic | 3 | ds007561 (1.0.0) | [11C]UCB-J dynamic **without blood** (reference-tissue case), T1w MRI | 4.9 GB | Siemens Biograph Horizon; 3D OSEM; 17 frames |

ds003382 is listed under FDG. It is also the FDG kinetic candidate, but it is not counted
twice.

## Future validation plan (same structure for each dataset)

Each step is a gate. A step starts only after the previous one passes and is written down.

1. **Pin and licence.** Record the dataset version, `dataset_description.json` licence and
   citation (DOI), and the exact file list from the OpenNeuro listing. A frozen download plan
   is written and committed **before** any byte is fetched, as for the PET/CT pairs.
2. **Sidecars only, about 1 MB per subject.** Download `*_pet.json`, `*_blood.json`/`.tsv`
   headers and `participants.tsv` for 2–3 subjects. Run `voxeltrace inspect-brain` and check
   that every provenance field it reports matches the sidecar text:
   - tracer, injected radioactivity and units;
   - time zero and frame timing;
   - decay correction factors;
   - reconstruction and attenuation correction;
   - scanner;
   - blood availability.
3. **Define success before images.** For each category, write the tracer-specific evidence a
   future rule set would need, together with its source:
   - FDG: glucose and fasting not in images, frame timing, reference-free SUV versus kinetic;
   - amyloid/tau: reference region, SUVR window, tracer-specific cut-offs;
   - kinetic: input function type, frame completeness, decay-correction reference.

   VoxelTrace would refuse, never assume, any of these that is missing.
4. **One subject's images (bounded).** Only if steps 1–3 pass: one subject, all sessions, with
   hashes. Check geometry, frame timing against the sidecar, units and decay correction
   against the sidecar, and the test-retest or session structure. **No SUV, SUVR or kinetic
   value is computed** until a brain rule set exists and has been reviewed.
5. **Report.** Per dataset, list which provenance fields were present, missing or
   inconsistent, and what a future rule set would refuse. No quantitative claim is made.

## What each category would eventually test

- **Brain FDG (ds004513, ds008786, ds003382):**
  - timing and decay-correction provenance on PET/MR exports;
  - MR-based attenuation-correction provenance (pseudo-CT, UTE) recorded as a protocol field;
  - repeat-session structure (ds004513).
- **Amyloid/tau (ds004856, ds006756):**
  - tracer-specific intake (VoxelTrace already marks these UNSUPPORTED for the FDG rule sets);
  - cross-vendor provenance (GE vs Siemens in ds004856);
  - longitudinal waves.
- **Dynamic/kinetic (ds005698, ds004230, ds007561):**
  - frame-timing completeness;
  - blood versus no-blood input provenance;
  - test-retest session pairing (ds005698).

## Explicitly not planned

- Downloads now.
- Any brain quantification, SUVR or kinetic modelling.
- PET/MR attenuation-correction modelling.
- Preclinical datasets (Inveon, Mediso, Molecubes).
