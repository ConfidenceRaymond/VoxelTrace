"""Pair-level HUMAN adjudication (VT-ADJUDICATION-1). Immutable, append-only, report-only.

An adjudication records a named human's decision about ONE automated pair verdict. It never
modifies the automated result: the automated verdict stays the audit's verdict and the
adjudication is shown next to it. Rules:

  * actions: CONFIRM_AUTOMATED_RESULT, OVERRIDE_WITH_EVIDENCE, REQUEST_SITE_INFORMATION,
    UNRESOLVED;
  * created_via must be a human channel (HUMAN_CLI / HUMAN_UI); records claiming an AI or
    automated origin are rejected; software never writes an adjudication on its own;
  * OVERRIDE_WITH_EVIDENCE needs a reason, the new verdict and >= 1 hash-bound evidence item;
  * binding: the record names the sha256 of the automated pair result it adjudicates; if the
    result changes, the record is STALE and not applied;
  * storage: JSON lines, each record chained to the previous record's hash; any edit,
    deletion or reordering breaks the chain (TAMPERED).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ADJUDICATION_SCHEMA = "VT-ADJUDICATION-1"
Action = Literal[
    "CONFIRM_AUTOMATED_RESULT", "OVERRIDE_WITH_EVIDENCE", "REQUEST_SITE_INFORMATION", "UNRESOLVED"
]
ReviewerRole = Literal[
    "PET_PHYSICIST", "NUCLEAR_MEDICINE_PHYSICIAN", "RADIOLOGIST", "IMAGING_CORE_LEAD",
    "TRIAL_QC_REVIEWER",
]  # fmt: skip
Verdict = Literal[
    "ASSESSABLE", "ASSESSABLE_WITH_WARNINGS", "NOT_ASSESSABLE", "INSUFFICIENT_INFORMATION"
]
GENESIS = "0" * 64


class EvidenceItem(BaseModel):
    description: str = Field(min_length=1)
    attachment_sha256: str

    @field_validator("attachment_sha256")
    @classmethod
    def _sha(cls, v: str) -> str:
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v):
            raise ValueError("attachment_sha256 must be 64 lowercase hex characters")
        return v


class Adjudication(BaseModel):
    schema_version: Literal["VT-ADJUDICATION-1"] = ADJUDICATION_SCHEMA
    adjudication_id: str = Field(min_length=1)
    subject: str
    baseline: str
    followup: str
    ruleset_id: str
    automated_verdict: Verdict
    automated_result_sha256: str = Field(min_length=64, max_length=64)
    affected_rules: list[str] = Field(default_factory=list)
    action: Action
    adjudicated_verdict: Verdict | None = None
    reason: str = Field(min_length=1)
    supplied_evidence: list[EvidenceItem] = Field(default_factory=list)
    reviewer_id: str = Field(min_length=1)
    reviewer_role: ReviewerRole
    timestamp: datetime
    software_version: str
    git_commit: str | None = None
    created_via: Literal["HUMAN_CLI", "HUMAN_UI"]
    simulated: bool = False

    def model_post_init(self, _ctx: Any) -> None:
        if self.action == "OVERRIDE_WITH_EVIDENCE":
            if self.adjudicated_verdict is None or not self.supplied_evidence:
                raise ValueError("OVERRIDE_WITH_EVIDENCE needs adjudicated_verdict and evidence")
        elif self.adjudicated_verdict is not None:
            raise ValueError("adjudicated_verdict is only allowed with OVERRIDE_WITH_EVIDENCE")


def result_sha256(pair_result: Any) -> str:
    """Hash of an automated PairAssessabilityResult (canonical JSON)."""
    data = (
        pair_result.model_dump(mode="json") if hasattr(pair_result, "model_dump") else pair_result
    )
    canon = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canon.encode()).hexdigest()


def _line_hash(prev: str, record_json: str) -> str:
    return hashlib.sha256((prev + record_json).encode()).hexdigest()


def append_adjudication(path: str | Path, record: Adjudication, *, confirmed: bool) -> str:
    """Append ONE human adjudication. ``confirmed`` must be True (explicit human action).
    Never rewrites existing lines. Returns the new chain hash."""
    if not confirmed:
        raise PermissionError("adjudication requires explicit human confirmation")
    path = Path(path)
    chain = verify_chain(path)
    if chain["status"] != "OK":
        raise ValueError(f"adjudication log is {chain['status']}; refusing to append")
    rec_json = record.model_dump_json()
    h = _line_hash(chain["head"], rec_json)
    with path.open("a") as fh:
        fh.write(
            json.dumps({"record": json.loads(rec_json), "prev": chain["head"], "hash": h}) + "\n"
        )
    return h


def verify_chain(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {"status": "OK", "head": GENESIS, "records": 0}
    prev = GENESIS
    n = 0
    for i, line in enumerate(path.read_text().splitlines()):
        try:
            obj = json.loads(line)
            rec_json = Adjudication.model_validate(obj["record"]).model_dump_json()
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "INVALID",
                "head": prev,
                "records": n,
                "line": i + 1,
                "error": str(exc),
            }
        if obj.get("prev") != prev or obj.get("hash") != _line_hash(prev, rec_json):
            return {"status": "TAMPERED", "head": prev, "records": n, "line": i + 1}
        prev, n = obj["hash"], n + 1
    return {"status": "OK", "head": prev, "records": n}


def load_adjudications(
    path: str | Path, *, allow_simulated: bool = False
) -> tuple[list[Adjudication], dict]:
    chain = verify_chain(path)
    if chain["status"] != "OK" or not Path(path).exists():
        return [], chain
    recs = [
        Adjudication.model_validate(json.loads(x)["record"])
        for x in Path(path).read_text().splitlines()
    ]
    return [r for r in recs if allow_simulated or not r.simulated], chain


def adjudication_status(pairs: list[Any], records: list[Adjudication]) -> list[dict[str, Any]]:
    """Report rows: automated verdict (immutable) and the LATEST valid adjudication, if any."""
    rows = []
    for p in pairs:
        key = (p.pair.subject_id, p.pair.baseline, p.pair.followup, p.ruleset_id)
        mine = [r for r in records if (r.subject, r.baseline, r.followup, r.ruleset_id) == key]
        h = result_sha256(p)
        current = [r for r in mine if r.automated_result_sha256 == h]
        stale = [r for r in mine if r.automated_result_sha256 != h]
        latest = current[-1] if current else None
        rows.append(
            {
                "subject": p.pair.subject_id,
                "pair": f"{p.pair.baseline}->{p.pair.followup}",
                "ruleset": p.ruleset_id,
                "automated_verdict": p.verdict,
                "adjudication_status": {
                    None: "NOT_ADJUDICATED",
                    "CONFIRM_AUTOMATED_RESULT": "CONFIRMED_BY_HUMAN",
                    "OVERRIDE_WITH_EVIDENCE": "OVERRIDDEN_BY_HUMAN",
                    "REQUEST_SITE_INFORMATION": "SITE_INFORMATION_REQUESTED",
                    "UNRESOLVED": "UNRESOLVED",
                }[latest.action if latest else None],
                "human_verdict": latest.adjudicated_verdict if latest else None,
                "reviewer": f"{latest.reviewer_id} ({latest.reviewer_role})" if latest else "",
                "adjudication_id": latest.adjudication_id if latest else "",
                "stale_records": len(stale),
            }
        )
    return rows
