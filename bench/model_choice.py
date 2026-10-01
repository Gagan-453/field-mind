"""
Phase 0b model-choice table and the ranking question. Read-only: reads runs_*.json
files written by run_demo.py, changes nothing.

  .venv/bin/python -m bench.model_choice results/phase0b/runs_mock_dev3.json \
        results/phase0b/runs_llamaserver_dev3_<model>.json [--json out.json]

One column per runs file. Rows: library top-1 / group / sep_named, Q3 (after the
gate) and raw model citation faithfulness, broken-JSON rates, envelope status
counts, ECE (group) and confident-and-wrong in BOTH confidence views (decision
and shown), low-confidence share in both views, Q1 / Q4 / S4, prompt and answer
tokens, diagnosis latency, chip temperature, and the ranking statistic.

RANKING QUESTION (pre-registered in reports/phase0b_lanes_model_choice.md before
any real-model run). Population: post-onset LIBRARY ticks with a non-empty
belief ranking where the diagnostician envelope is ok and the gate kept its order
(raw citation faithfulness >= min_faithfulness), and where the model's own rank-1
group is NOT the group of any case in belief's tied top set. Scoring: model
correct = its rank-1 case is in the true group (a model-only idea with no case is
incorrect); belief correct is tie-fair = share of the tied top set in the true
group. Rule: n < 30 -> INCONCLUSIVE; p_belief - p_model >= 0.10 and belief >= model
in every episode with >= 10 such ticks -> BELIEF_DECIDES; the mirror image ->
MODEL_DECIDES; anything else -> INCONCLUSIVE (status quo kept).
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from bench.belief_saturation import summarise as saturation
from bench.evaluator import _groups, aggregate, evaluate

MIN_FAITH = 0.5          # configs/base.yaml agent.min_faithfulness (the gate's rule)
RULE_MARGIN = 0.10       # pre-registered decision constant (design choice)
RULE_MIN_N = 30          # pre-registered
RULE_EP_MIN = 10         # an episode joins the consistency clause at >= 10 ticks


def _diag_env(a: dict) -> dict | None:
    for e in a.get("envelopes", []) or []:
        if e.get("agent") == "diagnostician":
            return e
    return None


def _raw_faith(env: dict, fact_ids: set) -> float:
    cited = env.get("cited_facts") or []
    return sum(c in fact_ids for c in cited) / len(cited) if cited else 1.0


def model_rank1_case(env: dict, brk: list[dict], gmap: dict) -> str | None:
    """The model's own rank-1, resolved the way orchestrator._merge resolves it:
    by cause against the deterministic hypotheses first, then by case_ref.
    None = a model-only idea with no case."""
    hyps = (env.get("payload") or {}).get("hypotheses") or []
    if not hyps:
        return None
    h = hyps[0]
    by_cause = {b.get("cause"): b.get("case_ref") for b in brk}
    if h.get("cause") in by_cause and by_cause[h.get("cause")]:
        return by_cause[h.get("cause")]
    ref = h.get("case_ref")
    return ref if ref in gmap else None


def ranking_question(runs: list[dict], use_shown: bool = False) -> dict:
    """use_shown=True replaces the model's own rank-1 with the SHOWN rank-1
    (hypotheses[0]), which is the population definition the mock prior used."""
    gmap, held, held_ids = _groups()
    per_ep, pooled = {}, {"n": 0, "belief": 0.0, "model": 0.0, "model_only": 0}
    for run in runs:
        gt = run["ground_truth"]
        target = gt.get("root_cause_id")
        if gt.get("family") == "N" or target in (None, "NONE") or target in held_ids:
            continue
        tgroup = gmap.get(target, target)
        onset = gt.get("fault_onset_t") or 0
        d = {"n": 0, "belief": 0.0, "model": 0.0, "model_only": 0}
        for a in run["assessments"]:
            brk = a.get("belief_ranking") or []
            if a["tick"] * 30.0 < onset or not brk or not a["hypotheses"]:
                continue
            if use_shown:
                m = a["hypotheses"][0].get("case_ref")
                m = m if m in gmap else None
            else:
                env = _diag_env(a)
                if env is None or env.get("status") != "ok":
                    continue
                if _raw_faith(env, {f["id"] for f in a["facts"]}) < MIN_FAITH:
                    continue
                m = model_rank1_case(env, brk, gmap)
            top = [b for b in brk if b["log_odds"] == brk[0]["log_odds"]]
            top_groups = {gmap.get(b.get("case_ref")) for b in top}
            mg = gmap.get(m) if m else None
            if m is not None and mg in top_groups:
                continue                                   # agrees with a leader
            d["n"] += 1
            d["model_only"] += m is None
            d["model"] += (mg == tgroup) if m is not None else 0.0
            d["belief"] += sum(gmap.get(b.get("case_ref")) == tgroup for b in top) / len(top)
        per_ep[run["episode_id"]] = d
        for k in pooled:
            pooled[k] += d[k]

    def rates(d):
        n = d["n"]
        return {"n": n, "model_only": d["model_only"],
                "p_belief": round(d["belief"] / n, 3) if n else None,
                "p_model": round(d["model"] / n, 3) if n else None}
    out = {"pooled": rates(pooled), "per_episode": {e: rates(d) for e, d in per_ep.items()}}
    out["verdict"] = verdict(out)
    return out


def verdict(r: dict) -> str:
    p = r["pooled"]
    if p["n"] < RULE_MIN_N:
        return "INCONCLUSIVE (n < 30)"
    # rates are rounded to 3 d.p.; round the difference too, so an exact 0.10
    # margin is not lost to float error (0.50 - 0.40 = 0.0999...)
    diff = round(p["p_belief"] - p["p_model"], 3)
    eps = [e for e in r["per_episode"].values() if e["n"] >= RULE_EP_MIN]
    if diff >= RULE_MARGIN and all(e["p_belief"] >= e["p_model"] for e in eps):
        return "BELIEF_DECIDES"
    if -diff >= RULE_MARGIN and all(e["p_model"] >= e["p_belief"] for e in eps):
        return "MODEL_DECIDES"
    return "INCONCLUSIVE"


def call_stats(runs: list[dict]) -> dict:
    envs = [e for r in runs for a in r["assessments"] for e in a.get("envelopes", []) or []]
    diag = [e for e in envs if e.get("agent") == "diagnostician"]
    calls = sum(r.get("diag_calls", 0) for r in runs)
    first_fail = sum(round(r.get("parse_failure_rate", 0) * r.get("diag_calls", 0)) for r in runs)
    status = {}
    for e in envs:
        status[f"{e['agent']}:{e['status']}"] = status.get(f"{e['agent']}:{e['status']}", 0) + 1
    lat = sorted(e["latency_ms"] for e in diag if e.get("status") == "ok")
    raw_c = raw_v = 0
    for r in runs:
        for a in r["assessments"]:
            ids = {f["id"] for f in a["facts"]}
            for e in a.get("envelopes", []) or []:
                if e.get("agent") == "diagnostician" and e.get("status") == "ok":
                    raw_c += len(e.get("cited_facts") or [])
                    raw_v += sum(c in ids for c in e.get("cited_facts") or [])

    def mean(xs):
        return round(statistics.mean(xs), 1) if xs else None
    return {
        "diag_calls": calls,
        "broken_json_first_reply": round(first_fail / calls, 3) if calls else None,
        "broken_json_after_repair": (round(sum(e["status"] == "invalid_schema" for e in diag)
                                           / len(diag), 3) if diag else None),
        "envelope_status": status,
        "model_citation_faithfulness_raw": round(raw_v / raw_c, 3) if raw_c else None,
        "n_model_citations": raw_c,
        "prompt_tokens_mean": mean([e.get("prompt_tokens", 0) for e in diag]),
        "answer_tokens_mean": mean([e["tokens"]["decode"] for e in diag if e.get("status") == "ok"]),
        "diag_latency_ms_mean": mean(lat),
        "diag_latency_ms_p95": round(lat[int(0.95 * (len(lat) - 1))], 1) if lat else None,
        "models": sorted({e.get("model") for e in diag}),
        "lanes": sorted({e.get("backend") for e in diag}),
    }


def column(path: str) -> dict:
    runs = json.load(open(path))
    s = aggregate([evaluate(r) for r in runs])
    lib = s["Q2_library"]
    sat_d, sat_s = saturation(runs, decision=True), saturation(runs, decision=False)
    col = {
        "file": path, "n_episodes": len(runs),
        "library_top1": lib.get("top1"), "library_group_top1": lib.get("group_top1"),
        "library_sep_named": lib.get("sep_named"),
        "library_belief_top1_tiefair": lib.get("belief_top1_tiefair"),
        "library_belief_group": lib.get("belief_group"),
        "Q3_faithfulness_after_gate": s["Q3_faithfulness"],
        "Q1_macro_f1": s["Q1_macro_f1"], "Q4_precision": s["Q4_action_precision"],
        "Q4_recall": s["Q4_action_recall"], "S4_llm_invocation": s["S4_llm_invocation_rate"],
    }
    for view, sat in (("decision", sat_d), ("shown", sat_s)):
        L = sat.get("library", {})
        col[f"ece_group_{view}"] = L.get("ece_group")
        col[f"confident_wrong_{view}"] = L.get("confident_and_wrong_group")
        col[f"confident_wrong_share_{view}"] = L.get("confident_and_wrong_group_share")
        col[f"low_conf_share_{view}"] = L.get("low_conf_share")
    col["scored_library_ticks"] = sat_d.get("library", {}).get("ticks")
    col.update(call_stats(runs))
    col["chip_temp"] = {r["episode_id"]: [r.get("chip_temp_start"), r.get("chip_temp_end")]
                        for r in runs if "chip_temp_start" in r}
    col["ranking_model_rank1"] = ranking_question(runs)
    col["ranking_shown_rank1"] = ranking_question(runs, use_shown=True)
    return col


ROWS = ["n_episodes", "library_top1", "library_group_top1", "library_sep_named",
        "library_belief_top1_tiefair", "library_belief_group",
        "Q3_faithfulness_after_gate", "model_citation_faithfulness_raw", "n_model_citations",
        "diag_calls", "broken_json_first_reply", "broken_json_after_repair",
        "ece_group_decision", "ece_group_shown", "confident_wrong_decision",
        "confident_wrong_shown", "confident_wrong_share_decision", "confident_wrong_share_shown",
        "low_conf_share_decision", "low_conf_share_shown", "scored_library_ticks",
        "Q1_macro_f1", "Q4_precision", "Q4_recall", "S4_llm_invocation",
        "prompt_tokens_mean", "answer_tokens_mean", "diag_latency_ms_mean", "diag_latency_ms_p95"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    cols = [column(p) for p in args.runs]
    names = [Path(p).stem.replace("runs_", "") for p in args.runs]
    print(f"{'':34s}" + "".join(f"{n[:22]:>24s}" for n in names))
    for k in ROWS:
        print(f"{k:34s}" + "".join(f"{str(c.get(k)):>24s}" for c in cols))
    for n, c in zip(names, cols):
        print(f"\n[{n}] models={c['models']} lanes={c['lanes']} status={c['envelope_status']}")
        for key in ("ranking_model_rank1", "ranking_shown_rank1"):
            r = c[key]
            print(f"  {key}: pooled {r['pooled']}  verdict={r['verdict']}")
            for e, d in r["per_episode"].items():
                print(f"      {e:24s} {d}")
        if c["chip_temp"]:
            print(f"  chip temp [start, end]: {c['chip_temp']}")
    if args.json:
        json.dump(dict(zip(names, cols)), open(args.json, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
