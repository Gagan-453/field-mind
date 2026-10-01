"""The pre-registered ranking statistic (bench/model_choice.py) on a synthetic run
whose answer is worked out by hand below, plus the verdict rule's boundaries."""
from __future__ import annotations

from bench.model_choice import ranking_question, verdict

FACTS = [{"id": "F1"}, {"id": "F2"}]


def _tick(t, model, brk, status="ok", cites=("F1",), shown=None):
    env = {"agent": "diagnostician", "status": status, "cited_facts": list(cites),
           "payload": {"hypotheses": [model]} if model else {}}
    return {"tick": t, "facts": FACTS, "envelopes": [env],
            "hypotheses": [{"case_ref": shown or (model or {}).get("case_ref"),
                            "confidence": 0.6}],
            "belief_ranking": [{"case_ref": c, "cause": f"cause {c}", "log_odds": lo}
                               for c, lo in brk]}


def _run(target="RCA-01", ep="ep_x"):
    m = lambda c: {"cause": f"model says {c}", "case_ref": c}          # noqa: E731
    ticks = [
        _tick(5, m("RCA-11"), [("RCA-01", 2.0)]),                       # pre-onset: out
        _tick(30, m("RCA-11"), [("RCA-01", 2.0), ("RCA-11", 1.0)]),     # counted: B 1, M 0
        _tick(31, m("RCA-16"), [("RCA-01", 2.0)]),                      # same group: out
        _tick(32, m("RCA-14"), [("RCA-01", 3.0), ("RCA-11", 3.0)]),     # tie: B 0.5, M 0
        _tick(33, m("RCA-11"), [("RCA-01", 2.0)], status="invalid_schema"),   # out
        _tick(34, m("RCA-11"), [("RCA-01", 2.0)], cites=("F9",)),       # gate drops order: out
        _tick(35, {"cause": "something new"}, [("RCA-11", 1.0)]),       # model-only: B 0, M 0
        _tick(36, {"cause": "cause RCA-01"}, [("RCA-11", 1.0), ("RCA-01", 0.5)]),
        #  ^ resolved by cause to RCA-01 (as _merge does): M 1, B 0
    ]
    return {"episode_id": ep, "assessments": ticks,
            "ground_truth": {"family": "A", "root_cause_id": target, "fault_onset_t": 900}}


def test_population_and_scoring_worked_by_hand():
    r = ranking_question([_run()])["pooled"]
    assert r["n"] == 4
    assert r["model_only"] == 1
    assert r["p_belief"] == round((1 + 0.5 + 0 + 0) / 4, 3)
    assert r["p_model"] == round((0 + 0 + 0 + 1) / 4, 3)


def test_heldout_and_normal_episodes_are_excluded():
    runs = [_run(target="RCA-06", ep="held"), _run(ep="lib")]
    runs.append({"episode_id": "n", "assessments": _run()["assessments"],
                 "ground_truth": {"family": "N", "root_cause_id": "NONE"}})
    out = ranking_question(runs)
    assert out["pooled"]["n"] == 4 and set(out["per_episode"]) == {"lib"}


def test_shown_variant_reads_the_shown_rank1_not_the_envelope():
    run = _run()
    for a in run["assessments"]:
        a["hypotheses"][0]["case_ref"] = "RCA-01"     # display always shows the truth
    r = ranking_question([run], use_shown=True)["pooled"]
    # the shown variant needs no ok envelope; it disagrees only where belief's
    # leader is RCA-11 (ticks 35, 36), and there the shown RCA-01 is right
    assert (r["n"], r["p_model"], r["p_belief"]) == (2, 1.0, 0.0)
    r = ranking_question([run])["pooled"]
    assert r["n"] == 4                                # the model's own rank-1 is unchanged


def _res(n, pb, pm, eps):
    return {"pooled": {"n": n, "p_belief": pb, "p_model": pm},
            "per_episode": {f"e{i}": {"n": en, "p_belief": b, "p_model": m}
                            for i, (en, b, m) in enumerate(eps)}}


def test_verdict_rule_boundaries():
    assert verdict(_res(29, 0.9, 0.1, [])).startswith("INCONCLUSIVE")
    assert verdict(_res(30, 0.50, 0.40, [(15, 0.5, 0.4)])) == "BELIEF_DECIDES"
    assert verdict(_res(30, 0.40, 0.50, [(15, 0.4, 0.5)])) == "MODEL_DECIDES"
    assert verdict(_res(30, 0.49, 0.40, [])) == "INCONCLUSIVE"                  # margin < 0.10
    # one qualifying episode disagrees -> inconclusive
    assert verdict(_res(60, 0.6, 0.4, [(30, 0.8, 0.2), (12, 0.3, 0.5)])) == "INCONCLUSIVE"
    # an episode under 10 ticks does not join the consistency clause
    assert verdict(_res(60, 0.6, 0.4, [(30, 0.8, 0.2), (9, 0.3, 0.5)])) == "BELIEF_DECIDES"
