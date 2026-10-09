# Adjudication protocol

Adjudication resolves disagreement **between human reviewers**. It never changes a
VoxelTrace verdict, and a VoxelTrace verdict never settles a disagreement between reviewers.

## Rounds

1. **Independent round (blinded).** At least two reviewers answer every case on their own.
   The coordinator receives the forms, locks a copy (sha256 of every file) and does not share
   answers between reviewers.
2. **Reviewer consensus.** For each case and standard where reviewers disagree, the
   coordinator sends each reviewer the other answers and reasons, anonymised and without any
   software output. Reviewers may keep or revise their answer. A revision is a new form; the
   original form is kept.
3. **Adjudicator.** Any disagreement left after round 2 goes to one senior reviewer who did
   not take part in round 1. The adjudicator records:
   - the final reference answer per standard;
   - a reason;
   - whether the case is *inherently ambiguous*, meaning the evidence supports more than one
     answer.

   Inherently ambiguous cases stay in the analysis and are reported as a separate stratum.
4. **Optional unblinded round.** Only after the reference answers are locked do reviewers see
   VoxelTrace's verdicts. They then record `rules_disagreed` and `disagreement_reason`. This
   round explains disagreements; it never changes the locked reference answers.

## Records

- Every form, revision and adjudication is kept with its timestamp and sha256.
- Nothing is deleted. Corrections are new records that refer to the record they replace.
- The coordinator keeps `COORDINATOR_ONLY_answer_key.json` (VoxelTrace verdicts) separate from
  the reviewer material until the reference answers are locked.
- Disagreements that point to a possible VoxelTrace error are logged as issues, with the case
  ID and standard, before any software change. A software change after locking is reported as
  a protocol deviation, and the scores are reported for the locked software version.
