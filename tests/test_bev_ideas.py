"""bev ideas (reports/bev_ideas.md): one switch per bev-decider use.

Assertions are on what an episode publishes, on the board and on the logged
records, never on the arithmetic that produced them. The bev backends here are
mocks in bev-decide's /v1/systemone format: plumbing and rules, not bev.
"""
import json
from pathlib import Path

import pytest
import yaml

from fieldmind.multi.agents import bev as bevmod
from fieldmind.multi.agents.bev import BevAgent, check_answers
from fieldmind.multi.blackboard import Blackboard, WriterError
from fieldmind.multi.lanes import SimLane
from fieldmind.multi.scheduler import Scheduler
from fieldmind.runtime.llm_backend import LLMReply, MockBackend, call_record

ROOT = Path(__file__).resolve().parent.parent
DEV = ROOT / "data/episodes_dev"
EP = "dev_A01_fcv_seize"
needs_dev = pytest.mark.skipif(not (DEV / EP).exists(), reason="dev episodes not generated")


def cfg_with(overlay="bev3.yaml", backend="mock", decider=False, **switches):
    """bev3.yaml (v3 + the bev lane), the decider off unless asked, the bev
    placement key added, and the given bev switches."""
    from run_demo import _deep_merge
    cfg = yaml.safe_load((ROOT / "configs/base.yaml").read_text())
    _deep_merge(cfg, yaml.safe_load((ROOT / "configs" / overlay).read_text()))
    cfg["llm"]["backend"] = backend
    cfg["agent"]["log_prompts"] = True
    cfg["multi"]["decider"]["enabled"] = decider
    cfg["multi"]["fixed_placement"]["bev"] = "bev"
    cfg["multi"]["bev"].update(switches)
    return cfg


def run(cfg, ep=EP):
    from bench.harness import Episode, run_episode
    return run_episode(Episode(DEV / ep), cfg, arch="multi")


def records(run_, agent, idea=None):
    return [c for a in run_["assessments"] for c in (a.get("multi") or {}).get("compact", [])
            if c.get("agent") == agent and (idea is None or c.get("idea") == idea)]


def published(run_):
    return [([h.get("case_ref") for h in a["hypotheses"]], [x["id"] for x in a["actions"]])
            for a in run_["assessments"]]


# ------------------------------------------------------------- switches
def test_switches_read_yaml_bools_and_refuse_anything_else():
    sw = bevmod.switches({"bev": {"explain": False, "first": "shadow", "actions": True}})
    assert sw["explain"] == "off" and sw["first"] == "shadow" and sw["actions"] == "on"
    assert all(sw[k] == "off" for k in bevmod.IDEAS if k not in ("explain", "first", "actions"))
    with pytest.raises(ValueError, match="must be one of"):
        bevmod.switches({"bev": {"explain": "maybe"}})
    with pytest.raises(ValueError, match="unknown key"):
        bevmod.switches({"bev": {"explian": "on"}})


def test_base_yaml_has_every_switch_off():
    cfg = yaml.safe_load((ROOT / "configs/base.yaml").read_text())
    assert set(bevmod.switches(cfg["multi"]).values()) == {"off"}


@pytest.mark.parametrize("idea", ["first", "rt_fallback"])
def test_first_threshold_has_no_default_when_on(idea):
    cfg = cfg_with(**{idea: "on"})
    with pytest.raises(ValueError, match="first_threshold"):
        BevAgent(MockBackend(), cfg["multi"])
    BevAgent(MockBackend(), cfg_with(**{idea: "shadow"})["multi"])     # shadow needs none
    cfg["multi"]["bev"]["first_threshold"] = 0.6
    BevAgent(MockBackend(), cfg["multi"])


# ---------------------------------------------------------- answer check
SPEC = {"c": {"type": "choice", "options": ["A", "B"]}, "y": {"type": "noul", "options": []}}
GOOD = {"c": {"type": "choice", "choice": "B", "probabilities": {"A": 0.3, "B": 0.7}},
        "y": {"type": "noul", "noul": 0.2}}


def test_check_answers_ranks_choices_and_keeps_yes_no():
    ok, why, out = check_answers(GOOD, SPEC)
    assert ok, why
    assert out["c"]["ranking"] == ["B", "A"] and out["y"]["p"] == 0.2


@pytest.mark.parametrize("bad, why", [
    ({"c": GOOD["c"]}, "asked"),                                            # a question unanswered
    ({**GOOD, "z": GOOD["y"]}, "asked"),                                    # an extra answer
    ({**GOOD, "c": {**GOOD["c"], "choice": "Z"}}, "not offered"),
    ({**GOOD, "c": {**GOOD["c"], "probabilities": {"A": 0.3, "Z": 0.7}}}, "probabilities"),
    ({**GOOD, "c": {**GOOD["c"], "probabilities": {"A": 1.3, "B": 0.7}}}, "probability"),
    ({**GOOD, "y": {"type": "noul", "noul": True}}, "P\\(yes\\)"),
    ({**GOOD, "y": {"type": "noul", "noul": 1.5}}, "P\\(yes\\)"),
    ({**GOOD, "y": {"type": "choice"}}, "not a noul"),
])
def test_check_answers_rejects_the_whole_reply_for_one_bad_question(bad, why):
    ok, msg, out = check_answers(bad, SPEC)
    assert not ok and out == {}
    assert __import__("re").search(why, msg), msg


# ------------------------------------------------------------- lanes
def lanes():
    return [SimLane("npu", MockBackend(), 909, 13.9), SimLane("cpu", MockBackend(), 126, 42),
            SimLane("bev", MockBackend(), 909, 13.9, kind="decider")]


def test_bev_jobs_go_to_the_bev_lane_by_the_explicit_bev_key():
    s = Scheduler(lanes(), {"placement": "fixed",
                            "fixed_placement": {"diag_water": "npu", "bev": "bev"}})
    assert s.choose_lane(s.new_job("bev_actions", 0, 3, 0, 0.0), 300).name == "bev"
    s2 = Scheduler(lanes(), {"placement": "fixed", "fixed_placement": {"diag_water": "npu"}})
    with pytest.raises(KeyError, match="no lane"):
        s2.choose_lane(s2.new_job("bev_actions", 0, 3, 0, 0.0), 300)
    with pytest.raises(ValueError, match="wrong kind"):
        Scheduler(lanes(), {"placement": "fixed", "fixed_placement": {"bev": "npu"}})
    ef = Scheduler(lanes(), {"placement": "earliest_finish"})
    ef.lanes[2].free_at = 1e9                       # bev lane busy: still the only one
    assert ef.choose_lane(ef.new_job("bev_first", 0, 3, 0, 0.0), 300).name == "bev"


def test_only_the_gate_writes_the_bev_sections():
    from fieldmind.agent.world_model import WorldModel
    bb = Blackboard(WorldModel(), audit=True)
    for agent in ("bev", "decider", "retriever", "scheduler"):
        for sec in ("bev_notes", "bev_flags"):
            with pytest.raises(WriterError):
                bb.write(sec, {"x": 1}, agent)
    bb.write("bev_flags", {"tick": 1}, "gate")


def test_server_timings_reach_the_call_record_only_from_bev():
    assert "server" not in call_record(LLMReply(text="x"))
    r = LLMReply(text="x", server_timings={"tokenize_ms": 1.0, "decode_ms": 20.0, "head_ms": 0.5})
    assert call_record(r)["server"] == {"tokenize_ms": 1.0, "decode_ms": 20.0, "head_ms": 0.5}


def test_mock_bev_answers_every_question_repeatably():
    m = MockBackend()
    hint = {"bev": {"c": {"type": "choice", "options": ["A", "B", "C"], "instructions": "q"},
                    "y": {"type": "noul", "options": [], "instructions": "q2"}}}
    a = json.loads(m.generate("{}", role="decider", mock_hint=hint).text)["answers"]
    b = json.loads(m.generate("{}", role="decider", mock_hint=hint).text)["answers"]
    assert a == b and a["c"]["choice"] == "A" and 0 <= a["y"]["noul"] <= 1
    ok, why, _ = check_answers(a, {k: {"type": v["type"], "options": v["options"]}
                                   for k, v in hint["bev"].items()})
    assert ok, why


# ------------------------------------------------------- orchestrator
def test_a_bev_switch_needs_a_bev_lane_and_its_placement_key():
    from bench.harness import build_multi_agent
    cfg = cfg_with(actions="shadow")
    del cfg["multi"]["fixed_placement"]["bev"]
    with pytest.raises(ValueError, match="fixed_placement.bev"):
        build_multi_agent(cfg, [])
    cfg = cfg_with(overlay="v3.yaml", actions="shadow")      # v3 has no bev lane
    del cfg["multi"]["fixed_placement"]["bev"]
    with pytest.raises(ValueError, match="kind 'decider'"):
        build_multi_agent(cfg, [])
    cfg = cfg_with(overlay="v3.yaml", clear_skip="on")       # code only: no lane needed
    del cfg["multi"]["fixed_placement"]["bev"]
    build_multi_agent(cfg, [])


def test_lockstep_only_ideas_refuse_real_time():
    from bench.harness import build_multi_agent
    orch = build_multi_agent(cfg_with(actions="shadow"), [])[0]
    orch.gate.merge_rule = "model"
    orch.diag.split = orch.diag.on_change = True
    with pytest.raises(NotImplementedError, match="lockstep only"):
        orch.start_realtime(object())
