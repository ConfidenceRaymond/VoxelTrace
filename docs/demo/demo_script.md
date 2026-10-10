# Demo script (spoken, about 6 minutes)

Commands and timings: [demo_runbook.md](demo_runbook.md). Demonstration data only.

**0:00 Opening.** "VoxelTrace answers one question before anyone reads an SUV change: are
these two PET scans comparable? Different scanners, software, reconstructions or uptake times
can make the change meaningless. This is research and trial-QC software, not a medical device,
and nothing you'll see uses AI to decide anything."

**0:30 Intake.** "Here is a study folder: subjects and visits. The first step checks each scan
as exported. Where something is missing, it says what, in plain language, with the DICOM field
and what would fix it."

**1:15 Preflight and fingerprint.** "Each scan is classified ready or not ready to quantify, and
its protocol is fingerprinted: scanner, software, reconstruction, corrections. That fingerprint
is what we compare across visits and sites."

**2:15 Pair results.** "Here are the pairs. These are demonstration pairs, each with one
deliberate change. Identical scans: assessable. A changed reconstruction: not assessable. The
injected dose removed: insufficient information. Missing evidence is never treated as a pass."

**3:00 Reasons.** "Every reason is catalogued: what it means, and whether a re-export, the
site's records or a reviewer can resolve it. If nothing deterministic can, it says so."

**3:30 Why.** "If you ask why this pair is not comparable, this is the trace: the rule, the
field, the value at both visits, how far we trust that value, and where it came from."

**4:15 Sites.** "Rolled up by site and scanner, so a core lab sees which sites need a query."

**4:45 Report.** "The one page a director reads. It states the validation status on the page."

**5:30 Verification.** "Everything you receive is checksummed and scanned for identifiers before
it leaves. You can verify it yourself, with or without VoxelTrace."

**6:00 Close.** "Where we are: tested on public data; Siemens validated on real pairs; GE and
Philips limited; independent expert validation pending. Would a retrospective audit of one of
your completed studies be useful to you?"
