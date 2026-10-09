# Pilot validation checklist

Tick each item before a result is reported to a sponsor.

**Installation and integrity**
- [ ] `voxeltrace --help` works in a fresh environment; record the version and git commit.
- [ ] `pytest` passes on the installed commit (synthetic tests; CI green).
- [ ] Input folder is read-only; subject folders are pseudonyms.
- [ ] Preflight run; every DO_NOT_QUANTIFY scan has a documented decision (re-export
  requested / excluded).

**Audit**
- [ ] Audit bundle written to a new directory; `verify-bundle` OK.
- [ ] Manifest records git commit, `git_dirty: false`, schema versions and rule-bundle
  sha256.
- [ ] REAL and SYNTHETIC sections reviewed separately; no synthetic fixtures in the
  delivered trial folder.

**Evidence**
- [ ] Every PERCIST-relevant reference region reviewed by a qualified human (no
  PROPOSED_REQUIRES_REVIEW left, or reported as pending).
- [ ] Any QIBA PASS_WITH_WARNING pair lists the attestation ID, role and source hash, and the
  attestation was validated.
- [ ] Adjudications (if any) listed with reviewer, role and evidence hashes; automated
  verdicts unchanged.

**Reporting**
- [ ] INSUFFICIENT_INFORMATION reasons summarised (II reason distribution) with draft site
  queries.
- [ ] Drift events reviewed; heuristic uptake/dose outliers labelled as heuristic.
- [ ] Known limitations ([known_limitations.md](known_limitations.md)) attached to the
  delivery.
- [ ] External physicist spot-check (BLINDED package) planned or done; false-safe cases
  investigated.
