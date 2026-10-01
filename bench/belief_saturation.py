"""
Belief saturation report (Session 1b, step 4). Read-only: reads a runs_*.json,
changes nothing. Mock-backend numbers; not agent results.

Definitions follow the Phase 0a Check 1 table (reports/phase0a_single_agent_fixes.md):
  scored tick  = post-onset tick with a non-empty hypothesis list (fault episodes
                 whose true cause is a library case / a held-out case), or, for
                 no-fault episodes, every tick with a non-empty belief ranking
  at clamp     = belief rank-1 log-odds >= world_model.CLAMP (+4.0, conf 0.982)
  tie          = belief rank-1 and rank-2 have exactly equal log-odds
  shown conf   = hypotheses[0].confidence (what the engineer sees)
  confident-and-wrong-group = shown conf > 0.5 and the shown rank-1 case is not in
                 the true case's group (fault classes only)

Usage: .venv/bin/python -m bench.belief_saturation results/dev/runs_mock_dev_before.json \
           [--trajectory dev_N03_normal,dev_N09_normal]
"""
from __future__ import annotations

import argparse
import json
import statistics

from bench.evaluator import _groups
from fieldmind.agent.world_model import CLAMP

CONF = 0.5


def classify(gt: dict, held_ids) -> str | None:
    if gt["family"] == "N":
        return "no-fault"
    t = gt["root_cause_id"]
    if t in (None, "NONE"):
        return None                      # fault with no case: not scored
    return "held-out" if t in held_ids else "library"


def scored_ticks(run: dict, cls: str):
    onset = run["ground_truth"].get("fault_onset_t") or 0
    for a in run["assessments"]:
        if cls == "no-fault":
            if a.get("belief_ranking"):
                yield a
        elif a["tick"] * 30.0 >= onset and a["hypotheses"] and a.get("belief_ranking"):
            yield a


def summarise(runs: list[dict]) -> dict:
    gmap, held, held_ids = _groups()
    acc: dict[str, dict] = {}
    for run in runs:
        gt = run["ground_truth"]
        cls = classify(gt, held_ids)
        if cls is None:
            continue
        target = gt["root_cause_id"]
        tgroup = (held.get(target) if cls == "held-out" else gmap.get(target, target))
        d = acc.setdefault(cls, {"n": 0, "clamp1": 0, "ties": 0, "ties_clamp": 0,
                                 "conf": [], "cw": 0})
        for a in scored_ticks(run, cls):
            brk = a["belief_ranking"]
            d["n"] += 1
            top = brk[0]["log_odds"]
            d["clamp1"] += top >= CLAMP - 1e-9
            if len(brk) > 1 and top == brk[1]["log_odds"]:
                d["ties"] += 1
                d["ties_clamp"] += top >= CLAMP - 1e-9
            if a["hypotheses"]:
                h = a["hypotheses"][0]
                c = h.get("confidence", 0.0)
                d["conf"].append(c)
                if cls != "no-fault" and c > CONF:
                    d["cw"] += gmap.get(h.get("case_ref")) != tgroup
    out = {}
    for cls, d in acc.items():
        n, cf = d["n"], d["conf"]
        dec = [0] * 10
        for c in cf:
            dec[min(9, int(c * 10))] += 1
        out[cls] = {
            "ticks": n,
            "rank1_at_clamp": d["clamp1"], "rank1_at_clamp_share": round(d["clamp1"] / n, 3),
            "ties": d["ties"], "tie_share": round(d["ties"] / n, 3),
            "ties_at_clamp": d["ties_clamp"],
            "ties_at_clamp_share_of_ties": round(d["ties_clamp"] / d["ties"], 3) if d["ties"] else None,
            "shown_conf_mean": round(statistics.mean(cf), 3) if cf else None,
            "shown_conf_median": round(statistics.median(cf), 3) if cf else None,
            "shown_conf_ge_0.9_share": round(sum(c >= 0.9 for c in cf) / len(cf), 3) if cf else None,
            "shown_conf_deciles": dec,
            "confident_and_wrong_group": d["cw"],
            "confident_and_wrong_group_share": round(d["cw"] / n, 3) if cls != "no-fault" else None,
        }
    return out


def trajectories(runs: list[dict], ids: list[str]) -> dict:
    out = {}
    for run in runs:
        if run["episode_id"] not in ids:
            continue
        rows = []
        for a in run["assessments"]:
            brk = a.get("belief_ranking") or []
            if brk and a["hypotheses"]:
                rows.append((a["tick"], brk[0]["case_ref"], brk[0]["log_odds"],
                             a["hypotheses"][0].get("confidence")))
        out[run["episode_id"]] = rows
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs")
    ap.add_argument("--trajectory", default="")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    runs = json.load(open(args.runs))
    s = summarise(runs)
    keys = ["ticks", "rank1_at_clamp", "rank1_at_clamp_share", "ties", "tie_share",
            "ties_at_clamp", "ties_at_clamp_share_of_ties", "shown_conf_mean",
            "shown_conf_median", "shown_conf_ge_0.9_share", "confident_and_wrong_group",
            "confident_and_wrong_group_share"]
    cls = [c for c in ("library", "held-out", "no-fault") if c in s]
    print(f"{'':36s}" + "".join(f"{c:>12s}" for c in cls))
    for k in keys:
        print(f"{k:36s}" + "".join(f"{str(s[c][k]):>12s}" for c in cls))
    print(f"{'shown conf deciles 0.0-1.0':36s}")
    for c in cls:
        print(f"  {c:10s} {s[c]['shown_conf_deciles']}")
    if args.trajectory:
        for ep, rows in trajectories(runs, args.trajectory.split(",")).items():
            print(f"\n{ep}: tick, belief rank-1, log-odds, shown conf")
            for r in rows:
                print(f"  t{r[0]:<4d} {r[1]:8s} {r[2]:+.3f}  {r[3]:.3f}")
    if args.json:
        json.dump(s, open(args.json, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
