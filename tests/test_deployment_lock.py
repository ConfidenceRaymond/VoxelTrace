"""Pilot deployment lock VT-DEPLOYMENT-LOCK-1."""

from __future__ import annotations

import copy
import json

import pytest

from voxeltrace.cli import main as cli
from voxeltrace.deployment_lock import RESULT_PACKAGES, capture, main_capture, verify


def test_capture_records_versions_rules_schemas_packages():
    lock = capture()
    assert lock["schema"] == "VT-DEPLOYMENT-LOCK-1"
    assert lock["voxeltrace"]["version"] and lock["rule_bundle_sha256"] and lock["schemas"]
    assert "numpy" in lock["packages"] and "pydicom" in lock["packages"]
    assert verify(lock)["status"] in ("LOCK_MATCH", "LOCK_MATCH_WITH_WARNINGS", "LOCK_MISMATCH")


@pytest.mark.parametrize(
    "mutate,item",
    [
        (lambda lk: lk["packages"].__setitem__("numpy", "0.0.1"), "package numpy"),
        (lambda lk: lk.__setitem__("rule_bundle_sha256", "0" * 64), "rule bundle sha256"),
        (lambda lk: lk["schemas"].__setitem__("bundle", "VT-BUNDLE-0"), "schema bundle"),
        (lambda lk: lk["python"].__setitem__("version", "3.9.0"), "python major.minor"),
        (lambda lk: lk["voxeltrace"].__setitem__("git_commit", "deadbeef"), "git commit"),
    ],
)
def test_result_relevant_mismatches_block(mutate, item):
    lock = copy.deepcopy(capture())
    mutate(lock)
    r = verify(lock)
    assert r["status"] == "LOCK_MISMATCH"
    assert any(i["item"] == item and i["severity"] == "BLOCKING" for i in r["issues"])


def test_other_package_drift_is_a_warning_only():
    lock = copy.deepcopy(capture())
    other = next(n for n in lock["packages"] if n not in RESULT_PACKAGES)
    lock["packages"][other] = "0.0.0-locked"
    r = verify(lock)
    assert any(i["item"] == f"package {other}" and i["severity"] == "WARNING" for i in r["issues"])


def test_capture_never_overwrites_and_cli(tmp_path, capsys):
    p = tmp_path / "lock.json"
    main_capture(p)
    with pytest.raises(FileExistsError):
        main_capture(p)
    assert cli(["deployment-lock", "verify", str(p)]) in (0, 1)
    json.loads(capsys.readouterr().out)
