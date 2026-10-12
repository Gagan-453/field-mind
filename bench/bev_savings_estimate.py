"""
How many decode tokens each bev-decider idea could remove, estimated from the
calls the board actually made (no new model runs).

Sources (all measured on the QIDK, lockstep, synthetic plant data):
  results/benchmarks/multi_v3/          v3 (raw notes, no text reader)
  results/benchmarks/multi_nudge_6mark, multi_nudge_6.1mark   (text reader on)
  results/benchmarks/single_6mark/      single agent, for context

Every per-call record carries prefill / decode tokens and prefill_ms /
decode_ms as the server reported them. Re-tokenised variants of real answers
use the model's own tokenizer (bench/tokenizers/). Nothing here is a
bev-decider measurement: bev has not run on the board, so its own cost is
given only as token counts, never as time or energy.

  .venv/bin/python bench/bev_savings_estimate.py [--json out.json]
"""

from __future__ import annotations

import argparse
import glob
import gzip
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bench.case_groups import OUT as GROUPS_PATH, load_group_map  # noqa: E402

BENCH = ROOT / "results" / "benchmarks"
TOK = ROOT / "bench" / "tokenizers"


def runs(folder: str) -> list[dict]:
    return [json.load(gzip.open(f))
            for f in sorted(glob.glob(str(BENCH / folder / "*.run.json.gz")))]


def call_records(rs: list[dict]):
    """(run, assessment, envelope) for every model answer, text reader included."""
    for r in rs:
        for a in r["assessments"]:
            for e in a["envelopes"]:
                yield r, a, e
            for t in (a.get("multi") or {}).get("text") or []:
                if t.get("envelope"):
                    yield r, a, t["envelope"]


def per_agent(rs):
    agg = defaultdict(lambda: defaultdict(float))
    for _, _, e in call_records(rs):
        for c in e.get("calls") or []:
            g = agg[(e["agent"], e["backend"])]
            g["calls"] += 1
            g["prefill"] += c.get("prefill") or 0
            g["decode"] += c.get("decode") or 0
            g["prefill_ms"] += c.get("prefill_ms") or 0
            g["decode_ms"] += c.get("decode_ms") or 0
            g["latency_ms"] += c.get("latency_ms") or 0
            g["retries"] += 0
        agg[(e["agent"], e["backend"])]["retries"] += e.get("retries") or 0
    out = {}
    for (agent, lane), g in sorted(agg.items()):
        n = g["calls"]
        out[f"{agent}@{lane}"] = {
            "calls": int(n), "retries": int(g["retries"]),
            "prefill_tokens": int(g["prefill"]), "decode_tokens": int(g["decode"]),
            "decode_per_call": round(g["decode"] / n, 1),
            "prefill_per_call": round(g["prefill"] / n, 1),
            "decode_s": round(g["decode_ms"] / 1000, 1),
            "prefill_s": round(g["prefill_ms"] / 1000, 1),
            "call_s": round(g["latency_ms"] / 1000, 1),
            "decode_share_of_call": round(g["decode_ms"] / g["latency_ms"], 3),
            "ms_per_decode_token": round(g["decode_ms"] / g["decode"], 1),
            "ms_per_prefill_token": round(g["prefill_ms"] / g["prefill"], 2),
        }
    return out


# ----------------------------------------------------------------- ideas 3, 4
def strip_citations(ans: dict) -> dict:
    """Idea 4: Llama names the cases only; bev picks the supporting fact."""
    a = dict(ans)
    a["r"] = [x[0] if isinstance(x, list) else x for x in ans.get("r", [])]
    return a


def cut_to(ans: dict, k: int) -> dict:
    """Idea 3: bev narrows the candidates, so Llama ranks at most k cases."""
    a = dict(ans)
    a["r"] = list(ans.get("r", []))[:k]
    return a


def compact_json(d: dict) -> str:
    return json.dumps(d, separators=(",", ":"))


def answer_variants(rs, tok):
    rows = []
    for r, _, e in call_records(rs):
        if e["agent"] != "diagnostician" or e.get("status") != "ok":
            continue
        raw = e.get("raw_reply") or ""
        try:
            ans = json.loads(raw)
        except ValueError:
            continue
        n = lambda s: len(tok.encode(s, add_special_tokens=False).ids)  # noqa: E731
        rows.append({
            "key": (r["episode_id"], e["tick"], e.get("prompt_tokens")),
            "decode": e["tokens"]["decode"],
            "decode_ms": sum(c.get("decode_ms") or 0 for c in e.get("calls") or []),
            "raw": n(raw),
            "round_trip": n(compact_json(ans)),
            "no_cites": n(compact_json(strip_citations(ans))),
            "top3": n(compact_json(cut_to(ans, 3))),
            "top3_no_cites": n(compact_json(strip_citations(cut_to(ans, 3)))),
            "ranked": len(ans.get("r", [])),
        })
    return rows


# --------------------------------------------------------------------- idea 2
def side_of_envelopes(a: dict) -> dict[int, str]:
    """Envelope index -> side. The scheduler's job results name the side
    (diag_water / diag_heat) but log the ESTIMATED prompt size, the envelope
    the real one; both grow with the prompt, so within a tick the two lists
    are paired in order of prompt size. A tick whose counts differ is left
    unmatched (counted)."""
    res = sorted((x for x in (a.get("multi") or {}).get("results") or []
                  if str(x.get("agent", "")).startswith("diag_")),
                 key=lambda x: x.get("prompt_tokens") or 0)
    env = sorted((i for i, e in enumerate(a["envelopes"]) if e["agent"] == "diagnostician"),
                 key=lambda i: a["envelopes"][i].get("prompt_tokens") or 0)
    if len(res) != len(env):
        return {}
    return {i: x["agent"][len("diag_"):] for i, x in zip(env, res)}


def skip_replay(rs, gmap, held):
    """Idea 2 (call or skip), replayed on the v3 calls. Before each side's call
    the code knows (a) belief's leader this tick and (b) that side's previous
    model top case. 'Eligible' = (a) == (b): the only calls a skip rule that
    also requires bev to agree could skip. bev's agreement is not known, so
    eligible is an UPPER bound on skipped calls. For each eligible call:
    'same' = the new answer's top case equals the previous one (skip loses
    nothing on rank 1); 'changed' = it differs (skip would have kept the old
    top), split by whether the change moved into or out of the true group."""
    c = defaultdict(int)
    decode_eligible = 0
    ms = defaultdict(float)
    keys = set()
    for r in rs:
        gt = r["ground_truth"].get("root_cause_id")
        tgroup = held.get(gt) if gt in held else gmap.get(gt, gt)
        prev: dict[str, str] = {}
        for a in r["assessments"]:
            sides = side_of_envelopes(a)
            lead = (a.get("belief_ranking") or [{}])[0].get("case_ref")
            for i, e in enumerate(a["envelopes"]):
                if e["agent"] != "diagnostician":
                    continue
                c["calls"] += 1
                side = sides.get(i)
                hyps = (e.get("payload") or {}).get("hypotheses") or []
                top = hyps[0].get("case_ref") if hyps else None
                if side is None:
                    c["side_unmatched"] += 1
                    continue
                p = prev.get(side)
                if p is not None and p == lead:
                    c["eligible"] += 1
                    decode_eligible += e["tokens"]["decode"]
                    keys.add((r["episode_id"], e["tick"], e.get("prompt_tokens")))
                    for cc in e.get("calls") or []:
                        ms["decode_s"] += (cc.get("decode_ms") or 0) / 1000
                        ms["call_s"] += (cc.get("latency_ms") or 0) / 1000
                    if top == p:
                        c["eligible_same_top"] += 1
                    else:
                        c["eligible_changed_top"] += 1
                        old_ok = gmap.get(p) == tgroup
                        new_ok = gmap.get(top) == tgroup
                        if new_ok and not old_ok:
                            c["changed_into_true_group"] += 1
                        elif old_ok and not new_ok:
                            c["changed_out_of_true_group"] += 1
                        else:
                            c["changed_same_group_status"] += 1
                if top is not None:
                    prev[side] = top
    c["decode_tokens_eligible"] = decode_eligible
    c.update({k: round(v, 1) for k, v in ms.items()})
    return dict(c), keys


# --------------------------------------------------------------------- idea 6
def verifier_claims(rs):
    n_claims = []
    for _, _, e in call_records(rs):
        if e["agent"] != "verifier":
            continue
        try:
            n_claims.append(len(json.loads(e.get("raw_reply") or "")["v"]))
        except (ValueError, KeyError, TypeError):
            pass
    return n_claims


# ---------------------------------------------------------------- bev's input
def bev_request_tokens(qwen):
    """Tokens bev would read for the 24 dev conformance requests (the decider's
    real request format): state + each option (cut at 64) + the question."""
    reqs = json.load(open(ROOT / "reports" / "data" / "bev_requests.json"))
    out = []
    for x in reqs:
        q = x["request"]
        n = lambda s: len(qwen.encode(s, add_special_tokens=False).ids)  # noqa: E731
        state = n(q["state"])
        opts = 0
        for qq in q["questions"].values():
            opts += n(qq["instructions"])
            for k, v in (qq.get("criteria") or {}).items():
                opts += min(64, n(f"{k}: {v}"))
        out.append({"state": state, "options_and_question": opts, "total": state + opts,
                    "n_options": sum(len(qq.get("criteria") or {}) for qq in q["questions"].values())})
    return out


def summary(xs):
    xs = sorted(xs)
    return {"n": len(xs), "median": st.median(xs), "mean": round(st.mean(xs), 1),
            "min": xs[0], "max": xs[-1]} if xs else {"n": 0}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    from tokenizers import Tokenizer
    llama = Tokenizer.from_file(str(TOK / "llama3.2-3b" / "tokenizer.json"))
    qwen = Tokenizer.from_file(str(TOK / "qwen3-1.7b" / "tokenizer.json"))
    gmap, held = load_group_map(GROUPS_PATH)

    v3 = runs("multi_v3")
    nudge = runs("multi_nudge_6mark") + runs("multi_nudge_6.1mark")
    single = runs("single_6mark")

    rows = answer_variants(v3, llama)
    tot = {k: sum(r[k] for r in rows) for k in rows[0] if k not in ("ranked", "key")}
    replay, eligible = skip_replay(v3, gmap, held)
    # Idea 4's time: the citation tokens at each call's own measured decode rate.
    cite_s = sum((r["raw"] - r["no_cites"]) * r["decode_ms"] / r["decode"] / 1000
                 for r in rows if r["decode"])
    # Ideas 2 + 4 together: skipped calls decode nothing; the rest lose their
    # citation tokens. Keys are unique (checked below).
    assert len({r["key"] for r in rows}) == len(rows)
    combined = sum(0 if r["key"] in eligible else r["decode"] - (r["raw"] - r["no_cites"])
                   for r in rows)
    out = {
        "v3_per_agent": per_agent(v3),
        "nudge_per_agent": per_agent(nudge),
        "single_per_agent": per_agent(single),
        "v3_ticks": sum(r["n_ticks"] for r in v3),
        "v3_episodes": len(v3),
        "v3_diag_answer_tokens": {
            "answers": len(rows), "totals": tot,
            "ranked_cases": summary([r["ranked"] for r in rows]),
            "answers_ranking_more_than_3": sum(r["ranked"] > 3 for r in rows),
            "decode_minus_raw_tokens": summary([r["decode"] - r["raw"] for r in rows]),
            "citation_tokens": tot["raw"] - tot["no_cites"],
            "citation_decode_s": round(cite_s, 1),
            "diag_decode_after_ideas_2_and_4": combined,
        },
        "v3_skip_replay": replay,
        "v3_verifier_claims": summary(verifier_claims(v3)),
        "bev_request_tokens": {k: summary([x[k] for x in bev_request_tokens(qwen)])
                               for k in ("state", "options_and_question", "total", "n_options")},
    }
    print(json.dumps(out, indent=1))
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
