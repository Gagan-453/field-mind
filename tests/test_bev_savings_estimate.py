"""bench/bev_savings_estimate.py: the answer surgery, the side pairing and the
call-or-skip replay, on hand-built runs whose outcomes are known."""

from bench.bev_savings_estimate import cut_to, side_of_envelopes, skip_replay, strip_citations


def _env(tick, case, prompt_tokens, decode=30):
    return {"agent": "diagnostician", "tick": tick, "status": "ok", "backend": "npu",
            "prompt_tokens": prompt_tokens, "tokens": {"prefill": prompt_tokens, "decode": decode},
            "calls": [{"decode_ms": decode * 60.0, "latency_ms": decode * 60.0 + 500}],
            "payload": {"hypotheses": [{"case_ref": case}]}}


def _tick(t, lead, envs, sides):
    res = [{"agent": f"diag_{s}", "evidence_tick": t, "prompt_tokens": e["prompt_tokens"] - 100}
           for e, s in zip(envs, sides)]
    return {"tick": t, "belief_ranking": [{"case_ref": lead}], "envelopes": envs,
            "multi": {"results": res}}


def _run(ticks, truth="RCA-01"):
    return {"episode_id": "ep_x", "ground_truth": {"root_cause_id": truth}, "assessments": ticks}


GMAP = {"RCA-01": "G1", "RCA-02": "G2", "RCA-03": "G3"}


def test_citations_are_removed_and_cases_kept():
    ans = {"r": [[2, [1, 3]], [1, [1]]], "sep": 2, "n": [], "x": []}
    assert strip_citations(ans)["r"] == [2, 1]
    assert ans["r"] == [[2, [1, 3]], [1, [1]]]          # input untouched
    assert cut_to({"r": [[1, []], [2, []], [3, []], [4, []]]}, 3)["r"] == [[1, []], [2, []], [3, []]]


def test_sides_are_paired_by_prompt_size_not_by_order():
    big, small = _env(5, "RCA-01", 700), _env(5, "RCA-03", 400)
    a = {"envelopes": [big, small],
         "multi": {"results": [{"agent": "diag_heat", "evidence_tick": 5, "prompt_tokens": 300},
                               {"agent": "diag_water", "evidence_tick": 5, "prompt_tokens": 600}]}}
    assert side_of_envelopes(a) == {0: "water", 1: "heat"}


def test_replay_counts_only_calls_where_last_answer_equals_belief_leader():
    run = _run([
        _tick(1, "RCA-01", [_env(1, "RCA-01", 500)], ["water"]),      # first call: never eligible
        _tick(2, "RCA-01", [_env(2, "RCA-01", 500)], ["water"]),      # eligible, same top
        _tick(3, "RCA-01", [_env(3, "RCA-02", 500)], ["water"]),      # eligible, moves out of truth
        _tick(4, "RCA-01", [_env(4, "RCA-01", 500)], ["water"]),      # last = RCA-02 != leader
        _tick(5, "RCA-03", [_env(5, "RCA-03", 500)], ["heat"]),       # heat's first call
    ])
    c, keys = skip_replay([run], GMAP, {})
    assert c["calls"] == 5
    assert c["eligible"] == 2
    assert c["eligible_same_top"] == 1
    assert c["changed_out_of_true_group"] == 1
    assert c.get("changed_into_true_group", 0) == 0
    assert c["decode_tokens_eligible"] == 60
    assert keys == {("ep_x", 2, 500), ("ep_x", 3, 500)}


def test_replay_keeps_sides_apart():
    # Water's last answer must not make a heat call eligible.
    run = _run([
        _tick(1, "RCA-01", [_env(1, "RCA-01", 500)], ["water"]),
        _tick(2, "RCA-01", [_env(2, "RCA-01", 500)], ["heat"]),
    ])
    c, _ = skip_replay([run], GMAP, {})
    assert c.get("eligible", 0) == 0
