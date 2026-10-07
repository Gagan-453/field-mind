#!/usr/bin/env python3
"""
Did the multi-agent beat belief alone? Reads one or more benchmark test folders
(results/benchmarks/<name>/) and prints, per scored episode, the published
group top-1 against belief alone (both from bench/evaluator.py via the saved
summaries), then the mean and the verdict of the pre-registered rule
(reports/multi_accuracy_fix.md, "Board check"):

  PASS when the mean published group top-1 over the scored episodes is above
  the mean belief group top-1, AND no episode is more than 0.05 below its belief.

    .venv/bin/python bench/beats_belief.py results/benchmarks/dev_quick_guarded [...]

With --replay it also replays every saved multi-agent run under each merge
rule (the model's answers are the same under every rule; see the report), so
one board run shows all rules side by side. Mock folders are refused.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from bench import replay_multi as rm

MARGIN = 0.05


def folder(d: Path, replay: bool):
    rows = []
    for s in sorted(d.glob("*_multi*.summary.json")):
        if ".REJECTED" in s.name:
            continue
        doc = json.loads(s.read_text())
        if "MOCK" in str(doc.get("meta", {}).get("where", "")):
            raise SystemExit(f"{d}: mock run, not an agent result")
        t2 = doc["evaluation"]["T2_root_cause"]
        if not t2.get("applicable"):
            continue
        row = {"episode": doc["evaluation"]["episode_id"], "published": t2.get("group_top1"),
               "belief": t2.get("belief_group"), "heldout": t2.get("heldout")}
        if replay:
            run = rm.load_run(str(s).replace(".summary.json", ".run.json.gz"))
            for rule in ("model", "belief_only", "tiebreak", "guarded", "nudge"):
                row[rule] = rm.group_top1(run, rm.replay(run, rule))[0]
        rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--replay", action="store_true")
    a = ap.parse_args()
    ok_all = True
    for f in a.folders:
        rows = folder(Path(f), a.replay)
        if not rows:
            print(f"{f}: no scored episodes")
            continue
        print(f"\n== {f}")
        extra = ["model", "belief_only", "tiebreak", "guarded", "nudge"] if a.replay else []
        print(f"{'episode':28s} {'published':>9s} {'belief':>7s} {'diff':>7s}" + "".join(f" {r:>11s}" for r in extra))
        for r in rows:
            d = r["published"] - r["belief"]
            print(f"{r['episode']:28s} {r['published']:9.3f} {r['belief']:7.3f} {d:+7.3f}"
                  + "".join(f" {r[x]:11.3f}" if r.get(x) is not None else f" {'-':>11s}" for x in extra)
                  + ("  (held-out)" if r["heldout"] else ""))
        mp = sum(r["published"] for r in rows) / len(rows)
        mb = sum(r["belief"] for r in rows) / len(rows)
        worst = min(r["published"] - r["belief"] for r in rows)
        ok = mp > mb and worst >= -MARGIN
        ok_all &= ok
        print(f"{'mean':28s} {mp:9.3f} {mb:7.3f} {mp - mb:+7.3f}   worst episode {worst:+.3f}")
        print(f"VERDICT: {'PASS' if ok else 'FAIL'} (mean above belief, no episode more than {MARGIN} below)")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
