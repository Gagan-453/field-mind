#!/usr/bin/env python3
"""
=============================================================================
 FieldMind Boiler Agent  --  entry point
=============================================================================

  python run_demo.py --episode ep_A01_fcv_seize --verbose
  python run_demo.py --all
  python run_demo.py --all --backend gemini          # needs GOOGLE_API_KEY
  python run_demo.py --all --backend litert          # needs the QIDK attached
  python run_demo.py --all --ablate-text             # the T8 modality check

The backend flag overrides configs/base.yaml. Nothing else about the pipeline
changes between backends -- same prompts, same parsing, same gate, same
metrics. That is the point.
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from bench.evaluator import aggregate, evaluate          # noqa: E402
from bench.board import chip_temperature                 # noqa: E402
from bench.harness import Episode, run_episode           # noqa: E402


def load_config(path: str, backend: str | None) -> dict:
    cfg = yaml.safe_load(Path(path).read_text())
    if backend:
        cfg["llm"]["backend"] = backend
    return cfg


def main():
    ap = argparse.ArgumentParser(description="FieldMind boiler agent")
    ap.add_argument("--config", default="configs/base.yaml")
    ap.add_argument("--episode", default=None, help="one episode id")
    ap.add_argument("--all", action="store_true", help="run every episode")
    ap.add_argument("--backend", default=None,
                    choices=["mock", "gemini", "litert", "llamaserver"],
                    help="overrides llm.backend in the config")
    ap.add_argument("--ablate-text", action="store_true",
                    help="remove all notes (T8 modality ablation)")
    ap.add_argument("--log-prompts", action="store_true",
                    help="store the rendered prompt and raw model reply in "
                         "every AgentEnvelope (large output; for debugging)")
    ap.add_argument("--episodes", default=None,
                    help="comma-separated episode ids to run (subset)")
    ap.add_argument("--url", default=None,
                    help="overrides llm.llamaserver.url (e.g. the CPU lane, :8081)")
    ap.add_argument("--lane", default=None,
                    help="overrides llm.llamaserver.lane (npu|cpu label)")
    ap.add_argument("--cooldown-s", type=float, default=0.0,
                    help="board runs: idle gap between episodes (chip cooling)")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--out", default="results")
    ap.add_argument("--episodes-dir", default=None,
                    help="overrides paths.episodes (e.g. data/episodes_dev)")
    ap.add_argument("--tag", default="",
                    help="suffix for the results files, so a dev run never "
                         "overwrites a reporting run")
    args = ap.parse_args()

    cfg = load_config(args.config, args.backend)
    ls = cfg["llm"].setdefault("llamaserver", {})
    if args.url:
        ls["url"] = args.url
    if args.lane:
        ls["lane"] = args.lane
    cfg.setdefault("agent", {})["log_prompts"] = args.log_prompts
    ep_dir = Path(args.episodes_dir or cfg["paths"]["episodes"])
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.episode:
        targets = [ep_dir / args.episode]
    elif args.episodes:
        targets = [ep_dir / e.strip() for e in args.episodes.split(",") if e.strip()]
    elif args.all:
        targets = sorted(p for p in ep_dir.iterdir() if p.is_dir())
    else:
        ap.error("give --episode <id>, --episodes a,b,c, or --all")

    print(f"backend = {cfg['llm']['backend']}"
          f"{'  [TEXT ABLATED]' if args.ablate_text else ''}")
    if cfg["llm"]["backend"] == "mock":
        # Say this every single run. A mock number that leaks into a table is
        # the most likely way this project reports something untrue.
        print("NOTE: mock backend. These numbers measure the deterministic and "
              "retrieval layers only.\n      They are NOT an agent result and "
              "must not be reported as one.")
    print()

    evals, runs = [], []
    for path in targets:
        if not (path / "ground_truth.json").exists():
            continue
        ep = Episode(path)
        if args.verbose:
            print(f"--- {ep.id}  ({ep.ground_truth['family']}/"
                  f"tier {ep.ground_truth['tier']}) "
                  f"truth: {ep.ground_truth['root_cause_text']}")
        on_board = cfg["llm"]["backend"] in ("llamaserver", "litert")
        if on_board and runs and args.cooldown_s > 0:
            time.sleep(args.cooldown_s)            # chip cooling between episodes
        temp0 = chip_temperature() if on_board else None
        run = run_episode(ep, cfg, ablate_text=args.ablate_text,
                          verbose=args.verbose)
        if on_board:
            run["chip_temp_start"] = temp0
            run["chip_temp_end"] = chip_temperature()
            run["cooldown_s_before"] = args.cooldown_s if len(runs) else 0.0
            print(f"  chip temp start {temp0}  end {run['chip_temp_end']}")
        ev = evaluate(run)
        runs.append(run)
        evals.append(ev)

        t2 = ev["T2_root_cause"]
        t6 = ev["T6_lead_time"]
        print(f"{ep.id:30s} F1={ev['T1_state']['macro_f1']:.2f} "
              f"top1={t2.get('top1', '-'):>5} top3={t2.get('top3', '-'):>5} "
              f"faith={ev['T3_faithfulness']['faithfulness']:.2f} "
              f"llm={ev['S4_llm_invocation_rate']:.2f} "
              f"lead={t6.get('lead_time_min', '-')} "
              f"p95={ev['S1_tick_latency_ms_p95']:.0f}ms")

    summary = aggregate(evals)
    tag = (f"{cfg['llm']['backend']}{'_ablated' if args.ablate_text else ''}"
           f"{'_' + args.tag if args.tag else ''}")
    (out_dir / f"summary_{tag}.json").write_text(json.dumps(
        {"config_backend": cfg["llm"]["backend"], "summary": summary,
         "per_episode": evals}, indent=2))
    (out_dir / f"runs_{tag}.json").write_text(json.dumps(runs, indent=2))

    print("\n" + "=" * 66)
    print("AGGREGATE")
    print("=" * 66)
    for k, v in summary.items():
        if k == "constraints":
            continue
        print(f"  {k:34s} {v}")
    print("  constraints:")
    for k, v in summary["constraints"].items():
        print(f"    {k:32s} {'PASS' if v else 'FAIL'}")
    print(f"\nwritten to {out_dir}/summary_{tag}.json")


if __name__ == "__main__":
    main()
