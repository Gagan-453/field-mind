"""
bev-decide conformance (reports/bev_decider.md, Part C steps 3 and 5): does the
board's bev-decide compute what bev_decider computes?

  1. requests   real decider requests from DEV episodes (a mock multi-agent run
                with configs/bev.yaml records every request it would send);
                never the reporting episodes
     .venv/bin/python -m bench.bev_conformance requests --out reports/data/bev_requests.json

  2. reference  bev_decider itself (PyTorch, fp32 on the CPU: exact, order
                invariant) on every request, plus each request with its options
                reversed. Needs torch + transformers + bev_decider 0.2.1, e.g. in
                llama.cpp's venv-convert:  <venv>/bin/pip install --no-deps bev-decider==0.2.1
     <venv>/bin/python -m bench.bev_conformance reference <bev-decider-0.4B dir> \\
         --requests reports/data/bev_requests.json --out reports/data/bev_reference.json

  3. compare    the same requests to a running bev-decide (debug on, so it
                returns its token ids), and again with the options reversed
     .venv/bin/python -m bench.bev_conformance compare http://localhost:8082 \\
         --reference reports/data/bev_reference.json --label cpu-16bit \\
         --out reports/data/bev_conformance_cpu-16bit.json

What compare reports:
  tokens     the board's prompt + options + answer token ids == bev_decider's
             input_ids, request by request. The one automatic check: exit 3.
  rank 1     agreement count, and EVERY disagreement listed with the
             reference's top-two margin: exit 4 if there is any, for a person
             to read. No margin threshold is applied: one defined from the
             board's own drift passes a broken port (its drift is large, so
             nothing counts as decisive -- caught by
             tests/test_bev_conformance.py), and a fixed one would be invented.
  max/median |p_board - p_ref| over every option, and the shuffle drift
             (|p| change when only the option order changes). Reported, not
             thresholded: bev_decider's README puts bf16 rounding noise at
             ~0.001 and says it can flip only near-ties; whether a larger
             number is drift or a porting bug is read from the 16-bit-on-CPU
             run against the Q8_0-on-HTP0 run.
Host side, stdlib only (reference imports bev_decider, which needs torch).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEV = ROOT / "data" / "episodes_dev"
# the dev quick set's fault episodes (reports/multi_accuracy_fix.md), DEV only
EPISODES = ["dev_A01_fcv_seize", "dev_A02_fcv_seize_fast", "dev_B01_tube_leak",
            "dev_B02_tube_leak_fast", "dev_C01_wet_coal", "dev_C02_feeder_trip",
            "dev_D01_high_cv_coal", "dev_D03_high_cv_severe"]


def reversed_options(request: dict) -> dict:
    """The same request with every question's criteria in reverse order."""
    r = json.loads(json.dumps(request))
    for q in r["questions"].values():
        if isinstance(q.get("criteria"), dict):
            q["criteria"] = dict(reversed(list(q["criteria"].items())))
    return r


# ---------------------------------------------------------------------------
def build_requests(n: int = 30, episodes: list[str] = EPISODES) -> list[dict]:
    import yaml
    from run_demo import _deep_merge
    from bench.harness import Episode, run_episode
    cfg = yaml.safe_load((ROOT / "configs/base.yaml").read_text())
    _deep_merge(cfg, yaml.safe_load((ROOT / "configs/bev.yaml").read_text()))
    cfg["llm"]["backend"] = "mock"
    cfg["agent"]["log_prompts"] = True
    per_ep = max(1, n // len(episodes))
    out = []
    for ep in episodes:
        run = run_episode(Episode(DEV / ep), cfg, arch="multi")
        calls = [(a["tick"], e["prompt"]) for a in run["assessments"]
                 for e in a["envelopes"] if e["agent"] == "decider"]
        if not calls:
            continue
        step = max(1, len(calls) // per_ep)            # evenly spaced over the episode
        for tick, prompt in calls[::step][:per_ep]:
            out.append({"id": f"{ep}@t{tick}", "request": json.loads(prompt)})
    return out


# ---------------------------------------------------------------------------
def reference(model_dir: str, items: list[dict]) -> list[dict]:
    from bev_decider import load                     # needs torch + transformers
    dec = load(model_dir, device="cpu", precision="fp32")
    out = []
    for it in items:
        req = it["request"]
        row = {"id": it["id"], "request": req, "answers": {}, "input_ids": {},
               "answers_reversed": {}}
        row["answers"] = dec.decide(req["state"], req["questions"])
        row["answers_reversed"] = dec.decide(req["state"], reversed_options(req)["questions"])
        for qid, q in req["questions"].items():
            row["input_ids"][qid] = list(dec.encoder.encode(req["state"], q)["input_ids"])
        out.append(row)
    return out


# ---------------------------------------------------------------------------
def _post(url: str, body: dict, timeout: float = 120) -> dict:
    req = urllib.request.Request(f"{url.rstrip('/')}/v1/systemone",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _probs(a: dict) -> dict:
    if a["type"] == "noul":
        return {"true": a["noul"], "false": 1 - a["noul"]}
    return a["probabilities"]


def _top(p: dict) -> tuple[str, float]:
    s = sorted(p.values(), reverse=True)
    return max(p, key=p.get), (s[0] - s[1]) if len(s) > 1 else 1.0


def compare(url: str, ref: list[dict], post=_post) -> dict:
    rows, diffs, shuffle = [], [], []
    for r in ref:
        board = post(url, dict(r["request"], debug=True))
        board_rev = post(url, reversed_options(r["request"]))
        for qid in r["request"]["questions"]:
            t = board["token_ids"][qid]
            ids = t["prompt"] + [x for o in t["options"] for x in o] + t["answer"]
            pb, pr = _probs(board["answers"][qid]), _probs(r["answers"][qid])
            prb = _probs(board_rev["answers"][qid])
            d = {k: abs(pb[k] - pr[k]) for k in pr}
            diffs += d.values()
            shuffle += [abs(prb[k] - pb[k]) for k in pb]
            top_b, _ = _top(pb)
            top_r, margin = _top(pr)
            rows.append({"id": r["id"], "question": qid,
                         "tokens_identical": ids == r["input_ids"][qid],
                         "n_tokens": len(r["input_ids"][qid]),
                         "max_abs_dp": max(d.values()), "top_board": top_b, "top_ref": top_r,
                         "ref_margin": margin, "latency_ms": board.get("latency_ms"),
                         "prompt_tokens": (board.get("usage") or {}).get("prompt_tokens")})
    lat = [x["latency_ms"] for x in rows if x["latency_ms"] is not None]
    return {
        "n_questions": len(rows),
        "tokens_identical": sum(x["tokens_identical"] for x in rows),
        "max_abs_dp": max(diffs) if diffs else None,
        "median_abs_dp": statistics.median(diffs) if diffs else None,
        "rank1_agree": sum(x["top_board"] == x["top_ref"] for x in rows),
        "rank1_disagreements": [{"id": x["id"], "question": x["question"],
                                 "board": x["top_board"], "reference": x["top_ref"],
                                 "reference_margin": round(x["ref_margin"], 6)}
                                for x in rows if x["top_board"] != x["top_ref"]],
        "shuffle_max_abs_dp": max(shuffle) if shuffle else None,
        "latency_ms_median": statistics.median(lat) if lat else None,
        "pass_tokens": all(x["tokens_identical"] for x in rows),
        "rows": rows,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("requests")
    a.add_argument("--out", required=True)
    a.add_argument("--n", type=int, default=30)
    b = sub.add_parser("reference")
    b.add_argument("model_dir")
    b.add_argument("--requests", required=True)
    b.add_argument("--out", required=True)
    c = sub.add_parser("compare")
    c.add_argument("url")
    c.add_argument("--reference", required=True)
    c.add_argument("--label", required=True)
    c.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "requests":
        items = build_requests(args.n)
        Path(args.out).write_text(json.dumps(items, indent=1, ensure_ascii=False) + "\n")
        print(f"{len(items)} requests from {len(EPISODES)} dev episodes -> {args.out}")
        return 0
    if args.cmd == "reference":
        items = json.loads(Path(args.requests).read_text())
        Path(args.out).write_text(json.dumps(reference(args.model_dir, items), indent=1,
                                             ensure_ascii=False) + "\n")
        print(f"reference for {len(items)} requests -> {args.out}")
        return 0
    res = compare(args.url, json.loads(Path(args.reference).read_text()))
    res["label"], res["url"] = args.label, args.url
    Path(args.out).write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))
    return 3 if not res["pass_tokens"] else 4 if res["rank1_disagreements"] else 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.exit(main())
