"""validate-input intake decision (read-only; built on preflight findings)."""

from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from test_pilot_bundle import trial
from voxeltrace.validate_input import classify_scan, tracer_class, validate_input


def _f(code, sev):
    return NS(reason_code=code, severity=sev, field="f", remediation="r")


def _scan(findings=(), tracer="Fluorodeoxyglucose"):
    return NS(
        subject="S",
        scan="baseline",
        state="X",
        findings=[],
        series=[NS(findings=list(findings), facts={"tracer": tracer})],
    )


@pytest.mark.parametrize(
    ("findings", "tracer", "decision"),
    [
        ((), "Fluorodeoxyglucose", "ACCEPT_FOR_AUDIT"),
        ((_f("NO_VENDOR_PRIVATE_PARSER", "INFO"),), "FDG", "ACCEPT_FOR_AUDIT"),
        ((_f("MISSING_PATIENTSIZE", "WARNING"),), None, "ACCEPT_WITH_WARNINGS"),
        ((_f("MISSING_RADIONUCLIDETOTALDOSE", "BLOCKING"),), "FDG", "NEEDS_REEXPORT"),
        ((_f("MULTIPLE_PET_SERIES", "NEEDS_REVIEW"),), "FDG", "NEEDS_REEXPORT"),
        ((_f("UNSUPPORTED_UNITS", "BLOCKING"),), "FDG", "UNSUPPORTED"),
        ((), "PSMA-11", "UNSUPPORTED"),
        ((), "Fluorothymidine", "NEEDS_REEXPORT"),
    ],
)
def test_decision_mapping(findings, tracer, decision):
    assert classify_scan(_scan(findings, tracer))["decision"] == decision


def test_tracer_class_matches_census():
    assert tracer_class("Fluorodeoxyglucose") == "FDG" and tracer_class("18F-DCFPyL") == "PSMA"
    assert tracer_class("Florbetapir") == "AMYLOID" and tracer_class(None) == "UNKNOWN"


def test_trial_folder_end_to_end(tmp_path, capsys):
    from voxeltrace.cli import main

    root, _ = trial(tmp_path)
    r = validate_input(root)
    assert r["decision"] in ("ACCEPT_FOR_AUDIT", "ACCEPT_WITH_WARNINGS", "NEEDS_REEXPORT")
    assert sum(r["counts"].values()) >= len(r["scans"]) and r["scans"]
    rc = main(["validate-input", str(root)])
    assert (
        rc == {"ACCEPT_FOR_AUDIT": 0, "ACCEPT_WITH_WARNINGS": 0, "NEEDS_REEXPORT": 2}[r["decision"]]
    )
    assert r["decision"] in capsys.readouterr().out


def test_empty_folder_needs_reexport(tmp_path):
    (tmp_path / "empty").mkdir()
    assert validate_input(tmp_path / "empty")["decision"] == "NEEDS_REEXPORT"
