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


# ------------------------------------------------- commit 3: telemetry
def test_nested_steps_are_timed_exclusively():
    import time
    from fieldmind.agent.world_model import WorldModel
    bb = Blackboard(WorldModel(), audit=True)
    with bb.step("scheduler"):
        time.sleep(0.02)
        with bb.step("diagnostician"):
            time.sleep(0.05)
    stage, audit = bb.take_stage_ms()
    assert 50 <= stage["diagnostician"] < 80
    assert 20 <= stage["scheduler"] < 45            # the child's 50 ms are not the scheduler's
    assert audit >= 0 and bb.take_stage_ms() == ({}, 0.0)


class SleepyMock(MockBackend):
    """The mock's latency_ms is NOMINAL (it adds 5 ms it never spends); this
    one really spends what it reports, so step times can be checked against it."""

    def generate(self, prompt, role="generic", max_tokens=512, mock_hint=None):
        import time
        t0 = time.perf_counter()
        time.sleep(0.004)
        r = super().generate(prompt, role, max_tokens, mock_hint)
        r.latency_ms = (time.perf_counter() - t0) * 1000
        return r


from fieldmind.runtime.llm_backend import register_backend  # noqa: E402
register_backend("mock_sleepy", SleepyMock)


@pytest.fixture(scope="module")
def timed_run():
    if not (DEV / EP).exists():
        pytest.skip("dev episodes not generated")
    return run(cfg_with(decider=True, backend="mock_sleepy"))


def test_stage_times_cover_each_call_and_fit_inside_the_tick(timed_run):
    model_ticks = 0
    for a in timed_run["assessments"]:
        m = a["multi"]
        st = m["stage_ms"]
        assert sum(st.values()) + m["audit_ms"] <= m["tick_ms"] + 1.0
        for agent in ("diagnostician", "decider"):
            calls = [c["latency_ms"] for e in a["envelopes"] if e["agent"] == agent
                     for c in e.get("calls", [])]
            if calls:
                model_ticks += 1
                # the step wraps the call: the backend's own latency is inside it
                assert st[agent] >= sum(calls) - 0.5, (a["tick"], agent, st[agent], calls)
    assert model_ticks > 10


def test_lane_wall_busy_is_the_sum_of_its_calls(timed_run):
    lanes_ = {l["lane"]: l for l in timed_run["multi"]["lanes"]}
    by_lane = {}
    for a in timed_run["assessments"]:
        for e in a["envelopes"]:
            for c in e.get("calls", []):
                lane = "bev" if e["agent"] == "decider" else "npu" if e["agent"] == "diagnostician" else "cpu"
                by_lane[lane] = by_lane.get(lane, 0.0) + c["latency_ms"] / 1000
    for lane, s in by_lane.items():
        assert abs(lanes_[lane]["wall_busy_s"] - s) < 1e-3, lane
    summ = timed_run["multi"]["stage_ms"]
    assert summ["sensor"]["n"] == len(timed_run["assessments"])


# ----------------------------------------------- commit 4: clear_skip
@pytest.fixture(scope="module")
def skip_runs():
    if not (DEV / EP).exists():
        pytest.skip("dev episodes not generated")
    out = {}
    for ep in ("dev_B01_tube_leak", "dev_D01_high_cv_coal"):
        for mode in ("off", "shadow", "on"):
            out[(ep, mode)] = run(cfg_with(clear_skip=mode), ep)
    return out


def _rule(run_):
    return {c["now_tick"]: c for c in records(run_, "rule")}


def test_clear_skip_skips_only_on_clear_ticks_and_makes_no_call_for_that_side(skip_runs):
    n = 0
    for ep in ("dev_B01_tube_leak", "dev_D01_high_cv_coal"):
        r = skip_runs[(ep, "on")]
        rule = _rule(r)
        for a in r["assessments"]:
            for s in [c for c in a["multi"]["compact"] if c.get("idea") == "clear_skip"]:
                n += 1
                assert rule[a["tick"]]["regime"] == "clear"
                assert not rule[a["tick"]]["model_led"]
                sides = [c.get("side") for c in a["multi"]["compact"] if c.get("agent") == "diagnostician"]
                assert s["side"] not in sides                       # no call for it
                merges = [c for c in a["multi"]["compact"] if c.get("agent") == "merge"]
                assert all(s["side"] not in m["order"] for m in merges)   # and no stale re-use
    assert n > 0


def test_clear_skip_saves_calls_and_shadow_changes_nothing(skip_runs):
    for ep in ("dev_B01_tube_leak", "dev_D01_high_cv_coal"):
        off, sh, on = (skip_runs[(ep, m)] for m in ("off", "shadow", "on"))
        assert published(sh) == published(off)
        assert sh["diag_calls"] == off["diag_calls"]
        assert len(records(sh, "bev", "clear_skip")) > 0                 # would-skips logged
        assert on["diag_calls"] < off["diag_calls"]
        assert on["multi"]["bev"]["per_idea"]["clear_skip"]["used"] == len(records(on, "bev", "clear_skip"))


# -------------------------------------------------- commit 5: explain
class LastOptionBev(MockBackend):
    """bev picks the LAST option of every choice and says yes to every
    yes/no; everything else is the plain mock."""

    def generate(self, prompt, role="generic", max_tokens=512, mock_hint=None):
        if role != "decider" or "bev" not in (mock_hint or {}):
            return super().generate(prompt, role, max_tokens, mock_hint)
        ans = {}
        for qid, q in mock_hint["bev"].items():
            if q["type"] == "noul":
                ans[qid] = {"type": "noul", "noul": 0.9}
            else:
                k = q["options"]
                ans[qid] = {"type": "choice", "choice": k[-1],
                            "probabilities": {o: (0.8 if o == k[-1] else 0.2 / max(1, len(k) - 1)) for o in k}}
        return LLMReply(text=json.dumps({"answers": ans}), backend="mock", model="mock-0",
                        prefill_tokens=None, decode_tokens=0)


class DownBev(MockBackend):
    """bev-decide unreachable; Llama and Gemma answer as the plain mock."""

    def generate(self, prompt, role="generic", max_tokens=512, mock_hint=None):
        if role == "decider":
            return LLMReply(text="", status="error", error="connection: refused", backend="mock",
                            model="mock-0", prefill_tokens=None, decode_tokens=None)
        return super().generate(prompt, role, max_tokens, mock_hint)


register_backend("mock_lastbev", LastOptionBev)
register_backend("mock_downbev", DownBev)
EXPLAIN_EP = "dev_A01_fcv_seize"     # sides show several facts (B01 shows one)


@pytest.fixture(scope="module")
def explain_runs():
    if not (DEV / EXPLAIN_EP).exists():
        pytest.skip("dev episodes not generated")
    return {m: run(cfg_with(explain=m), EXPLAIN_EP) for m in ("off", "shadow", "on")} | {
        "last": run(cfg_with(explain="on", backend="mock_lastbev"), EXPLAIN_EP),
        "down": run(cfg_with(explain="on", backend="mock_downbev"), EXPLAIN_EP)}


def test_explain_shadow_publishes_exactly_off_and_logs_bevs_picks(explain_runs):
    off, sh = explain_runs["off"], explain_runs["shadow"]
    assert published(sh) == published(off) and sh["diag_calls"] == off["diag_calls"]
    recs = records(sh, "bev", "explain")
    assert len(recs) == sh["diag_calls"] and all(r["status"] == "ok" and "cite_agreement" in r for r in recs)


def test_explain_on_asks_llama_for_the_ranking_only(explain_runs):
    envs = [e for a in explain_runs["on"]["assessments"] for e in a["envelopes"]
            if e["agent"] == "diagnostician"]
    assert envs
    for e in envs:
        assert '{"r":[<case line>,...]}' in e["prompt"] and '"sep"' not in e["prompt"]
        assert set(json.loads(e["raw_reply"])) == {"r"}


def test_explain_on_publishes_bevs_citations_through_the_gate(explain_runs):
    from bench.evaluator import evaluate
    r = explain_runs["last"]
    n = 0
    for a in r["assessments"]:
        comp = a["multi"]["compact"]
        for rec in [c for c in comp if c.get("idea") == "explain" and c.get("answers")]:
            expanded = [c for c in comp if c.get("agent") == "diagnostician"
                        and c.get("side") == rec["side"]]
            assert expanded and expanded[0]["answer"] == rec["composed"]   # the gate expanded the rebuilt answer
            for line, cites in rec["composed"]["r"]:
                if f"cite{line}" in rec["answers"]:
                    n += 1
                    assert cites == [int(rec["answers"][f"cite{line}"]["ranking"][0])]
    assert n > 10
    # bev's citations are shown lines, so faithfulness does not fall below
    # the plain run's (A01 is 0.99 there already: the evaluator's own scoring)
    t3 = lambda x: evaluate(x)["T3_faithfulness"]["faithfulness"]     # noqa: E731
    assert t3(r) >= t3(explain_runs["off"])


def test_explain_with_bev_down_keeps_the_ranking_without_citations(explain_runs):
    r = explain_runs["down"]
    recs = records(r, "bev", "explain")
    assert recs and all(x["status"] == "error" for x in recs)
    assert all(all(c == [] for _, c in x["composed"]["r"]) and x["composed"]["sep"] is None
               for x in recs)
    assert published(r) and r["multi"]["bev"]["per_idea"]["explain"]["failed"] == len(recs)


def test_explain_on_decodes_less_on_the_mock_plumbing_only(explain_runs):
    dec = lambda run_: sum((e.get("tokens") or {}).get("decode") or 0          # noqa: E731
                           for a in run_["assessments"] for e in a["envelopes"]
                           if e["agent"] == "diagnostician")
    assert dec(explain_runs["on"]) < dec(explain_runs["off"])   # mock counts: len(text)//4


def test_rank_only_grammar_accepts_rankings_and_nothing_else():
    from fieldmind.multi import grammar
    g = grammar.rank_only(4)
    for ok in ('{"r":[]}', '{"r":[2]}', '{"r":[2,1,4]}'):
        assert grammar.accepts(g, ok), ok
    for bad in ('{"r":[2,2]}', '{"r":[5]}', '{"r":[1,2,3,4]}', '{"r":[[1,[1]]]}', '{"r":[1],"sep":1}'):
        assert not grammar.accepts(g, bad), bad


# ---------------------------------------------------- commit 6: first
FIRST_EP = "dev_D01_high_cv_coal"


@pytest.fixture(scope="module")
def first_runs():
    if not (DEV / FIRST_EP).exists():
        pytest.skip("dev episodes not generated")

    def c(mode, t=None):
        cfg = cfg_with(first=mode)
        cfg["multi"]["bev"]["first_threshold"] = t
        return cfg
    # mock bev: first option highest; top probability 0.5 with 3 options, 1/1 with 2..
    return {"off": run(c("off"), FIRST_EP), "shadow": run(c("shadow"), FIRST_EP),
            "on": run(c("on", 0.4), FIRST_EP), "never": run(c("on", 1.01), FIRST_EP)}


def test_first_asks_only_on_weak_or_tied_ticks_and_shadow_changes_nothing(first_runs):
    off, sh = first_runs["off"], first_runs["shadow"]
    assert published(sh) == published(off) and sh["diag_calls"] == off["diag_calls"]
    recs = records(sh, "bev", "first")
    assert recs
    rule = _rule(sh)
    assert all(r["regime"] in ("weak", "tie") for r in recs)
    assert all(rule[r["evidence_tick"]]["regime"] == r["regime"] for r in recs)
    assert all("agree_top" in r for r in recs if r.get("p_top") is not None)


def test_first_below_threshold_never_replaces_llama(first_runs):
    never = first_runs["never"]
    assert published(never) == published(first_runs["off"])
    assert never["diag_calls"] == first_runs["off"]["diag_calls"]
    assert not any(r.get("replaced_llama") for r in records(never, "bev", "first"))


def test_first_on_replaces_the_call_and_leads_with_bevs_pick(first_runs):
    on, off = first_runs["on"], first_runs["off"]
    assert on["diag_calls"] < off["diag_calls"]
    flat = {"RCA-09", "RCA-10", "RCA-15"}
    led = 0
    for a in on["assessments"]:
        comp = a["multi"]["compact"]
        rule = [c for c in comp if c.get("agent") == "rule"]
        for rec in [c for c in comp if c.get("idea") == "first" and c.get("replaced_llama")]:
            stand_in = [e for e in a["envelopes"] if e["agent"] == "diagnostician" and e["backend"] == "bev"]
            assert stand_in and all(not e["calls"] for e in stand_in)        # no Llama call
            bev_top = rec["answers"]["root"]["ranking"][0]
            if rule and rule[0]["model_led"] and bev_top not in flat and len(stand_in) == 1:
                led += 1
                assert a["hypotheses"][0]["case_ref"] == bev_top
    assert led > 0


# ------------------------------------------- commit 7: actions, unknown
class NayBev(MockBackend):
    """bev says no to every yes/no (0.1) and puts NONE first in every choice
    that offers it: the harshest case for the action and unknown rules."""

    def generate(self, prompt, role="generic", max_tokens=512, mock_hint=None):
        if role != "decider" or "bev" not in (mock_hint or {}):
            return super().generate(prompt, role, max_tokens, mock_hint)
        ans = {}
        for qid, q in mock_hint["bev"].items():
            if q["type"] == "noul":
                ans[qid] = {"type": "noul", "noul": 0.1}
            else:
                k = q["options"]
                top = "NONE" if "NONE" in k else k[0]
                ans[qid] = {"type": "choice", "choice": top,
                            "probabilities": {o: (0.7 if o == top else 0.3 / max(1, len(k) - 1)) for o in k}}
        return LLMReply(text=json.dumps({"answers": ans}), backend="mock", model="mock-0",
                        prefill_tokens=None, decode_tokens=0)


register_backend("mock_naybev", NayBev)
ACT_EP = "dev_A01_fcv_seize"


def _catalogue():
    from fieldmind.agent.l6_gate import ActionCatalogue
    return ActionCatalogue(ROOT / "data/kb/action_catalogue.json")


@pytest.fixture(scope="module")
def act_runs():
    if not (DEV / ACT_EP).exists():
        pytest.skip("dev episodes not generated")
    return {"off": run(cfg_with(), ACT_EP),
            "shadow": run(cfg_with(actions="shadow", unknown="shadow", backend="mock_naybev"), ACT_EP),
            "on": run(cfg_with(actions="on", unknown="on", backend="mock_naybev"), ACT_EP)}


def test_actions_and_unknown_shadow_change_nothing_published(act_runs):
    sh = act_runs["shadow"]
    assert published(sh) == published(act_runs["off"])
    assert records(sh, "bev", "actions") and records(sh, "bev", "unknown")
    assert not any("bev_flags" in a["multi"] for a in sh["assessments"])


def test_protected_actions_are_never_asked_about_nor_dropped(act_runs):
    from fieldmind.multi.agents.bev import protected
    from fieldmind.agent.l6_gate import Action
    cat = _catalogue()
    for rec in records(act_runs["on"], "bev", "actions"):
        for q in rec["about"]:
            e = cat.lookup(q[4:])
            assert e and not protected(Action(id=e["id"], text=e["text"], urgency=e["urgency"],
                                              source="catalogue"), e), q
    dropped_any = False
    for a_off, a_on in zip(act_runs["off"]["assessments"], act_runs["on"]["assessments"]):
        off_ids = [x["id"] for x in a_off["actions"]]
        on_ids = [x["id"] for x in a_on["actions"]]
        assert set(on_ids) <= set(off_ids) and a_on["escalate"] == a_off["escalate"]
        for gone in set(off_ids) - set(on_ids):
            dropped_any = True
            e = cat.lookup(gone)
            assert e["urgency"] != "NOW" and e["category"] not in ("ESCALATION", "MITIGATION")
        for x in a_off["actions"]:
            if x["urgency"] == "NOW":
                assert x["id"] in on_ids
    assert dropped_any


def test_finalize_keeps_a_protected_action_even_when_told_to_drop_it():
    from fieldmind.multi.agents.bev import protected
    cat = _catalogue()
    now = [a for a in cat.all if a["urgency"] == "NOW"][0]
    soon = [a for a in cat.all if a["urgency"] != "NOW"
            and a["category"] not in ("ESCALATION", "MITIGATION")][0]
    from fieldmind.agent.l6_gate import Action
    mk = lambda e: Action(id=e["id"], text=e["text"], urgency=e["urgency"], source="catalogue")  # noqa: E731
    assert protected(mk(now), now) and not protected(mk(soon), soon)
    assert protected(mk(soon), None)                      # unknown to the catalogue: kept


def test_unknown_flags_without_touching_the_ranking(act_runs):
    on, off = act_runs["on"], act_runs["off"]
    assert [p[0] for p in published(on)] == [p[0] for p in published(off)]
    flags = [a["multi"]["bev_flags"] for a in on["assessments"] if "bev_flags" in a["multi"]]
    assert flags and all(f["unknown_fault"] and f["p_none"] >= 0.5 for f in flags)


def test_unknown_flag_stays_down_when_none_is_unlikely():
    if not (DEV / ACT_EP).exists():
        pytest.skip("dev episodes not generated")
    r = run(cfg_with(unknown="on"), ACT_EP)       # plain mock: NONE is the last option, lowest
    flags = [a["multi"]["bev_flags"] for a in r["assessments"] if "bev_flags" in a["multi"]]
    assert flags and all(not f["unknown_fault"] and f["p_none"] < 0.5 for f in flags)


# ------------------------------------------------- commit 8: verifier
VER_EP = "dev_A03_bfp_suction"     # verifier runs and ticks have several facts (mock)


@pytest.fixture(scope="module")
def ver_runs():
    if not (DEV / VER_EP).exists():
        pytest.skip("dev episodes not generated")
    return {"off": run(cfg_with(), VER_EP),
            "shadow": run(cfg_with(verifier="shadow"), VER_EP),
            "nay": run(cfg_with(verifier="on", backend="mock_naybev"), VER_EP)}


def test_bev_verifier_shadow_changes_nothing_and_logs_agreement(ver_runs):
    sh, off = ver_runs["shadow"], ver_runs["off"]
    assert published(sh) == published(off)
    assert [a["unexplained"] for a in sh["assessments"]] == [a["unexplained"] for a in off["assessments"]]
    recs = records(sh, "bev", "verifier")
    claim_recs = [r for r in recs if any(k.startswith("claim") for k in (r.get("answers") or {}))]
    assert claim_recs and all("agree" in r for r in claim_recs)


def test_bev_verifier_on_replaces_gemma_and_its_fails_reach_the_claims(ver_runs):
    nay = ver_runs["nay"]
    gemma_calls = [e for a in nay["assessments"] for e in a["envelopes"]
                   if e["agent"] == "verifier" and e["calls"]]
    assert gemma_calls == []                                     # Gemma never called
    n = nc = 0
    for a in nay["assessments"]:
        verdicts = [c for c in a["multi"]["compact"] if c.get("idea") == "verifier" and c.get("verdict")]
        if not verdicts:
            continue
        n += 1
        assert all(v == "f" for _, v in verdicts[0]["verdict"]["v"])   # bev said no to every claim
        contra = [c for c in a["multi"]["compact"] if c.get("idea") == "verifier"
                  and "contra" in (c.get("answers") or {})]
        if contra:                                                    # the contradiction is bev's pick
            nc += 1
            assert verdicts[0]["verdict"]["c"] == int(contra[0]["answers"]["contra"]["ranking"][0])
        else:
            assert verdicts[0]["verdict"]["c"] is None
        shown = a["hypotheses"][:3]
        assert any(h.get("verifier") == "failed check" for h in shown)
        if contra:
            assert any(u.startswith("verifier contradiction") for u in a["unexplained"])
    assert n > 0 and nc > 0
