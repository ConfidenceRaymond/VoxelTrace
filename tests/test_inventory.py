"""data-inventory is read-only and reports sizes, series, licences and symlinks."""

from __future__ import annotations

import json

from voxeltrace.inventory import format_text, inventory


def _tree(tmp_path):
    root = tmp_path / "ws"
    pet = root / "data" / "coll" / "SUBJ-1" / "baseline" / "PET"
    pet.mkdir(parents=True)
    (pet / "a.dcm").write_bytes(b"x" * 100)
    (root / "data" / "coll" / "provenance_manifest.json").write_text("{}")
    (root / "outputs" / "ns").mkdir(parents=True)
    (root / "outputs" / "ns" / "link.dcm").symlink_to(pet / "a.dcm")
    (root / "tmp").mkdir()
    (root / "tmp" / "big.bin").write_bytes(b"y" * 50)
    repo = root / "repo"
    (repo / "configs").mkdir(parents=True)
    (repo / "configs" / "allowlist.json").write_text(json.dumps(
        {"series": [{"PatientID": "SUBJ-1", "timepoint": "baseline", "modality": "PET", "license": "CC BY 4.0"},
                    {"PatientID": "SUBJ-1", "timepoint": "baseline", "modality": "CT", "license": "OTHER"}]}))  # fmt: skip
    return root, repo


def test_inventory_counts_without_following_or_deleting(tmp_path):
    root, repo = _tree(tmp_path)
    before = sorted(str(p) for p in root.rglob("*"))
    r = inventory(root, repo)
    assert sorted(str(p) for p in root.rglob("*")) == before  # nothing created, moved or deleted
    assert r["top_level"]["outputs"] == {
        "bytes": 0,
        "files": 0,
        "symlinks": 1,
    }  # link counted, not followed
    (s,) = r["imaging_series"]
    assert (s["subject"], s["timepoint"], s["modality"], s["files"], s["bytes"]) == (
        "SUBJ-1",
        "baseline",
        "PET",
        1,
        100,
    )
    assert s["allowlist_licence"] == [
        "CC BY 4.0"
    ]  # keyed by subject/timepoint/modality, not subject only
    assert s["provenance_manifest"] is True
    assert any("tmp/" in a for a in r["needs_attention"])
    assert "Nothing was deleted" in format_text(r)


def test_cli_refuses_out_outside_workspace_and_overwrite(tmp_path):
    from voxeltrace.cli import main

    assert main(["data-inventory", "--root", str(tmp_path), "--out", "/etc/vt_inventory.txt"]) == 2
