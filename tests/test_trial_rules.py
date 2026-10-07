import csv
import json

import pydicom
import pytest
import yaml

from dicom_factory import build_pet_ct_seg_case
from voxeltrace.quant.reference_region import ReferenceRegionResult
from voxeltrace.rules import percist, qiba
from voxeltrace.rules.registry import get_ruleset, verdict
from voxeltrace.rules.schema import RuleCheck
from voxeltrace.rules.trial_overrides import TrialConfig, effective_ruleset
from voxeltrace.trial.audit import run_trial_audit
from voxeltrace.trial.export import export_audit
from voxeltrace.trial.perturb import EXPECTED, KINDS, perturb_case
from voxeltrace.trial.schema import PairContext, ScanPair, ScanTimepoint
from voxeltrace.trial.summary import site_summary


def tp(name, uptake_min=None, **kw):
    return ScanTimepoint(
        subject_id="S",
        timepoint=name,
        suv_status="PASS",
        uptake_s=None if uptake_min is None else uptake_min * 60,
        **kw,
    )


def ctx(b, f, **flags):
    return PairContext(
        pair=ScanPair(subject_id="S", baseline=b.timepoint, followup=f.timepoint),
        baseline=b,
        followup=f,
        site_flags=flags,
    )


@pytest.mark.parametrize(
    ("b", "f", "status"),
    [
        (60, 70, "PASS"),  # exactly 10 min
        (60, 70.5, "FAIL"),  # > 10 min
        (56, 54, "FAIL"),  # follow-up before 55 min
    ],
)
def test_qiba_uptake_difference(b, f, status):
    rule, fn = qiba.UPTAKE_DIFF, qiba.RULES[1][1]
    assert fn(rule, ctx(tp("B", b), tp("F", f))).status == status


def test_qiba_window_and_unknown():
    rule, fn = qiba.UPTAKE_WINDOW, qiba.RULES[0][1]
    assert fn(rule, ctx(tp("B", 55), tp("F", 75))).status == "PASS"
    assert fn(rule, ctx(tp("B", 54.9), tp("F", 60))).status == "FAIL"
    r = fn(rule, ctx(tp("B", 60), tp("F", None)))
    assert r.status == "UNKNOWN" and r.reasons[0].code == "AMBIGUOUS_TIMING"


def test_percist_uptake_15_min_and_50_min_floor():
    rule, fn = percist.UPTAKE_DIFF, percist.RULES[1][1]
    assert fn(rule, ctx(tp("B", 55), tp("F", 70))).status == "PASS"
    assert fn(rule, ctx(tp("B", 55), tp("F", 70.1))).status == "FAIL"
    assert fn(rule, ctx(tp("B", 49), tp("F", 55))).status == "FAIL"


def _liver(sul_mean, sd=0.2):
    return ReferenceRegionResult(
        status="COMPUTED", region="LIVER", sul_mean=sul_mean, sul_sd=sd, voxel_count=100
    )


@pytest.mark.parametrize(
    ("a", "b", "status"),
    [
        (1.5, 1.8, "PASS"),  # delta 0.3 = 0.3 SUL and 0.3 <= 0.2*1.8 = 0.36
        (1.5, 1.81, "FAIL"),  # > 0.3 SUL
        (1.0, 1.26, "FAIL"),  # 0.26 <= 0.3 but > 0.2*1.26 = 0.252
        (1.0, 1.25, "PASS"),  # 0.25 <= 0.25
    ],
)
def test_percist_liver_stability_boundaries(a, b, status):
    rule, fn = percist.LIVER, percist.RULES[2][1]
    assert (
        fn(rule, ctx(tp("B", 60, liver=_liver(a)), tp("F", 60, liver=_liver(b)))).status == status
    )


def test_percist_liver_missing_is_actionable():
    rule, fn = percist.LIVER, percist.RULES[2][1]
    r = fn(rule, ctx(tp("B", 60), tp("F", 60)))
    assert r.status == "UNKNOWN"
    assert {x.code for x in r.reasons} == {"MANUAL_OR_REFERENCE_MASK_REQUIRED"}
    assert r.reasons[0].info.remediation


def test_verdict_aggregation():
    def c(impact, status):
        return RuleCheck(
            rule_id="r",
            rule_version="1",
            standard="VOXELTRACE",
            name="r",
            impact=impact,
            status=status,
            expected="",
            source="",
        )

    assert verdict([c("blocking", "PASS"), c("warning", "PASS")]) == "ASSESSABLE"
    assert verdict([c("blocking", "PASS"), c("warning", "FAIL")]) == "ASSESSABLE_WITH_WARNINGS"
    assert verdict([c("blocking", "UNKNOWN"), c("warning", "PASS")]) == "INSUFFICIENT_INFORMATION"
    assert verdict([c("blocking", "FAIL"), c("blocking", "UNKNOWN")]) == "NOT_ASSESSABLE"


def test_rulesets_single_standard_and_cited():
    for rid in ("qiba-fdg-1.14", "percist-1.0", "eanm-fdg-2.0"):
        rs = get_ruleset(rid)
        assert len({r.standard for r, _ in rs.rules} - {"VOXELTRACE"}) == 1
        for r, _ in rs.rules:
            assert r.sources and all(s.quote and s.locator for s in r.sources)
    with pytest.raises(KeyError):
        get_ruleset("made-up-standard")


def test_trial_overrides_explicit():
    cfg = TrialConfig(
        trial_id="T1",
        ruleset="qiba-fdg-1.14",
        parameter_overrides={"QIBA-UPTAKE-DIFF": {"max_diff_min": 5.0}},
        disabled_rules=[
            {"rule_id": "QIBA-SAME-SYSTEM", "justification": "harmonised multi-scanner trial"}
        ],
    )
    rs = effective_ruleset(cfg)
    rule, _ = rs.rule("QIBA-UPTAKE-DIFF")
    assert rule.parameters["max_diff_min"] == 5.0 and rule.overridden_by == "TRIAL_OVERRIDE:T1"
    assert all(r.rule_id != "QIBA-SAME-SYSTEM" for r, _ in rs.rules)
    assert rs.version.endswith("+T1") and len(rs.overrides) == 2
    with pytest.raises(ValueError):
        TrialConfig(
            trial_id="T",
            ruleset="qiba-fdg-1.14",
            disabled_rules=[{"rule_id": "QIBA-SAME-SYSTEM", "justification": "no"}],
        )
    with pytest.raises(KeyError):
        effective_ruleset(
            TrialConfig(
                trial_id="T",
                ruleset="qiba-fdg-1.14",
                parameter_overrides={"QIBA-UPTAKE-DIFF": {"bogus": 1}},
            )
        )


@pytest.fixture(scope="module")
def trial(tmp_path_factory):
    root = tmp_path_factory.mktemp("trial")
    base = root / "real"
    build_pet_ct_seg_case(base)
    for f in (base / "a_pet").glob("*.dcm"):
        ds = pydicom.dcmread(f)
        ds.ConvolutionKernel = "XYZ Gauss2.00"
        ds.CorrectedImage = ["NORM", "DTIM", "ATTN", "SCAT", "DECY", "RAN"]
        ds.ReconstructionMethod = "PSF+TOF 2i21s"
        ds.save_as(f)
    t = root / "trial"
    t.mkdir()
    synth = {}
    for kind in KINDS:
        perturb_case(base, root / "p" / kind, kind)
        (t / kind).mkdir()
        (t / kind / "BASELINE").symlink_to(base, target_is_directory=True)
        (t / kind / "FOLLOWUP").symlink_to(root / "p" / kind, target_is_directory=True)
        synth[f"{kind}/FOLLOWUP"] = f"SYNTHETIC_PERTURBATION {kind}"
    (t / "trial.yaml").write_text(
        yaml.safe_dump(
            {
                "trial_id": "TEST",
                "ruleset": "qiba-fdg-1.14",
                "timepoint_order": ["BASELINE", "FOLLOWUP"],
                "sites": {k: ("SITE-A" if i % 2 else "SITE-B") for i, k in enumerate(KINDS)},
                "synthetic_perturbations": synth,
            }
        )
    )
    return t, root


def test_perturbations_never_touch_original(trial):
    _, root = trial
    with pytest.raises(FileExistsError):
        perturb_case(root / "real", root / "p" / "identity", "identity")
    for f in (root / "p" / "missing_dose" / "PT").glob("*.dcm"):
        ds = pydicom.dcmread(f, stop_before_pixels=True)
        assert ds.SeriesDescription.startswith("SYNTHETIC_PERTURBATION")
        break


def test_known_answer_perturbations_end_to_end(trial):
    t, root = trial
    audit = run_trial_audit(t)
    got = {p.pair.subject_id: p for p in audit.pairs}
    assert set(got) == set(KINDS)
    for kind, (exp_verdict, exp_rules) in EXPECTED.items():
        p = got[kind]
        blocking = {
            c.rule_id
            for c in p.checks
            if c.impact == "blocking" and c.status in ("FAIL", "UNKNOWN")
        }
        assert p.verdict == exp_verdict, (kind, p.verdict, blocking)
        assert set(exp_rules) <= blocking
        assert p.synthetic_perturbation
    paths = export_audit(audit, root / "out")
    rows = list(csv.DictReader((root / "out" / "subject_timepoint_matrix.csv").open()))
    assert {r["pair_verdict"] for r in rows} >= {"BASELINE", "ASSESSABLE", "NOT_ASSESSABLE"}
    summ = json.loads((root / "out" / "site_summary.json").read_text())
    assert summ["pairs_analyzed"] == 7 and set(summ["by_site"]) == {"SITE-A", "SITE-B"}
    assert "MISSING_REQUIRED_TAG" in summ["insufficient_information_by_reason"]
    assert all(p.exists() for p in paths)
    assert site_summary(audit)["synthetic_pairs"] == 7
