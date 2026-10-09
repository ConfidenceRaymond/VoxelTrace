# Intended use: conservative draft (research / trial QC)

**This is not legal or regulatory advice.** Whether VoxelTrace is a medical device in any
jurisdiction depends on its intended use, labelling and marketing claims, and must be
confirmed by qualified regulatory counsel before any commercial offer. VoxelTrace has no
clearance, approval, CE marking or licence anywhere.

## Draft intended-use statement

> VoxelTrace is research and clinical-trial quality-control software. It assesses whether
> quantitative FDG PET/CT image data from different timepoints, sites, scanners and
> reconstruction protocols meet the data-comparability prerequisites of user-selected
> published guidelines (QIBA FDG-PET/CT Profile, EANM FDG PET/CT guideline, PERCIST). It
> reports the result, with the evidence and reasons, to trial imaging professionals for
> data-quality and protocol-compliance purposes.
>
> VoxelTrace is not intended for diagnosis, prognosis, monitoring, treatment selection or any
> other patient-management decision. It does not classify treatment response, does not
> produce findings about individual patients' disease, and is not intended for use in
> clinical care. Its outputs are not to be used to determine an individual subject's
> eligibility, dosing or treatment.

**Intended users:** imaging core labs, PET physicists, trial imaging scientists and sponsors'
imaging functions. Not patients, and not clinicians in the context of care.

## Why the boundary matters

- **US (FDA).** Whether software is a device depends on intended use: diagnosis, cure,
  mitigation, treatment or prevention of disease.
  - The statutory exclusion for clinical decision support (FD&C Act section 520(o)(1)(E))
    does **not** cover software intended to acquire, process or analyse a medical image.
    VoxelTrace processes PET images (it computes SUV), so it **cannot rely on the CDS
    exclusion**. Its non-device position, if any, must rest on not having a medical purpose
    (trial data QC, research).
  - The CDS guidance was revised in January 2026 (FDA document dated 29 January 2026,
    superseding the 6 January 2026 version, which superseded the September 2022 guidance).
  - Software functions intended *solely* to transfer, store, convert formats or display
    medical images are excluded under 520(o)(1)(D) (MDDS / image storage and communication
    guidance). VoxelTrace analyses images, so this exclusion does not describe it either.
- **EU (MDR 2017/745).** Qualification depends on the manufacturer's intended purpose (MDCG
  2019-11, Rev.1 June 2025, non-binding). Software that gives information used to take
  diagnostic or therapeutic decisions falls under Rule 11 (class IIa or higher). Software for
  research or data QC without a medical purpose for individual patients is generally argued
  not to qualify, but counsel must confirm.
- **Canada (Health Canada).** The *Software as a Medical Device (SaMD): Definition and
  Classification* guidance (December 2019) also bases qualification on functionality and how
  the software is represented or labelled, using IMDRF concepts.

## When VoxelTrace could enter medical-device territory

Each of the following would move it toward device status:

1. Marketing or labelling for **clinical care**, for example QC of PET used in a patient's
   report, or "ensures accurate SUV for treatment decisions".
2. Outputs used to make **individual patient decisions**, for example PERCIST response
   categories, eligibility or measurability decisions that change a patient's treatment or
   trial enrolment, or alerts to treating clinicians.
3. Providing **quantitative values for clinical interpretation** (SUV, SUL, MTV/TLG reported
   for reading), rather than as evidence behind a comparability verdict.
4. **Modifying images** (harmonization) or producing derived images for reading.
5. **Autonomous AI interpretation** of images or findings.
6. Integration into **clinical systems** (PACS/RIS reporting) as a clinical function.

Current product rules that keep it on the research/QC side:
- no response classification;
- no clinical claims;
- reports state "not for clinical diagnosis";
- PERCIST is used for prerequisites only;
- no image modification;
- no model in the audit.

## Clinical-trial context (to assess, not concluded)

Software used to process trial data may be subject to sponsor computerized-system
expectations, such as electronic records and audit-trail requirements and GCP data-integrity
expectations, independently of device status. See `quality_system_roadmap.md`. No compliance
is claimed.

## Sources (accessed 2026-10-09; primary documents to be re-read by counsel)

- FDA, *Clinical Decision Support Software*, guidance revised January 2026 (fda.gov guidance
  page); prior final guidance 28 September 2022.
- FDA, *Medical Device Data Systems, Medical Image Storage Devices, and Medical Image
  Communications Devices* guidance (section 520(o)(1)(D)).
- FDA, *Policy for Device Software Functions and Mobile Medical Applications* guidance.
- Regulation (EU) 2017/745, Annex VIII Rule 11; MDCG 2019-11 Rev.1 (June 2025),
  *Qualification and classification of software*.
- Health Canada, *Guidance Document: Software as a Medical Device (SaMD): Definition and
  Classification* (2019):
  https://www.canada.ca/en/health-canada/services/drugs-health-products/medical-devices/application-information/guidance-documents/software-medical-device-guidance-document.html
- Earlier in-repository regulatory references are limited to scanner 510(k) records and
  decay-correction recall notices (`../vendor_decay_timing.md`). This document is the first
  regulatory-positioning note.
