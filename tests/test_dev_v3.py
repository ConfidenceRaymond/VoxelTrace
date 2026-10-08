from types import SimpleNamespace

import pytest

from voxeltrace.evaluation import dev_v3
from voxeltrace.evaluation.dev_v3 import (
    NATURAL_NEGATION,
    PEAK_VALUE_ONLY,
    added_claims,
    carry_over,
    v3_id,
)
from voxeltrace.evidence.claims import _PROTOCOL_FACTS


def v2rec(question, family="claim", target=None, id_="S-adversarial-009-v2"):
    return {
        "id": id_,
        "class": "ADVERSARIAL",
        "family": family,
        "question": question + "\n\nLABEL DEFS\n\nschema",
        "context": None,
        "images": [],
        "target": target or {"label": "CONTRADICTED"},
        "target_v1": None,
        "provenance": {"subject_pseudonym": "S"},
    }


def test_negations_cover_every_claims_rule_fact():
    assert set(NATURAL_NEGATION) == set(_PROTOCOL_FACTS)
    for fact, (aff, neg) in NATURAL_NEGATION.items():
        assert aff == _PROTOCOL_FACTS[fact][0]
        assert "NOT:" not in neg and " not " in f" {neg} "


def test_v3_id():
    assert v3_id("S-x-001-v2") == "S-x-001-v3"


def test_not_prefix_rewritten_label_unchanged():
    r = carry_over(v2rec('Is the statement "NOT: Reconstruction used time-of-flight" supported?'))
    first = r["question"].split("\n\n")[0]
    assert first == 'Is the statement "Reconstruction did not use time-of-flight" supported?'
    assert r["target"] == {"label": "CONTRADICTED"}
    assert r["v3_changes"] == ["NOT_PREFIX_TO_NATURAL_NEGATION"]
    assert r["parent_id"] == "S-adversarial-009-v2" and r["id"] == "S-adversarial-009-v3"
    assert r["question"].endswith("LABEL DEFS\n\nschema")


def test_unknown_negation_refused():
    with pytest.raises(ValueError):
        carry_over(v2rec('Is the statement "NOT: Something new" supported?'))


def test_suvpeak_definition_dropped_from_task_only():
    q = (
        "Using the structured evidence, what is the SUVpeak of segment 1 and how is SUVpeak "
        "defined in this evidence?"
    )
    tgt = {"status": "REPORTED", "values": {"suv_peak": 12.2}}
    r = carry_over(v2rec(q, family="value", target=tgt))
    assert r["question"].split("\n\n")[0].endswith(PEAK_VALUE_ONLY)
    assert "defined" not in r["question"].split("\n\n")[0]
    assert r["target"] == tgt
    assert r["v3_changes"] == ["SUVPEAK_DEFINITION_INDEPENDENT"]


def test_unchanged_record_has_no_changes():
    r = carry_over(v2rec('Is the statement "SUVmax is 1" supported?'))
    assert r["v3_changes"] == []


def _fake(monkeypatch, value_status=None, protocol_status="CONTRADICTED"):
    calls = []

    def fake_quantity(ev, metric, claimed, *, segment, claim_id):
        calls.append((metric, claimed))
        status = "SUPPORTED" if claim_id.startswith("v3-exact") else "CONTRADICTED"
        return SimpleNamespace(status=value_status or status, statement=f"{metric} is {claimed}")

    def fake_fact(p, fact, claimed=True):
        st = _PROTOCOL_FACTS[fact][0]
        return SimpleNamespace(
            status=protocol_status if not claimed else "SUPPORTED",
            statement=st if claimed else f"NOT: {st}",
            claim_id=f"protocol-{fact}",
        )

    monkeypatch.setattr(dev_v3, "claim_quantity", fake_quantity)
    monkeypatch.setattr(dev_v3, "claim_protocol_fact", fake_fact)
    les = SimpleNamespace(
        segment_number=1,
        voxel_count=10,
        suv_max=10.0,
        suv_mean=4.0,
        suv_median=3.0,
        suv_peak=SimpleNamespace(value=8.0),
        mtv_ml=2.0,
        tlg=8.0,
    )
    ev = SimpleNamespace(measured=SimpleNamespace(lesions=[les]))
    return ev, calls


def test_added_claims_balanced(monkeypatch):
    ev, calls = _fake(monkeypatch)
    recs, dropped = added_claims("S", ev, None, {"quantitative_evidence": {}}, {"a": 1})
    assert not dropped
    value = [r for r in recs if r["v3_variant"].startswith("VALUE_")]
    assert len(value) == 18  # 6 metrics x (exact, halved, doubled)
    assert ("suv_max", "5") in calls and ("suv_max", "20") in calls
    labels = {r["v3_variant"]: r["target"]["label"] for r in value}
    assert labels == {
        "VALUE_EXACT": "SUPPORTED",
        "VALUE_HALVED": "CONTRADICTED",
        "VALUE_DOUBLED": "CONTRADICTED",
    }
    neg = [r for r in recs if r["v3_variant"] == "PROTOCOL_NATURAL_NEGATION"]
    assert len(neg) == 5 and all("NOT:" not in r["question"] for r in neg)
    assert all(
        r["provenance"]["target_sources"][0]["source_ref"].endswith(":claimed_false") for r in neg
    )
    assert len({r["id"] for r in recs}) == len(recs) == 28


def test_rule_disagreement_dropped_not_relabelled(monkeypatch):
    ev, _ = _fake(monkeypatch, value_status="NOT_ESTABLISHED")
    recs, dropped = added_claims("S", ev, None, {}, {})
    assert not any(r["v3_variant"].startswith("VALUE_") for r in recs)
    assert len(dropped) == 18


def test_protocol_label_taken_from_rule(monkeypatch):
    ev, _ = _fake(monkeypatch, protocol_status="NOT_ESTABLISHED")
    recs, _ = added_claims("S", ev, None, {}, {})
    neg = [r for r in recs if r["v3_variant"] == "PROTOCOL_NATURAL_NEGATION"]
    assert {r["target"]["label"] for r in neg} == {"NOT_ESTABLISHED"}
