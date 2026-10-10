"""Pilot deployment lock (VT-DEPLOYMENT-LOCK-1): capture the exact environment a pilot runs in,
and verify later that the same environment is used.

  capture(model_manifest=None) -> lock dict
  verify(lock) -> report (status LOCK_MATCH / LOCK_MATCH_WITH_WARNINGS / LOCK_MISMATCH)

What is BLOCKING on verify: Python major.minor, VoxelTrace version, git commit or a dirty tree,
rule bundle sha256, any schema version, and the version of any runtime dependency that can
touch a result (numpy, pydicom, pydantic, pydantic-settings, SimpleITK, nibabel, Pillow,
PyYAML). Other installed packages and the platform string are WARNING. The optional local model
is recorded for provenance only; no audit result depends on it.
"""

from __future__ import annotations

import json
import platform
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

LOCK_SCHEMA = "VT-DEPLOYMENT-LOCK-1"
RESULT_PACKAGES = (
    "numpy",
    "pydicom",
    "pydantic",
    "pydantic-settings",
    "simpleitk",
    "nibabel",
    "pillow",
    "pyyaml",
)


def _packages() -> dict[str, str]:
    out = {}
    for d in metadata.distributions():
        name = (d.metadata.get("Name") or "").lower()
        if name and name != "voxeltrace":
            out[name] = d.version
    return dict(sorted(out.items()))


def capture(model_manifest: str | Path | None = None) -> dict[str, Any]:
    import voxeltrace
    from voxeltrace.quant.suv import git_state
    from voxeltrace.versions import SCHEMAS, rule_bundle

    sha, dirty = git_state()
    rb = rule_bundle()
    lock: dict[str, Any] = {
        "schema": LOCK_SCHEMA,
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "release": platform.release(),
        },
        "voxeltrace": {"version": voxeltrace.__version__, "git_commit": sha, "git_dirty": dirty},
        "rule_bundle_sha256": rb["rule_bundle_sha256"],
        "rule_versions": {k: v["version"] for k, v in sorted(rb["rulesets"].items())},
        "schemas": dict(sorted(SCHEMAS.items())),
        "packages": _packages(),
        "model": None,
    }
    if model_manifest:
        m = json.loads(Path(model_manifest).read_text())
        lock["model"] = {
            k: m.get(k) for k in ("repo", "repo_id", "model_id", "revision", "license") if m.get(k)
        } or {"manifest": Path(model_manifest).name}
        lock["model"]["role"] = "optional explanation only; never used by the audit"
    return lock


def verify(lock: dict[str, Any]) -> dict[str, Any]:
    cur = capture()
    issues: list[dict[str, str]] = []

    def chk(what: str, want: Any, got: Any, sev: str) -> None:
        if want != got:
            issues.append({"item": what, "locked": str(want), "current": str(got), "severity": sev})

    if lock.get("schema") != LOCK_SCHEMA:
        issues.append(
            {
                "item": "schema",
                "locked": str(lock.get("schema")),
                "current": LOCK_SCHEMA,
                "severity": "BLOCKING",
            }
        )
    mm = lambda v: ".".join(str(v).split(".")[:2])  # noqa: E731
    chk(
        "python major.minor",
        mm(lock["python"]["version"]),
        mm(cur["python"]["version"]),
        "BLOCKING",
    )
    chk("python patch", lock["python"]["version"], cur["python"]["version"], "WARNING")
    chk("platform", lock["platform"], cur["platform"], "WARNING")
    chk(
        "voxeltrace version",
        lock["voxeltrace"]["version"],
        cur["voxeltrace"]["version"],
        "BLOCKING",
    )
    chk("git commit", lock["voxeltrace"]["git_commit"], cur["voxeltrace"]["git_commit"], "BLOCKING")
    if cur["voxeltrace"]["git_dirty"]:
        issues.append(
            {
                "item": "git tree",
                "locked": "clean",
                "current": "dirty (uncommitted changes)",
                "severity": "BLOCKING",
            }
        )
    chk("rule bundle sha256", lock["rule_bundle_sha256"], cur["rule_bundle_sha256"], "BLOCKING")
    for k in sorted(set(lock["schemas"]) | set(cur["schemas"])):
        chk(f"schema {k}", lock["schemas"].get(k), cur["schemas"].get(k), "BLOCKING")
    for name in sorted(set(lock["packages"]) | set(cur["packages"])):
        sev = "BLOCKING" if name in RESULT_PACKAGES else "WARNING"
        chk(f"package {name}", lock["packages"].get(name), cur["packages"].get(name), sev)
    sevs = {i["severity"] for i in issues}
    status = (
        "LOCK_MISMATCH"
        if "BLOCKING" in sevs
        else "LOCK_MATCH_WITH_WARNINGS"
        if sevs
        else "LOCK_MATCH"
    )
    return {"schema": LOCK_SCHEMA + "-VERIFY", "status": status, "issues": issues,
            "blocking": sum(i["severity"] == "BLOCKING" for i in issues)}  # fmt: skip


def main_capture(out: str | Path, model_manifest: str | Path | None = None) -> dict[str, Any]:
    lock = capture(model_manifest)
    p = Path(out)
    if p.exists():
        raise FileExistsError(f"{p} exists (a lock is never overwritten)")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(lock, indent=2) + "\n")
    return lock


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(capture(), indent=2))
    sys.exit(0)
