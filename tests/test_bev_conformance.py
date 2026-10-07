"""bench/bev_conformance.py: requests come from dev episodes and are exactly what
the decider sends; compare's token check fails when it should and every rank-1
disagreement is listed. A fake board (a function standing in for the HTTP post)
replaces bev-decide."""
import json
from pathlib import Path

import pytest

from bench import bev_conformance as bc

DEV = Path(__file__).resolve().parent.parent / "data" / "episodes_dev"


@pytest.mark.skipif(not (DEV / "dev_A01_fcv_seize").exists(), reason="dev episodes not generated")
def test_requests_are_dev_decider_requests():
    items = bc.build_requests(n=4, episodes=["dev_A01_fcv_seize"])
    assert 1 <= len(items) <= 4
    for it in items:
        assert it["id"].startswith("dev_A01_fcv_seize@t")
        q = it["request"]["questions"]["root_cause"]
        assert q["type"] == "choice" and 2 <= len(q["criteria"]) <= 6
        assert set(it["request"]) == {"state", "questions"}


def test_the_quick_set_is_dev_only():
    assert all(e.startswith("dev_") for e in bc.EPISODES)


def test_reversed_options_reverses_criteria_only():
    req = {"state": "s", "questions": {"q": {"type": "choice", "instructions": "i",
                                             "criteria": {"A": "a", "B": "b", "C": "c"}}}}
    r = bc.reversed_options(req)
    assert list(r["questions"]["q"]["criteria"]) == ["C", "B", "A"]
    assert list(req["questions"]["q"]["criteria"]) == ["A", "B", "C"]      # input untouched
    assert r["state"] == "s" and r["questions"]["q"]["instructions"] == "i"


REQ = {"state": "s", "questions": {"q": {"type": "choice", "instructions": "i",
                                         "criteria": {"A": "a", "B": "b", "C": "c"}}}}
IDS = [1, 2, 3, 10, 11, 20, 21, 30, 31, 40]
REF = [{"id": "x", "request": REQ, "input_ids": {"q": IDS},
        "answers": {"q": {"type": "choice", "choice": "A",
                          "probabilities": {"A": 0.6, "B": 0.3, "C": 0.1}}}}]


def _board(probs, ids=IDS, rev_probs=None):
    def post(url, body):
        p = probs if list(body["questions"]["q"]["criteria"]) == ["A", "B", "C"] else (rev_probs or probs)
        out = {"answers": {"q": {"type": "choice", "choice": max(p, key=p.get), "probabilities": p}},
               "latency_ms": 12.0, "usage": {"prompt_tokens": len(ids)}}
        if body.get("debug"):
            out["token_ids"] = {"q": {"prompt": ids[:3], "options": [ids[3:5], ids[5:7], ids[7:9]],
                                      "answer": ids[9:]}}
        return out
    return post


def test_an_identical_board_passes():
    res = bc.compare("u", REF, post=_board({"A": 0.6, "B": 0.3, "C": 0.1}))
    assert res["pass_tokens"] and res["rank1_disagreements"] == []
    assert res["max_abs_dp"] == 0 and res["shuffle_max_abs_dp"] == 0
    assert res["tokens_identical"] == res["n_questions"] == 1


def test_different_token_ids_fail():
    res = bc.compare("u", REF, post=_board({"A": 0.6, "B": 0.3, "C": 0.1}, ids=IDS[:-1] + [99]))
    assert not res["pass_tokens"]


def test_a_flipped_top_is_listed_however_large_the_drift():
    """A broken port drifts a lot; that must not hide its rank-1 flip (the first
    version of compare let it, by calling nothing decisive past the drift)."""
    res = bc.compare("u", REF, post=_board({"A": 0.25, "B": 0.65, "C": 0.1}))
    assert res["rank1_disagreements"] == [{"id": "x", "question": "q", "board": "B",
                                           "reference": "A", "reference_margin": 0.3}]
    assert res["max_abs_dp"] == pytest.approx(0.35)


def test_small_drift_passes_and_is_reported():
    res = bc.compare("u", REF, post=_board({"A": 0.598, "B": 0.302, "C": 0.1},
                                           rev_probs={"A": 0.597, "B": 0.303, "C": 0.1}))
    assert res["pass_tokens"] and res["rank1_disagreements"] == []
    assert res["max_abs_dp"] == pytest.approx(0.002)
    assert res["shuffle_max_abs_dp"] == pytest.approx(0.001)
