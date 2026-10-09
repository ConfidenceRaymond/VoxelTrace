"""AI architecture freeze: the deterministic audit path never imports model code."""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "voxeltrace"
AUDIT_PATH = ["quant", "rules", "trial", "evidence", "preflight", "census", "ingest", "vendors",
              "pilot.py", "bundle.py", "cli.py", "expert_validation.py", "versions.py"]  # fmt: skip
FORBIDDEN = re.compile(
    r"^\s*(from|import)\s+(voxeltrace\.(ai|training|evaluation)|torch|transformers|httpx)\b", re.M
)


def test_audit_path_imports_no_model_code():
    files = []
    for item in AUDIT_PATH:
        p = SRC / item
        files += [p] if p.is_file() else sorted(p.rglob("*.py"))
    bad = [str(f.relative_to(SRC)) for f in files if FORBIDDEN.search(f.read_text())]
    assert bad == [], bad


def test_adjudication_rejects_automated_origin():
    import pytest

    from voxeltrace.trial.adjudication import Adjudication

    with pytest.raises(ValueError):
        Adjudication.model_validate({"created_via": "AI_MODEL"})
