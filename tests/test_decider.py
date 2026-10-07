"""bev-decider in the multi-agent (reports/bev_decider.md).

Every assertion is on what an episode publishes or on the board, never on the
arithmetic that produced it. The decider's backends below are mocks that
answer in bev-decide's /v1/systemone format; they test the plumbing and the
rules, not bev-decider.
"""
import json
import math
from pathlib import Path

import pytest
import yaml

from fieldmind.multi import merge_rules as mr
from fieldmind.multi.agents.decider import check_answer
from fieldmind.multi.blackboard import Blackboard, WriterError
from fieldmind.multi.lanes import SimLane
from fieldmind.multi.scheduler import Scheduler
from fieldmind.runtime.llm_backend import LLMReply, MockBackend, register_backend

ROOT = Path(__file__).resolve().parent.parent
DEV = ROOT / "data/episodes_dev"
EP = "dev_A01_fcv_seize"

needs_dev = pytest.mark.skipif(not (DEV / EP).exists(), reason="dev episodes not generated")


# ------------------------------------------------------------ decider mocks
def _answer(choice, probs):
    return json.dumps({"answers": {"root_cause": {"type": "choice", "choice": choice,
                                                  "probabilities": probs}}})


class ContrarianMock(MockBackend):
    """The decider always backs the LAST offered case (belief's third)."""

    def generate(self, prompt, role="generic", max_tokens=512, mock_hint=None):
        if role != "decider":
            return super().generate(prompt, role, max_tokens, mock_hint)
        keys = mock_hint["options"]
        probs = {k: (0.9 if k == keys[-1] else 0.1 / (len(keys) - 1)) for k in keys}
        return LLMReply(text=_answer(keys[-1], probs), backend="mock", model="mock-0",
                        prefill_tokens=None, decode_tokens=0)


class RogueMock(MockBackend):
    """The decider names a case it was not offered."""

    def generate(self, prompt, role="generic", max_tokens=512, mock_hint=None):
        if role != "decider":
            return super().generate(prompt, role, max_tokens, mock_hint)
        probs = {k: 0.0 for k in mock_hint["options"][1:]}
        probs["RCA-99"] = 1.0
        return LLMReply(text=_answer("RCA-99", probs), backend="mock", model="mock-0")


class DownMock(MockBackend):
    """bev-decide is unreachable: every decider call fails."""
    seen = []

    def generate(self, prompt, role="generic", max_tokens=512, mock_hint=None):
        if role != "decider":
            return super().generate(prompt, role, max_tokens, mock_hint)
        DownMock.seen.append(prompt)
        return LLMReply(text="", status="error", error="connection: refused",
                        backend="mock", model="mock-0", prefill_tokens=None, decode_tokens=None)


for _n, _c in (("mock_contrarian", ContrarianMock), ("mock_rogue", RogueMock), ("mock_down", DownMock)):
    register_backend(_n, _c)


def _cfg(backend="mock", decider=True, overlay="bev.yaml"):
    from run_demo import _deep_merge
    cfg = yaml.safe_load((ROOT / "configs/base.yaml").read_text())
    _deep_merge(cfg, yaml.safe_load((ROOT / "configs" / overlay).read_text()))
    cfg["llm"]["backend"] = backend
    cfg["agent"]["log_prompts"] = True
    cfg["multi"]["merge_rule"] = "nudge"
    cfg["multi"]["decider"]["enabled"] = decider
    return cfg


def _run(cfg, ep=EP):
    from bench.harness import Episode, run_episode
    return run_episode(Episode(DEV / ep), cfg, arch="multi")


def _records(run, agent):
    return [c for a in run["assessments"] for c in (a.get("multi") or {}).get("compact", [])
            if c.get("agent") == agent]


def _published(run):
    return [[h.get("case_ref") for h in a["hypotheses"]] for a in run["assessments"]]


@pytest.fixture(scope="module")
def runs():
    if not (DEV / EP).exists():
        pytest.skip("dev episodes not generated")
    return {
        # arm A: accuracy.yaml + nudge, no decider anywhere in the config
        "A": _run(_cfg(decider=False, overlay="accuracy.yaml")),
        # the bev.yaml config with the decider switched off (lane present, idle)
        "off": _run(_cfg(decider=False)),
        "mock": _run(_cfg()),
        "contrarian": _run(_cfg("mock_contrarian")),
        "rogue": _run(_cfg("mock_rogue")),
        "down": _run(_cfg("mock_down")),
    }


# ---------------------------------------------------------------- off = same
@needs_dev
def test_decider_off_publishes_exactly_what_arm_a_publishes(runs):
    a, off = runs["A"], runs["off"]
    assert [x["hypotheses"] for x in off["assessments"]] == [x["hypotheses"] for x in a["assessments"]]
    assert [x["actions"] for x in off["assessments"]] == [x["actions"] for x in a["assessments"]]
    assert [x["state"] for x in off["assessments"]] == [x["state"] for x in a["assessments"]]
    assert "decider" not in off["multi"] and not _records(off, "decider")


@needs_dev
def test_a_decider_that_never_counts_changes_nothing_published(runs):
    """Rejected (rogue) and failed (down) answers reach no offset: the episode
    publishes what arm A publishes, tick for tick."""
    for k in ("rogue", "down"):
        assert _published(runs[k]) == _published(runs["A"]), k
        assert not any("decider_offsets" in r for r in _records(runs[k], "rule")), k


# ------------------------------------------------------------ gate checking
@needs_dev
def test_an_answer_naming_a_case_not_offered_is_rejected_every_time(runs):
    r = runs["rogue"]
    t = r["multi"]["decider"]
    assert t["calls"] > 0 and t["rejected"] == t["calls"] and t["failed"] == 0
    assert all("ranking" not in d and "offered" in d["why"] for d in _records(r, "decider"))


@needs_dev
def test_a_failed_call_is_logged_and_asked_again_next_tick(runs):
    r = runs["down"]
    t = r["multi"]["decider"]
    recs = _records(r, "decider")
    assert t["failed"] == t["calls"] == len(recs) > 0
    assert all(d["status"] == "error" for d in recs)
    # nothing was kept, so unchanged evidence is asked about again: more calls
    # than the run whose answers are kept and re-used
    assert t["calls"] > runs["mock"]["multi"]["decider"]["calls"]


@pytest.mark.parametrize("payload,why", [
    ({"type": "noul", "noul": 0.9}, "not a choice"),
    ({"type": "choice", "choice": "A", "probabilities": {"A": 0.6, "B": 0.4}}, "offered"),
    ({"type": "choice", "choice": "A", "probabilities": {"A": 0.5, "B": 0.3, "C": 0.1, "D": 0.1}}, "offered"),
    ({"type": "choice", "choice": "A", "probabilities": {"A": 1.2, "B": 0.0, "C": 0.0}}, "probability of A"),
    ({"type": "choice", "choice": "A", "probabilities": {"A": True, "B": 0.0, "C": 0.0}}, "probability of A"),
    ({"type": "choice", "choice": "Z", "probabilities": {"A": 0.5, "B": 0.3, "C": 0.2}}, "not offered"),
])
def test_check_answer_refuses(payload, why):
    ok, msg, ranking = check_answer(payload, ["A", "B", "C"])
    assert not ok and why in msg and ranking == []


def test_check_answer_ranks_by_probability_ties_in_belief_order():
    ok, _, ranking = check_answer({"type": "choice", "choice": "B",
                                   "probabilities": {"A": 0.2, "B": 0.4, "C": 0.4}}, ["A", "B", "C"])
    assert ok and ranking == ["B", "C", "A"]


# -------------------------------------------------------------- capped nudge
@needs_dev
def test_the_contrarian_decider_moves_the_ranking_but_never_past_the_cap(runs):
    r = runs["contrarian"]
    rules = [x for x in _records(r, "rule") if "decider_offsets" in x]
    assert rules, "the decider's answers never reached the nudge"
    for x in rules:
        assert max(x["offsets"].values()) <= mr.CAP + 1e-9                 # the SUM is capped
        assert max(x["decider_offsets"].values()) <= mr.CAP + 1e-9
        for c, v in x["offsets"].items():                                    # sum, capped
            want = min(mr.CAP, x["model_offsets"].get(c, 0) + x["decider_offsets"].get(c, 0))
            assert v == pytest.approx(want, abs=1e-4)
    # it did change what was published somewhere (else this test proves nothing)
    assert _published(r) != _published(runs["A"])


@needs_dev
def test_the_diagnosticians_offsets_are_untouched_by_the_decider(runs):
    """The decider's offsets live apart: the diagnosticians' own offsets follow
    the same path tick for tick as in arm A (their answers do not depend on what
    is published, tests/test_rule_prompt_identity.py), whatever the decider says."""
    def model_offsets(run):
        return [x.get("model_offsets", x.get("offsets")) for x in _records(run, "rule")]
    base = model_offsets(runs["A"])
    for k in ("mock", "contrarian"):
        assert model_offsets(runs[k]) == base, k


def test_total_offsets_sums_and_caps_and_is_the_identity_without_a_decider():
    model = {"A": 1.0, "B": 0.35}
    assert mr.total_offsets(model, {}) == model
    assert mr.total_offsets(model, {"A": 0.35, "C": 0.175}) == {"A": 1.2, "B": 0.35, "C": 0.175}


# ------------------------------------------------------------ candidates
def _fake_bb(belief, model_ranking):
    from types import SimpleNamespace as N
    secs = {"belief": [N(case_ref=c, cause=f"cause {c}", confidence=p, retired=False) for c, p in belief],
            "model_ranking": model_ranking}
    return N(read=lambda s: secs[s])


def test_union_is_belief_top3_then_the_models_new_cases_of_this_tick_only():
    from fieldmind.multi.agents.decider import DeciderAgent
    lib = {"RCA-05": {"root_cause": "lib cause 05"}, "RCA-06": {"root_cause": "lib cause 06"}}
    d = DeciderAgent(None, {"top_k": 3, "question": "q", "candidates": "union"}, library=lib)
    bb = _fake_bb([("RCA-01", 0.9), ("RCA-02", 0.7), ("RCA-03", 0.5), ("RCA-04", 0.4)],
                  {"tick": 7, "cases": ["RCA-02", "RCA-05", "RCA-04", "RCA-06"]})
    got = d.offered(bb, 7)
    assert [c for c, _ in got] == ["RCA-01", "RCA-02", "RCA-03", "RCA-05", "RCA-04"]   # model's top 3 only
    assert dict(got)["RCA-05"] == "lib cause 05" and dict(got)["RCA-04"] == "cause RCA-04"
    assert [c for c, _ in d.offered(bb, 8)] == ["RCA-01", "RCA-02", "RCA-03"]          # stale ranking ignored
    b = DeciderAgent(None, {"top_k": 3, "question": "q", "candidates": "belief"}, library=lib)
    assert [c for c, _ in b.offered(bb, 7)] == ["RCA-01", "RCA-02", "RCA-03"]
    with pytest.raises(ValueError):
        DeciderAgent(None, {"top_k": 3, "question": "q", "candidates": "everything"})


# ------------------------------------------------------- flat-case guard
FLAT = None


class FlatLoverMock(MockBackend):
    """The decider backs a flat case whenever one is offered (else the last)."""

    def generate(self, prompt, role="generic", max_tokens=512, mock_hint=None):
        if role != "decider":
            return super().generate(prompt, role, max_tokens, mock_hint)
        keys = mock_hint["options"]
        pick = next((k for k in keys if k in ("RCA-09", "RCA-10", "RCA-15")), keys[-1])
        probs = {k: (0.9 if k == pick else 0.1 / (len(keys) - 1)) for k in keys}
        return LLMReply(text=_answer(pick, probs), backend="mock", model="mock-0",
                        prefill_tokens=None, decode_tokens=0)


register_backend("mock_flatlover", FlatLoverMock)


def test_decider_nudges_only_lowers_flat_cases():
    off = {"A": 0.35, "F": 0.35}
    plain = mr.decider_nudges(off, ["F", "B", "A"])
    guarded = mr.decider_nudges(off, ["F", "B", "A"], frozenset({"F"}))
    assert plain == mr.add_nudges(off, [{"case_ref": c} for c in ["F", "B", "A"]])
    assert guarded["F"] == 0.35 and plain["F"] == 0.7
    assert {k: v for k, v in guarded.items() if k != "F"} == {k: v for k, v in plain.items() if k != "F"}
    assert "G" not in mr.decider_nudges({}, ["G", "B"], frozenset({"G"}))


def _right_ticks(run):
    gr = json.loads((ROOT / "data/kb/case_groups.json").read_text())["groups"]
    grp = {m: g["id"] for g in gr for m in g["members"]}
    gt = run["ground_truth"]
    true = grp.get(gt["root_cause_id"], gt["root_cause_id"])
    out = {}
    for a in run["assessments"]:
        if a["tick"] * gt["tick_period_s"] >= gt["fault_onset_t"] and a["hypotheses"]:
            c = a["hypotheses"][0].get("case_ref")
            out[a["tick"]] = grp.get(c, c) == true
    return out


@needs_dev
@pytest.mark.parametrize("ep", ["dev_A01_fcv_seize", "dev_B03_tube_leak_slow", "dev_D01_high_cv_coal"])
def test_the_flat_guard_is_never_worse_tick_by_tick_and_does_bite(ep):
    """The guard's claim, on episodes: with a decider that pushes flat cases,
    every scored tick right without the guard is right with it."""
    from bench.replay_multi import published, replay
    on = _cfg("mock_flatlover")
    off = _cfg("mock_flatlover")
    off["multi"]["decider"]["guard_flat"] = False
    r_on, r_off = _run(on, ep), _run(off, ep)
    right_on, right_off = _right_ticks(r_on), _right_ticks(r_off)
    assert right_on.keys() == right_off.keys()
    assert all(right_on[t] for t in right_off if right_off[t])          # never worse
    flat = {"RCA-09", "RCA-10", "RCA-15"}
    pushed = lambda run: any(x.get("decider_offsets", {}).get(c, 0) > 0
                             for x in _records(run, "rule") for c in flat)
    assert not pushed(r_on)
    if ep in ("dev_A01_fcv_seize", "dev_B03_tube_leak_slow"):          # the guard really acts here:
        assert pushed(r_off) and _published(r_on) != _published(r_off)  # published differs and some
        assert any(right_on[t] and not right_off[t] for t in right_on)  # ticks become right
    for r in (r_on, r_off):
        assert replay(r, "nudge") == published(r)


# ------------------------------------------------------- offline replay
@needs_dev
def test_the_offline_replay_reproduces_decider_runs_tick_for_tick(runs):
    """bench/replay_multi.py (and so bench/benchmark.py's keep-check) replays a
    nudge run with the decider exactly, from the run file alone."""
    from bench.replay_multi import published, replay
    for k in ("mock", "contrarian", "rogue", "A"):
        assert replay(runs[k], "nudge") == published(runs[k]), k


@needs_dev
def test_the_benchmark_runner_keeps_a_correct_board_decider_run_and_rejects_a_wrong_lane(runs):
    """bench/benchmark.py's keep-check on a decider run: the replay passes, and on
    the board the decider's calls must come from bev-decide's model on its lane."""
    import copy
    from types import SimpleNamespace
    from bench.benchmark import Runner
    L, BEV = "Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf", "bev-decider-0.4B-backbone-Q8_0.gguf"
    cfg = _cfg()
    run = copy.deepcopy(runs["mock"])
    for a in run["assessments"]:                       # what a correct board run reports
        for e in a["envelopes"]:
            lane = cfg["multi"]["fixed_placement"].get(e["agent"], "npu")
            e["backend"] = lane
            e["model"] = f"/data/local/tmp/llm/{BEV if lane == 'bev' else L}"
        for t in (a.get("multi") or {}).get("text", []):
            t["envelope"].update(backend="cpu", model=f"/data/local/tmp/llm/{L}")

    def check(c):
        me = SimpleNamespace(args=SimpleNamespace(arch="multi"), board=True, cfg=c,
                             test=SimpleNamespace(params={"merge_rule": "nudge",
                                                          "models": {"npu": L, "cpu": L}}))
        return Runner.check_run(me, run)
    assert check(cfg) == []
    e = next(e for a in run["assessments"] for e in a["envelopes"] if e["agent"] == "decider")
    e["backend"] = "npu"                                  # the decider answered from the wrong lane
    assert any("decider" in p and "backend" in p for p in check(cfg))


# -------------------------------------------------- belief is never written
@needs_dev
def test_belief_is_identical_with_and_without_the_decider(runs):
    """Plan rule: model answers never write belief. Belief's own ranking (log-
    odds, confidence) per tick is the same whatever the decider says."""
    base = [a.get("belief_ranking") for a in runs["A"]["assessments"]]
    for k in ("mock", "contrarian"):
        assert [a.get("belief_ranking") for a in runs[k]["assessments"]] == base, k


# ------------------------------------------------------------- when it runs
@needs_dev
def test_the_decider_asks_only_when_its_evidence_changed(runs):
    r = runs["mock"]
    recs = _records(r, "decider")
    assert recs and r["multi"]["decider"]["calls"] == len(recs)
    non_quiet = sum(1 for a in r["assessments"] if a["triage"] != "QUIET")
    assert len(recs) < non_quiet                       # unchanged ticks make no call
    # every call offers belief's top 3, in belief's order: confidence, ties in
    # insertion order (the run's belief_ranking and belief_order of that tick)
    by_tick = {a["tick"]: a for a in r["assessments"]}
    for d in recs:
        a = by_tick[d["evidence_tick"]]
        ins = {c: i for i, c in enumerate(a["belief_order"])}
        live = [b for b in a["belief_ranking"] if b.get("case_ref")]
        want = [b["case_ref"] for b in sorted(live, key=lambda b: (-b["confidence"], ins[b["case_ref"]]))][:3]
        assert d["offered"][:d["n_belief"]] == want                # belief's top 3 first, in order
        extra = d["offered"][d["n_belief"]:]                        # then the model's, at most 3, new ones
        assert len(extra) <= 3 and not set(extra) & set(want) and len(set(d["offered"])) == len(d["offered"])
    assert all(d["ranking"] == d["offered"] for d in recs)        # the mock backs the first offered
    assert any(len(d["offered"]) > d["n_belief"] for d in recs)    # union added cases somewhere


@needs_dev
def test_every_decider_call_is_logged_with_its_size_and_stays_under_the_prompt_limit(runs):
    envs = [e for a in runs["mock"]["assessments"] for e in a["envelopes"] if e["agent"] == "decider"]
    assert envs
    for e in envs:
        assert e["prompt_tokens"] > 0 and e["tokens"]["decode"] == 0
        assert e["prompt_tokens"] < 1280                                 # plan rule 4
        req = json.loads(e["prompt"])
        assert set(req) == {"state", "questions"}
        q = req["questions"]["root_cause"]
        assert q["type"] == "choice" and 2 <= len(q["criteria"]) <= 6
        assert q["instructions"] == "Which root cause best explains the plant facts?"
        assert all(line.startswith("[") for line in req["state"].splitlines())


@needs_dev
def test_the_decider_runs_on_its_own_lane_only(runs):
    lanes = {l["lane"]: l for l in runs["mock"]["multi"]["lanes"]}
    calls = runs["mock"]["multi"]["decider"]["calls"]
    assert lanes["bev"]["kind"] == "decider" and lanes["bev"]["n_jobs"] == calls
    off = {l["lane"]: l for l in runs["off"]["multi"]["lanes"]}
    assert off["bev"]["n_jobs"] == 0                     # no llm agent ever lands there


# ------------------------------------------------------- configuration rules
def test_bev_yaml_is_accuracy_yaml_plus_the_decider_and_nothing_else():
    acc = yaml.safe_load((ROOT / "configs/accuracy.yaml").read_text())
    bev = yaml.safe_load((ROOT / "configs/bev.yaml").read_text())
    bev["multi"]["fixed_placement"].pop("decider")
    bev["multi"]["lanes"].pop("bev")
    bev["multi"].pop("decider")
    assert bev["multi"].pop("merge_rule") == "nudge"
    acc["multi"].pop("merge_rule")
    assert bev == acc


def test_decider_off_by_default():
    base = yaml.safe_load((ROOT / "configs/base.yaml").read_text())
    assert base["multi"]["decider"]["enabled"] is False
    assert all(l.get("kind", "llm") == "llm" for l in base["multi"]["lanes"].values())


@needs_dev
def test_the_decider_needs_nudge_and_a_decider_lane():
    from bench.harness import build_multi_agent
    cfg = _cfg()
    cfg["multi"]["merge_rule"] = "tiebreak"
    with pytest.raises(ValueError, match="nudge"):
        build_multi_agent(cfg, [])
    cfg = _cfg()
    cfg["multi"]["lanes"]["bev"]["kind"] = "llm"
    with pytest.raises(ValueError, match="wrong kind|decider"):
        build_multi_agent(cfg, [])


def _lanes():
    return [SimLane("npu", MockBackend(), 909, 13.9), SimLane("cpu", MockBackend(), 126, 42),
            SimLane("bev", MockBackend(), 909, 13.9, kind="decider")]


@pytest.mark.parametrize("placement", [{"decider": "npu"}, {"diag_water": "bev"}])
def test_fixed_placement_on_a_lane_of_the_wrong_kind_is_refused(placement):
    fp = {"diag_water": "npu", "diag_heat": "npu", "decider": "bev", **placement}
    with pytest.raises(ValueError, match="wrong kind"):
        Scheduler(_lanes(), {"placement": "fixed", "fixed_placement": fp})


def test_earliest_finish_keeps_llm_agents_off_the_decider_lane_and_the_decider_on_it():
    s = Scheduler(_lanes(), {"placement": "earliest_finish"})
    s.lanes[0].free_at = s.lanes[1].free_at = 1e9             # llm lanes busy, bev idle
    j = s.new_job("diag_water", 0, 2, 60, 0.0)
    assert s.choose_lane(j, 500).name in ("npu", "cpu")
    d = s.new_job("decider", 0, 3, 0, 0.0)
    assert s.choose_lane(d, 500).name == "bev"


def test_only_the_gate_writes_the_decider_sections():
    from fieldmind.agent.world_model import WorldModel
    bb = Blackboard(WorldModel(), audit=True)
    for agent in ("decider", "retriever", "scheduler"):
        for sec in ("decider_answer", "decider_evidence"):
            with pytest.raises(WriterError):
                bb.write(sec, {"x": 1}, agent)
    bb.write("decider_evidence", {"A": 0.35}, "gate")
    assert dict(bb.read("decider_evidence")) == {"A": 0.35}
