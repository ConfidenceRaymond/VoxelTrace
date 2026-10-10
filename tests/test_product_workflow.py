"""Product workflow without developer tooling: workspace resolution, init-trial, UI pages."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from test_pilot_bundle import trial


def test_workspace_root_env_and_installed_fallback(tmp_path, monkeypatch):
    import voxeltrace.config as cfg

    monkeypatch.setenv("VOXELTRACE_WORKSPACE", str(tmp_path))
    assert cfg.workspace_root() == tmp_path.resolve()
    monkeypatch.delenv("VOXELTRACE_WORKSPACE")
    monkeypatch.setattr(
        cfg, "REPO_ROOT", tmp_path / "site-packages"
    )  # installed layout: no pyproject
    monkeypatch.chdir(tmp_path)
    assert cfg.workspace_root() == tmp_path.resolve()


def test_init_trial_writes_safe_defaults_and_never_overwrites(tmp_path):
    from voxeltrace.cli import main
    from voxeltrace.trial.discovery import discover_trial

    root, _ = trial(tmp_path)
    (root / "trial.yaml").unlink()
    assert main(["init-trial", str(root), "--trial-id", "T-1", "--ruleset", "percist-1.0"]) == 0
    doc = yaml.safe_load((root / "trial.yaml").read_text())
    assert doc["lesion_evidence_policy"] == "REVIEW_REQUIRED" and "sites" not in doc
    layout = discover_trial(root)
    assert layout.config.ruleset == "percist-1.0" and set(layout.timepoint_order) >= set(
        next(iter(layout.scans.values()))
    )
    assert main(["init-trial", str(root), "--trial-id", "T-1"]) == 2  # never overwritten


def test_init_trial_rejects_flat_folder(tmp_path):
    from voxeltrace.trial.init_trial import write_trial_yaml

    (tmp_path / "a.dcm").write_bytes(b"x")
    with pytest.raises(ValueError):
        write_trial_yaml(tmp_path, trial_id="X")


@pytest.mark.parametrize("page", ["app/Home.py", "app/pages/0_Intake_and_Audit.py"])
def test_product_pages_render(page, tmp_path, monkeypatch):
    # the review UI is the optional [app] extra; CI installs [dev] only
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

    monkeypatch.setenv("VOXELTRACE_WORKSPACE", str(tmp_path))
    at = AppTest.from_file(str(Path(__file__).parents[1] / page), default_timeout=60).run()
    assert not at.exception
    text = " ".join(e.value for e in at.markdown) + " ".join(e.value for e in at.subheader)
    if page == "app/Home.py":
        assert "Quantitative trust for PET imaging" in text and "Local AI" not in text
