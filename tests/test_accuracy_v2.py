"""Accuracy-fix steps 2, 3 and 6 as switches: the lean answer (no group letter,
no `x` / `n`), and case slots (at most one flat case, belief's top cases always
shown). Assertions on prompts, grammars and outcomes."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from fieldmind.multi import compact, grammar

ROOT = Path(__file__).resolve().parent.parent
DEV = ROOT / "data/episodes_dev"
LIB = {c["case_id"]: c for c in json.loads((ROOT / "data/kb/case_library.json").read_text())["cases"]}
FLAT = frozenset({"RCA-09", "RCA-10", "RCA-15"})


def C(cid, score):
    return dict(LIB[cid], score=score)


# ---------------------------------------------------------------- lean answer
def test_lean_grammar_accepts_only_a_ranking():
    rules = grammar.diagnosis(3, 4, 2, ["A", "B", "B", "G"], lean=True)
    assert grammar.accepts(rules, '{"r":[[2,[1,3]],[1,[1]]]}')
    assert grammar.accepts(rules, '{"r":[]}')
    assert not grammar.accepts(rules, '{"g":"B","r":[[2,[1]]],"sep":null,"n":[],"x":[]}')
    assert not grammar.accepts(rules, '{"r":[[5,[1]]]}')                   # line 5 not shown
    assert set(rules) >= {"root", "r"} and "g" not in rules and "unexpl" not in rules
    full = grammar.diagnosis(3, 4, 2, ["A", "B", "B", "G"])
    assert grammar.accepts(full, '{"g":"B","r":[[2,[1]]],"sep":null,"n":[],"x":[]}')


def test_lean_answer_expands_with_the_group_derived_by_code():
    lm = {"cases": [{"case_id": c, "root_cause": LIB[c]["root_cause"], "discriminating_evidence": ""}
                    for c in ("RCA-07", "RCA-10")],
          "facts": ["F1", "F2"], "fact_detail": ["a", "b"], "conf": [0.9, 0.3],
          "context": [], "evidence_tick": 7, "letters": ["G", "B"]}
    payload, info = compact.expand_diag_answer({"r": [[2, [1]], [1, [1, 2]]]}, lm)
    assert [h["case_ref"] for h in payload["hypotheses"]] == ["RCA-10", "RCA-07"]
    assert info["g"] == "B" and info["g_from"] == "code"
    assert payload["unexplained"] == [] and info["n"] == []


def test_lean_answer_switch_is_validated():
    with pytest.raises(ValueError):
        compact.compact_switches({"answer": "terse", "schema": True})
    with pytest.raises(ValueError):
        compact.compact_switches({"answer": "lean"})                        # needs schema


# ----------------------------------------------------------------- case slots
def test_at_most_one_flat_case_and_belief_top_cases_are_added():
    cases = [C("RCA-09", .5), C("RCA-10", .5), C("RCA-15", .4), C("RCA-07", .3)]
    got = compact.select_cases(cases, ["RCA-14", "RCA-07"], LIB, FLAT, "heat", 4)
    ids = [c["case_id"] for c in got]
    assert ids == ["RCA-09", "RCA-07", "RCA-14"]
    assert sum(i in FLAT for i in ids) == 1
    assert got[-1]["belief_slot"] is True


def test_belief_top_case_of_the_other_side_is_not_added():
    got = compact.select_cases([C("RCA-07", .5)], ["RCA-01"], LIB, FLAT, "heat", 4)
    assert [c["case_id"] for c in got] == ["RCA-07"]                       # RCA-01 is water-side


def test_over_k_drops_the_lowest_scoring_non_belief_case():
    cases = [C("RCA-07", .9), C("RCA-13", .2), C("RCA-14", .5), C("RCA-18", .4)]
    got = compact.select_cases(cases, ["RCA-03"], LIB, FLAT, "heat", 4)
    ids = [c["case_id"] for c in got]
    assert "RCA-03" in ids and "RCA-13" not in ids and len(ids) == 4


# -------------------------------------------------------------- the v2 config
def _cfg(overlay):
    from run_demo import _deep_merge
    cfg = yaml.safe_load((ROOT / "configs/base.yaml").read_text())
    _deep_merge(cfg, yaml.safe_load((ROOT / overlay).read_text()))
    cfg["llm"]["backend"] = "mock"
    cfg["agent"]["log_prompts"] = True
    return cfg


@pytest.mark.skipif(not (DEV / "dev_D01_high_cv_coal").exists(), reason="dev episodes not generated")
def test_v2_prompts_show_no_group_letter_request_no_example_and_one_flat_case():
    from bench.harness import Episode, run_episode
    run = run_episode(Episode(DEV / "dev_D01_high_cv_coal"), _cfg("configs/accuracy_v2.yaml"), arch="multi")
    prompts = [e["prompt"] for a in run["assessments"] for e in a["envelopes"] if e["agent"] == "diagnostician"]
    assert prompts
    for p in prompts:
        assert '"g"' not in p and "Example" not in p and '{"r":' in p
        shown = [l for l in p.split("RETRIEVED CASES:")[1].split("NOTES")[0].splitlines() if l[:2].rstrip(".").isdigit()]
        assert sum(any(f in l for f in FLAT) for l in shown) <= 1
    for a in run["assessments"]:
        for c in a["multi"]["compact"]:
            if c.get("agent") == "diagnostician":
                bel = sorted(a["belief_ranking"], key=lambda b: -b["confidence"])[:2]
                for b in bel:                            # belief's top cases are shown (if on this side)
                    from fieldmind.multi import sides
                    if b["case_ref"] not in FLAT and c["side"] in sides.case_sides(LIB[b["case_ref"]]):
                        assert b["case_ref"] in c["case_ids"], (a["tick"], b["case_ref"])
    assert all(e["agent"] != "verifier" for a in run["assessments"] for e in a["envelopes"])
    assert all(a["multi"]["text"] == [] for a in run["assessments"])          # no model note reader


# ------------------------------------------------------ bench/beats_belief.py
def _folder(tmp_path, rows, where="agent code on the laptop, model calls on the board"):
    for ep, pub, bel in rows:
        (tmp_path / f"{ep}_multi.summary.json").write_text(json.dumps({
            "meta": {"where": where},
            "evaluation": {"episode_id": ep, "T2_root_cause": {
                "applicable": True, "group_top1": pub, "belief_group": bel, "heldout": False}}}))
    return tmp_path


def _verdict(d):
    import subprocess
    import sys
    p = subprocess.run([sys.executable, "bench/beats_belief.py", str(d)], cwd=ROOT,
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def test_beats_belief_passes_only_above_the_mean_and_within_the_margin(tmp_path):
    rc, out = _verdict(_folder(tmp_path / "a", [("e1", .60, .55), ("e2", .80, .82)]) if (tmp_path / "a").mkdir() is None else None)
    assert rc == 0 and "PASS" in out
    rc, out = _verdict(_folder(tmp_path / "b", [("e1", .60, .55), ("e2", .70, .82)]) if (tmp_path / "b").mkdir() is None else None)
    assert rc == 1 and "FAIL" in out                            # one episode 0.12 below belief
    rc, out = _verdict(_folder(tmp_path / "c", [("e1", .55, .55), ("e2", .82, .82)]) if (tmp_path / "c").mkdir() is None else None)
    assert rc == 1                                              # equal is not beating


def test_beats_belief_refuses_mock_runs(tmp_path):
    (tmp_path / "m").mkdir()
    rc, out = _verdict(_folder(tmp_path / "m", [("e1", .9, .1)], where="MOCK backend on the laptop"))
    assert rc != 0 and "mock" in out
