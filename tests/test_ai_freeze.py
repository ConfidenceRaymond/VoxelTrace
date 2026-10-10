"""AI architecture freeze: the deterministic audit path never imports model code."""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "voxeltrace"
AUDIT_PATH = ["quant", "rules", "trial", "evidence", "preflight", "census", "ingest", "vendors",
              "pilot.py", "bundle.py", "cli.py", "expert_validation.py", "versions.py",
              # pilot workflow (0.4.0): intake, acceptance, delivery, trace, reports
              "pilot_run.py", "delivery.py", "intake.py", "trace.py", "remediation.py",
              "privacy_scan.py", "validate_input.py", "executive.py", "pdf.py",
              "partner_intake.py"]  # fmt: skip
FORBIDDEN = re.compile(
    r"^\s*(from|import)\s+(voxeltrace\.(ai|training|evaluation)|torch|transformers|httpx)\b", re.M
)


def test_audit_path_imports_no_model_code():
    files = _audit_files()
    bad = [str(f.relative_to(SRC)) for f in files if FORBIDDEN.search(f.read_text())]
    assert bad == [], bad


MODEL_HINT = re.compile(
    r"qwen|vlm-venv|AutoModel|AutoProcessor|from_pretrained|chat/completions", re.I
)


def _audit_files():
    files = []
    for item in AUDIT_PATH:
        p = SRC / item
        files += [p] if p.is_file() else sorted(p.rglob("*.py"))
    return files


def test_audit_path_never_loads_or_calls_a_model():
    """No model loading, model path or chat endpoint anywhere in the deterministic path."""
    bad = [str(f.relative_to(SRC)) for f in _audit_files() if MODEL_HINT.search(f.read_text())]
    assert bad == [], bad


def test_review_records_must_come_from_humans():
    import pytest

    from voxeltrace.trial.lesion_review import LesionReview

    with pytest.raises(ValueError):
        LesionReview.model_validate({"created_via": "AI_MODEL"})


def test_local_ai_client_is_local_only_and_cannot_decide():
    import pytest

    from voxeltrace.ai.client import SYSTEM_PROMPT, LocalAIClient

    with pytest.raises(ValueError, match="non-local"):
        LocalAIClient("https://api.example.com/v1", allow_remote=False)
    c = LocalAIClient("http://127.0.0.1:9/v1")
    with pytest.raises(NotImplementedError):
        c.reason_structured({"verdict": "ASSESSABLE"}, "is this pair comparable?")
    req = c.build_reasoning_request({"suv_max": 4.2}, "explain")
    assert (
        req["temperature"] == 0.0 and "computed deterministically" in req["messages"][1]["content"]
    )
    assert "Never invent, estimate or alter quantitative measurements" in SYSTEM_PROMPT
    c.close()


def test_every_bundle_declares_no_ai_component(tmp_path):
    import json

    import yaml
    from pydicom.uid import generate_uid

    from dicom_factory import write_image_series
    from voxeltrace.pilot import run_audit

    root = tmp_path / "t"
    for i, tp in enumerate(("baseline", "followup")):
        write_image_series(
            root / "S" / tp, modality="PT", study_uid=generate_uid(), slope=1.5 + i / 10
        )
    (root / "trial.yaml").write_text(yaml.safe_dump({"trial_id": "T", "ruleset": "qiba-fdg-1.14",
                                                     "timepoint_order": ["baseline", "followup"],
                                                     "reference_proposals": "off"}))  # fmt: skip
    run_audit(root, tmp_path / "o", rulesets=("qiba-fdg-1.14",))
    m = json.loads((tmp_path / "o" / "audit_bundle" / "manifest.json").read_text())
    assert m["ai_components"].startswith("none")


def test_adjudication_rejects_automated_origin():
    import pytest

    from voxeltrace.trial.adjudication import Adjudication

    with pytest.raises(ValueError):
        Adjudication.model_validate({"created_via": "AI_MODEL"})
