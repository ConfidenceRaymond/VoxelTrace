# IP and moat assessment

This is a business assessment, not legal advice. **No patentability, freedom-to-operate or
validity conclusion is made.** A patent attorney must assess any filing before further public
disclosure. Note that the repository is already public (MIT), so much of the core is
disclosed.

| Asset | What it is today | Category | Notes |
|---|---|---|---|
| Cross-vendor parser knowledge | strict SUV validator, DICOM timing/decay handling, refusal taxonomy; vendor decay-timing research (`../vendor_decay_timing.md`) | **open-source-friendly** (already public) | value lies in correctness and trust, not secrecy; openness invites physicist scrutiny |
| Scanner / software knowledge base | VT-VENDOR-KB-1, vendor validation matrix | **potentially protectable as a curated database / trade secret** for future, non-public entries | the public entries are disclosed; future partner-derived entries (per model and software version behaviours) can be kept confidential under agreement |
| II corpus | catalogue of *why* real data cannot be decided, with reason codes, from censuses (thousands of public series) and audits | **trade secret** (aggregate, from partners) | grows with every audit; most defensible if built from partner data under rights to aggregate statistics; no such rights exist yet |
| Rules library | QIBA/EANM/PERCIST rule encodings with source citations | **probably not defensible** | the standards are public; anyone can encode them; the defensible part is the *tested* encoding and its validation record |
| Trial-specific rule packs | charter-specific overrides per sponsor or core lab | **trade secret / customer confidential** | usually customer-owned or jointly owned; contract terms decide |
| Validation corpus | blinded cohort, answer keys, locked tags, future expert adjudications | **potentially protectable** (data and know-how); the results become a credibility asset once published | expert agreement data would be the hardest asset for a competitor to copy, but it does not exist yet |
| Protocol fingerprint history | VT-PROTOCOL-FP-1 fingerprints and drift over time per site | **trade secret** (aggregate, partner data) | valuable longitudinally; needs data rights |
| Scanner qualification registry | not built; would record which model/software/reconstruction combinations were verified, and how | **potentially protectable** future database | depends on partner phantoms and exports |
| External dataset learnings | census v3, OpenNeuro census, collection-specific quirks | **open-source-friendly / probably not defensible** | public data; can be reproduced |
| Software implementation | Python package, CLI, app | copyright (MIT licence) | open, so no exclusivity; commercial value lies in workflow, support and validation package |

## Where a moat could come from (none established yet)

1. **Validation evidence:** a published, blinded expert agreement study across vendors.
2. **Data network:** an II corpus, fingerprint history and qualification registry built from
   partner audits under agreed aggregate rights.
3. **Workflow embedding:** core-lab integration plus a validated deliverable process (QMS,
   change control), which makes switching costly.
4. **Trust and neutrality:** vendor-neutral, deterministic and open rules. This is hard for a
   scanner vendor to match.

**Probably not a moat:** the rule encodings themselves, generic DICOM parsing, and the
optional language-model explanation.
