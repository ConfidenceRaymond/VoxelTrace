"""Write protocol / reconstruction / correction / QC / claim evidence for one quantified case."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from voxeltrace.evidence.claims import (
    RULES_VERSION,
    ClaimEvidence,
    claim_quantity,
    default_case_claims,
)
from voxeltrace.evidence.protocol import (
    ProtocolEvidence,
    ProtocolQC,
    assess_protocol_qc,
    extract_protocol,
)
from voxeltrace.quant.evidence import QuantRun


def protocol_for_run(run: QuantRun) -> tuple[ProtocolEvidence, ProtocolQC]:
    """Protocol evidence sharing the run's validated SUV timing (no re-derivation)."""
    assert run.outcome is not None and run.pet_series_uid is not None
    src = run.outcome.result or run.outcome.refusal
    assert src is not None
    series = run.case.get_series(run.pet_series_uid)
    p = extract_protocol(series, src.inputs, src.validation)
    return p, assess_protocol_qc(p, src.validation.eligible)


def gate_demonstrations(run: QuantRun) -> list[ClaimEvidence]:
    """Deliberately wrong claims, showing the gate rejects them."""
    ev = run.evidence
    les = [x for x in ev.measured.lesions if x.voxel_count > 0]
    if not les or les[0].suv_max is None:
        return []
    wrong = f"{les[0].suv_max * 1.25:.2f}"
    c = claim_quantity(
        ev, "suv_max", wrong, segment=les[0].segment_number, claim_id="demo-wrong-suvmax"
    )
    return [c]


def write_protocol_outputs(run: QuantRun, out_dir: str | Path) -> tuple[list[Path], dict[str, Any]]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    p, qc = protocol_for_run(run)
    claims = default_case_claims(run.evidence, p)
    demos = gate_demonstrations(run)
    files = {
        "scanner_evidence.json": p.scanner.model_dump(mode="json"),
        "acquisition_protocol.json": p.acquisition.model_dump(mode="json"),
        "reconstruction_protocol.json": p.reconstruction.model_dump(mode="json"),
        "correction_evidence.json": p.corrections.model_dump(mode="json"),
        "protocol_qc.json": qc.model_dump(mode="json"),
        "claim_evidence.json": {
            "rules_version": RULES_VERSION,
            "source": "deterministic rules (no LLM)",
            "subject_pseudonym": run.evidence.provenance.subject_pseudonym,
            "pet_series_uid": run.pet_series_uid,
            "claims": [c.model_dump(mode="json") for c in claims],
            "gate_demonstrations": [c.model_dump(mode="json") for c in demos],
        },
    }
    written = []
    for name, payload in files.items():
        path = out / name
        path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
        written.append(path)
    return written, {"protocol": p, "qc": qc, "claims": claims, "demos": demos}
