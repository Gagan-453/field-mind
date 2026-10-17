#!/usr/bin/env python3
"""
first_threshold table from SHADOW runs on the DEV set (reports/bev_ideas.md):
for each candidate threshold, how often bev would have stood in for Llama
(coverage) and, among those, how often bev's top case equalled Llama's top
case and how often it was in the true case's look-alike group.

    .venv/bin/python -m bench.bev_calibrate TEST [TEST ...]

TEST: benchmark tests run with --bev "first=shadow" (and/or rt_fallback=shadow)
on dev_* episodes only. The tool REFUSES reporting episodes (ep_*): thresholds
are never set on them (project rule). It prints the table and picks nothing:
the threshold is a human decision, recorded in the report with this table.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bench.bev_report import find, load  # noqa: E402
from bench.case_groups import load_group_map  # noqa: E402

STEPS = [round(0.30 + 0.05 * i, 2) for i in range(14)]          # 0.30 .. 0.95


def rows(tests: list[dict]) -> list[dict]:
    gmap, held = load_group_map()
    out = []
    for t in tests:
        for ep, d in t["episodes"].items():
            if not ep.startswith("dev_"):
                raise SystemExit(f"{t['name']}: {ep} is not a dev episode; thresholds are set on dev only")
            gt = d["run"]["ground_truth"].get("root_cause_id")
            tg = held.get(gt) if gt in held else gmap.get(gt, gt)
            for a in d["run"]["assessments"]:
                for c in (a.get("multi") or {}).get("compact", []):
                    if c.get("agent") == "bev" and c.get("idea") in ("first", "rt_fallback") \
                            and c.get("p_top") is not None and c.get("answers"):
                        top = c["answers"]["root"]["ranking"][0]
                        out.append({"p": c["p_top"], "agree": c.get("agree_top"),
                                    "true_group": (tg is not None and gmap.get(top, top) == tg)})
    return out


def table(rs: list[dict]) -> str:
    lines = ["| threshold | would stand in | of asks | agrees with Llama | in true group |",
             "|---|---|---|---|---|"]
    for t in STEPS:
        sel = [r for r in rs if r["p"] >= t]
        ag = [r["agree"] for r in sel if r["agree"] is not None]
        tg = [r["true_group"] for r in sel]
        lines.append(f"| {t:.2f} | {len(sel)} | {len(sel) / len(rs):.3f} | "
                     f"{(sum(ag) / len(ag)) if ag else float('nan'):.3f} (n {len(ag)}) | "
                     f"{(sum(tg) / len(tg)) if tg else float('nan'):.3f} |")
    return "\n".join(lines)


def main(argv=None) -> int:
    names = argv if argv is not None else sys.argv[1:]
    if not names:
        print(__doc__)
        return 2
    rs = rows([load(find(n)) for n in names])
    if not rs:
        raise SystemExit("no first / rt_fallback shadow answers in these tests")
    print(f"{len(rs)} bev answers from shadow runs (dev set)\n")
    print(table(rs))
    print("\nNo threshold is chosen here: record the human choice and this table in reports/bev_ideas.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
