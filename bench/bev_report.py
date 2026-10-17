#!/usr/bin/env python3
"""
Compare benchmark tests: with and without bev ideas (reports/bev_ideas.md,
commit 12). Every number is read from the saved run files; nothing is
estimated.

    .venv/bin/python -m bench.bev_report A B [C ...] [--a2 A2] [--out DIR]

A, A2, B... are test names under results/benchmarks/ (or benchmarks_mock/),
or folder paths. A is the baseline; A2 (optional) a second run of the same
baseline, which gives the run-to-run spread |A1 - A2| the pass rule uses. Only
episodes every test has are compared. Writes COMPARE_<A>.md and .html into
the last test's folder (or --out).

Sections: accuracy (bench.evaluator.aggregate, pooled as the pass rule says);
per-stage ms per tick (each blackboard step's own time, nested steps
subtracted; LAPTOP times until the agent code runs on the board); model calls
per agent and lane (calls, read and decode tokens, call time, server-side read
and decode time, bev's tokenize / transformer / head time); lane busy share
(measured call time / episode wall time); board resources per server process
(bench/board_sampler.py; CPU s, cores busy, peak RSS; board load, clocks,
temps, supply energy -- null unless measured); what each bev idea did.

On the mock backend everything model-related is plumbing: the mock's call
times are nominal (it reports 5 ms it never spends) and its decode counts are
len(text)//4. The report says so at the top.
"""

from __future__ import annotations

import argparse
import gzip
import html
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bench.evaluator import aggregate  # noqa: E402

HARD = ("sensor", "triage", "retriever", "gate", "scheduler")


# ------------------------------------------------------------------ load
def find(name: str) -> Path:
    for p in (Path(name), ROOT / "results/benchmarks" / name, ROOT / "results/benchmarks_mock" / name):
        if p.is_dir() and any(p.glob("*.summary.json")):
            return p
    raise SystemExit(f"no benchmark test {name!r} (looked in results/benchmarks[_mock]/)")


def load(path: Path) -> dict:
    eps = {}
    for s in sorted(path.glob("*.summary.json")):
        stem = s.name[:-len(".summary.json")]
        summ = json.loads(s.read_text())
        ep = summ.get("meta", {}).get("episode") or stem.rsplit("_", 1)[0]
        run_p = path / f"{stem}.run.json.gz"
        if not run_p.exists():
            continue
        res_p = path / f"{stem}.resources.json"
        eps.setdefault(ep, {"summary": summ, "run": json.load(gzip.open(run_p)),
                            "resources": json.loads(res_p.read_text()) if res_p.exists() else None})
    test = json.loads((path / "test.json").read_text()) if (path / "test.json").exists() else {}
    any_run = next(iter(eps.values()))["run"] if eps else {}
    return {"name": path.name, "dir": path, "params": test.get("params", {}), "episodes": eps,
            "mock": any_run.get("backend") == "mock"}


# --------------------------------------------------------------- metrics
def _q(xs, f):
    s = sorted(xs)
    return s[min(len(s) - 1, int(f * len(s)))] if s else None


def _r(x, nd=2):
    return None if x is None else round(x, nd)


def metrics(t: dict, eps: list[str]) -> dict:
    runs = [t["episodes"][e]["run"] for e in eps]
    evs = [t["episodes"][e]["summary"]["evaluation"] for e in eps]
    agg = aggregate(evs)
    lib, held = agg.get("Q2_library") or {}, agg.get("Q2_heldout") or {}
    ticks = sum(r["n_ticks"] for r in runs)
    acc = {"library group top-1": lib.get("group_top1"), "library top-1": lib.get("top1"),
           "belief group top-1 (code only)": lib.get("belief_group"),
           "held-out group top-1": held.get("group_top1"),
           "faithfulness": agg.get("Q3_faithfulness"), "citation relevance": agg.get("Q3_rel"),
           "actions precision": agg.get("Q4_action_precision"),
           "actions recall": agg.get("Q4_action_recall"),
           "model invocation rate": agg.get("S4_llm_invocation_rate")}
    # per-stage ms per tick (ticks the stage ran)
    stage, tick_ms = defaultdict(list), []
    for r in runs:
        for a in r["assessments"]:
            m = a.get("multi") or {}
            for k, v in (m.get("stage_ms") or {}).items():
                stage[k].append(v)
            if m.get("tick_ms") is not None:
                tick_ms.append(m["tick_ms"])
    stages = {k: {"ticks": len(v), "mean": _r(statistics.mean(v), 3), "p95": _r(_q(v, 0.95), 3),
                  "max": _r(max(v), 3), "total_s": _r(sum(v) / 1000, 3)} for k, v in sorted(stage.items())}
    # model calls per agent @ lane
    calls = defaultdict(lambda: defaultdict(float))
    decode_total = 0
    for r in runs:
        envs = [e for a in r["assessments"] for e in a.get("envelopes", [])]
        envs += [x["envelope"] for a in r["assessments"] for x in (a.get("multi") or {}).get("text", [])]
        envs += [dict(e, agent=e["agent"] + " (shadow)") for a in r["assessments"]
                 for e in (a.get("multi") or {}).get("bev_shadow", [])]
        for e in envs:
            key = f"{e['agent']}@{e.get('backend', '?')}"
            c = calls[key]
            c["answers"] += 1
            if not e.get("calls"):
                c["stand_ins"] += 1                   # bev standing in: no call of its own
            for k in e.get("calls") or []:
                c["calls"] += 1
                c["read_tokens"] += k.get("prefill") or 0
                c["decode_tokens"] += k.get("decode") or 0
                decode_total += k.get("decode") or 0
                c["call_s"] += (k.get("latency_ms") or 0) / 1000
                c["server_read_s"] += (k.get("prefill_ms") or 0) / 1000
                c["server_decode_s"] += (k.get("decode_ms") or 0) / 1000
                for sk, sv in (k.get("server") or {}).items():
                    c[f"bev_{sk[:-3]}_s"] += sv / 1000
    calls = {k: {kk: (round(vv, 2) if isinstance(vv, float) and not vv.is_integer() else int(vv))
                 for kk, vv in v.items()} for k, v in sorted(calls.items())}
    # lanes: measured call time / wall time
    wall = sum(r.get("wall_clock_s") or 0 for r in runs)
    busy = defaultdict(float)
    for r in runs:
        for ln in (r.get("multi") or {}).get("lanes", []):
            busy[ln["lane"]] += ln.get("wall_busy_s") or 0
    lanes = {k: {"busy_s": _r(v, 1), "share_of_wall": _r(v / wall, 3) if wall else None}
             for k, v in sorted(busy.items())}
    # board resources
    res = [t["episodes"][e]["resources"] for e in eps if t["episodes"][e]["resources"]]
    res = [x for x in res if "error" not in x]
    procs, energy = defaultdict(lambda: defaultdict(float)), None
    for x in res:
        for k, p in (x.get("processes") or {}).items():
            procs[k]["cpu_s"] += p["cpu_s"]
            procs[k]["peak_rss_mb"] = max(procs[k]["peak_rss_mb"], p["peak_rss_mb"])
            procs[k]["process"] = p["process"]
    if res and all(x.get("supply_power") for x in res):
        energy = round(sum(v["supply_energy_j"] for x in res for v in x["supply_power"].values()), 1)
    dur = sum(x.get("duration_s") or 0 for x in res)
    board = {"episodes_sampled": len(res), "of": len(eps),
             "processes": {k: {"process": v["process"], "cpu_s": round(v["cpu_s"], 1),
                               "cores_busy_mean": round(v["cpu_s"] / dur, 3) if dur else None,
                               "peak_rss_mb": v["peak_rss_mb"]} for k, v in sorted(procs.items())},
             "board_cpu_busy_pct_mean": _r(statistics.mean([x["cpu_busy_pct"] for x in res
                                                            if x.get("cpu_busy_pct") is not None]), 1)
             if any(x.get("cpu_busy_pct") is not None for x in res) else None,
             "cpu_max_c": max((x["temps"].get("cpu_max_c") or 0 for x in res), default=None) or None,
             "npu_max_c": max((x["temps"].get("npu_max_c") or 0 for x in res), default=None) or None,
             "supply_energy_j": energy,
             "sampler_cpu_s": _r(sum(x.get("sampler_cpu_s") or 0 for x in res), 2) if res else None}
    # bev ideas
    bev = {"switches": None, "per_idea": defaultdict(lambda: defaultdict(int)), "agreement": {}}
    agree = defaultdict(list)
    for r in runs:
        b = (r.get("multi") or {}).get("bev")
        if b:
            bev["switches"] = b["switches"]
            for idea, cnt in b["per_idea"].items():
                for k, v in cnt.items():
                    bev["per_idea"][idea][k] += v
        for a in r["assessments"]:
            for c in (a.get("multi") or {}).get("compact", []):
                if c.get("agent") != "bev":
                    continue
                for k in ("cite_agreement", "agree_top", "agree", "agree_kind", "agree_subject",
                          "unknown_fault", "replaced_llama", "used"):
                    if c.get(k) is not None:
                        agree[f"{c['idea']}.{k}"].append(float(c[k]))
                if c.get("would_drop") is not None:
                    agree[f"{c['idea']}.would_drop_per_ask"].append(len(c["would_drop"]))
    bev["per_idea"] = {k: dict(v) for k, v in sorted(bev["per_idea"].items())}
    bev["agreement"] = {k: {"n": len(v), "mean": round(statistics.mean(v), 3)}
                        for k, v in sorted(agree.items())}
    return {"episodes": len(eps), "ticks": ticks, "wall_s": round(wall, 1), "accuracy": acc,
            "decode_tokens": decode_total, "decode_per_tick": round(decode_total / ticks, 2) if ticks else None,
            "stages": stages, "tick_ms": {"mean": _r(statistics.mean(tick_ms), 3) if tick_ms else None,
                                          "p95": _r(_q(tick_ms, 0.95), 3)},
            "calls": calls, "lanes": lanes, "board": board, "bev": bev}


# ---------------------------------------------------------------- render
def _f(x):
    return "–" if x is None else (f"{x:,}" if isinstance(x, int) else f"{x:g}" if isinstance(x, float) else str(x))


def _diff(b, a):
    return None if not isinstance(a, (int, float)) or not isinstance(b, (int, float)) else round(b - a, 4)


def build(tests: list[dict], a2: dict | None, out: Path) -> tuple[str, str]:
    eps = sorted(set.intersection(*[set(t["episodes"]) for t in tests + ([a2] if a2 else [])]))
    if not eps:
        raise SystemExit("the tests share no episode")
    M = [metrics(t, eps) for t in tests]
    M2 = metrics(a2, eps) if a2 else None
    names = [t["name"] for t in tests]
    mock = any(t["mock"] for t in tests + ([a2] if a2 else []))
    L = [f"# Benchmark comparison: {' vs '.join(names)}", ""]
    if mock:
        L += ["> **MOCK backend: plumbing only.** Model answers are the mock's (no reasoning); its call "
              "times are nominal and its decode counts are len(text)//4. Not an agent result.", ""]
    L += [f"Baseline **{names[0]}**" + (f", second baseline run **{a2['name']}**" if a2 else "")
          + f". {len(eps)} episodes in common: {', '.join(eps)}. Stage times are LAPTOP times "
          "(agent code runs on the laptop until Phase 4); model call times are as the client saw them. "
          "All plant data is synthetic.", ""]
    L += ["| test | settings |", "|---|---|"]
    for t in tests + ([a2] if a2 else []):
        p = t["params"]
        L.append(f"| {t['name']} | overlay `{p.get('overlay')}`, mode {p.get('mode')}, "
                 f"bev `{p.get('bev') or 'off'}`, backend {p.get('backend')} |")
    # headline
    head = ["episodes", "ticks", "wall_s", "decode_tokens", "decode_per_tick"]
    cols = names + ([a2["name"]] if a2 else []) + [f"{n} − {names[0]}" for n in names[1:]]
    L += ["", "## Headline", "", "| metric | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    spread = {}
    for k in head + list(M[0]["accuracy"]):
        vals = [m[k] if k in m else m["accuracy"].get(k) for m in M]
        a2v = (M2[k] if k in M2 else M2["accuracy"].get(k)) if M2 else None
        if M2 is not None:
            spread[k] = abs(_diff(a2v, vals[0])) if _diff(a2v, vals[0]) is not None else None
        row = vals + ([a2v] if M2 else []) + [_diff(v, vals[0]) for v in vals[1:]]
        L.append(f"| {k} | " + " | ".join(_f(x) for x in row) + " |")
    if M2:
        L += ["", "Run-to-run spread |A1 − A2|: " + ", ".join(f"{k} {_f(v)}" for k, v in spread.items()
                                                               if v is not None)]
    # stages
    st_keys = sorted(set().union(*[m["stages"] for m in M]), key=lambda k: (k not in HARD, k))
    L += ["", "## Time per stage, ms per tick it ran (LAPTOP)", "",
          "Each blackboard step's own time; a model agent's step includes its call. Hard path = "
          + ", ".join(HARD) + ".", "",
          "| stage | " + " | ".join(f"{n} mean / p95 / max" for n in names) + " |",
          "|---" * (len(names) + 1) + "|"]
    for k in st_keys:
        cells = []
        for m in M:
            s = m["stages"].get(k)
            cells.append("–" if not s else f"{_f(s['mean'])} / {_f(s['p95'])} / {_f(s['max'])} ({s['ticks']})")
        L.append(f"| {k}{' (hard path)' if k in HARD else ''} | " + " | ".join(cells) + " |")
    L.append("| whole tick | " + " | ".join(f"{_f(m['tick_ms']['mean'])} / {_f(m['tick_ms']['p95'])}"
                                            for m in M) + " |")
    # calls
    L += ["", "## Model calls per agent @ lane", "",
          "answers = envelopes; stand-ins = bev answering in that agent's place (no call of its own). "
          "Read = prefill. bev decodes nothing.", ""]
    for n, m in zip(names, M):
        L += [f"**{n}**", "", "| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | "
              "server read s | server decode s | bev tokenize / transformer / head s |", "|---" * 10 + "|"]
        for k, c in m["calls"].items():
            bev_s = " / ".join(_f(c.get(f"bev_{x}_s")) for x in ("tokenize", "decode", "head"))
            L.append(f"| {k} | {_f(c.get('answers'))} | {_f(c.get('calls', 0))} | {_f(c.get('stand_ins', 0))} | "
                     f"{_f(c.get('read_tokens', 0))} | {_f(c.get('decode_tokens', 0))} | {_f(c.get('call_s', 0))} | "
                     f"{_f(c.get('server_read_s', 0))} | {_f(c.get('server_decode_s', 0))} | {bev_s} |")
        L.append("")
    # lanes
    L += ["## Lane busy share (measured call time / episode wall time)", "",
          "| lane | " + " | ".join(names) + " |", "|---" * (len(names) + 1) + "|"]
    for ln in sorted(set().union(*[m["lanes"] for m in M])):
        L.append(f"| {ln} | " + " | ".join(
            (f"{_f(m['lanes'][ln]['busy_s'])} s ({_f(m['lanes'][ln]['share_of_wall'])})"
             if ln in m["lanes"] else "–") for m in M) + " |")
    # board
    L += ["", "## Board resources (bench/board_sampler.py)", "",
          "CPU s = utime + stime of the process; cores busy = CPU s / sampled time. NPU: no hardware "
          "counter is read; the NPU lane's work is its call time above. Supply energy is the power "
          "supply's, not the chip's, and `–` when the board does not expose it.", "",
          "| | " + " | ".join(names) + " |", "|---" * (len(names) + 1) + "|"]
    procs = sorted(set().union(*[m["board"]["processes"] for m in M]))
    for p in procs:
        L.append(f"| {p}: CPU s / cores busy / peak RSS MB | " + " | ".join(
            (lambda x: f"{_f(x['cpu_s'])} / {_f(x['cores_busy_mean'])} / {_f(x['peak_rss_mb'])}" if x else "–")(
                m["board"]["processes"].get(p)) for m in M) + " |")
    for k in ("episodes_sampled", "board_cpu_busy_pct_mean", "cpu_max_c", "npu_max_c",
              "supply_energy_j", "sampler_cpu_s"):
        L.append(f"| {k} | " + " | ".join(_f(m["board"][k]) for m in M) + " |")
    # bev
    L += ["", "## bev ideas", ""]
    for n, m in zip(names, M):
        b = m["bev"]
        if not b["switches"]:
            L += [f"**{n}**: every bev idea off.", ""]
            continue
        on = {k: v for k, v in b["switches"].items() if v != "off"}
        L += [f"**{n}**: {', '.join(f'{k}={v}' for k, v in on.items())}", "",
              "| idea | " + " | ".join(["calls", "failed", "rejected", "used", "shadow", "other"]) + " |",
              "|---" * 7 + "|"]
        for idea, c in b["per_idea"].items():
            other = {k: v for k, v in c.items() if k not in ("calls", "failed", "rejected", "used", "shadow")}
            L.append(f"| {idea} | " + " | ".join(_f(c.get(k, 0)) for k in
                                                 ("calls", "failed", "rejected", "used", "shadow"))
                     + f" | {', '.join(f'{k} {v}' for k, v in other.items()) or '–'} |")
        if b["agreement"]:
            L += ["", "| logged per answer | n | mean |", "|---|---|---|"]
            L += [f"| {k} | {v['n']} | {_f(v['mean'])} |" for k, v in b["agreement"].items()]
        L.append("")
    md = "\n".join(L) + "\n"
    return md, _html(md, names, M, mock)


def _bars(title: str, rows: list[tuple[str, float]], unit: str) -> str:
    rows = [(k, v) for k, v in rows if isinstance(v, (int, float))]
    if not rows:
        return ""
    mx = max(v for _, v in rows) or 1
    h = 22 * len(rows) + 10
    g = "".join(f'<text x="0" y="{22 * i + 16}" class="l">{html.escape(k)}</text>'
                f'<rect x="230" y="{22 * i + 4}" width="{max(1, 380 * v / mx):.1f}" height="14" class="b"/>'
                f'<text x="{236 + 380 * v / mx:.1f}" y="{22 * i + 16}" class="v">{v:g} {unit}</text>'
                for i, (k, v) in enumerate(rows))
    return f'<h3>{html.escape(title)}</h3><svg viewBox="0 0 700 {h}" width="100%">{g}</svg>'


def _html(md: str, names, M, mock) -> str:
    charts = _bars("Decode tokens per tick", [(n, m["decode_per_tick"]) for n, m in zip(names, M)], "tok")
    charts += _bars("Whole tick, mean ms (laptop)", [(n, m["tick_ms"]["mean"]) for n, m in zip(names, M)], "ms")
    charts += _bars("Model call time by agent@lane, s",
                    [(f"{n}: {k}", c.get("call_s", 0)) for n, m in zip(names, M) for k, c in m["calls"].items()], "s")
    charts += _bars("Board CPU s by process",
                    [(f"{n}: {k}", p["cpu_s"]) for n, m in zip(names, M)
                     for k, p in m["board"]["processes"].items()], "s")
    body = []
    for ln in md.splitlines():
        if ln.startswith("# "):
            body.append(f"<h1>{html.escape(ln[2:])}</h1>")
        elif ln.startswith("## "):
            body.append(f"<h2>{html.escape(ln[3:])}</h2>")
        elif ln.startswith("> "):
            body.append(f'<p class="warn">{html.escape(ln[2:]).replace("**", "")}</p>')
        elif ln.startswith("|") and not set(ln) <= set("|-"):
            cells = [c.strip() for c in ln.strip("|").split("|")]
            body.append("<tr>" + "".join(f"<td>{html.escape(c).replace('**', '')}</td>" for c in cells) + "</tr>")
        elif ln.strip():
            body.append(f"<p>{html.escape(ln).replace('**', '')}</p>")
    out, table = [], False
    for b in body:
        if b.startswith("<tr>") and not table:
            out.append("<table>")
            table = True
        if not b.startswith("<tr>") and table:
            out.append("</table>")
            table = False
        out.append(b)
    if table:
        out.append("</table>")
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
            "content='width=device-width, initial-scale=1'><title>Benchmark Comparison</title><style>"
            ":root{--ink:#1c2230;--muted:#5b6475;--line:#d9dee7;--soft:#f4f6f9;--bar:#1f5fae;--warn:#fbf1df}"
            "@media (prefers-color-scheme:dark){:root{--ink:#e6e9ef;--muted:#a3abba;--line:#3a4150;"
            "--soft:#222733;--bar:#6aa0e6;--warn:#3d3220}body{background:#161a22}}"
            "body{font:14px/1.45 -apple-system,Helvetica,Arial,sans-serif;color:var(--ink);background:#fff;"
            "margin:0 auto;max-width:1100px;padding:16px}table{border-collapse:collapse;width:100%;"
            "font-size:12.5px;margin:8px 0 16px;display:block;overflow-x:auto}td{border-bottom:1px solid "
            "var(--line);padding:4px 8px;white-space:nowrap}tr:first-child td{font-weight:600;"
            "background:var(--soft)}.warn{background:var(--warn);padding:8px 10px;border-radius:6px}"
            "svg .l{font-size:11px;fill:var(--ink)}svg .v{font-size:11px;fill:var(--muted)}"
            "svg .b{fill:var(--bar)}h2{border-bottom:1px solid var(--line);padding-bottom:4px}</style>"
            "</head><body>" + "\n".join(out[:4]) + charts + "\n".join(out[4:]) + "</body></html>")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("tests", nargs="+", help="baseline A first, then the arms to compare")
    ap.add_argument("--a2", default=None, help="a second run of the baseline (run-to-run spread)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    tests = [load(find(n)) for n in a.tests]
    a2 = load(find(a.a2)) if a.a2 else None
    out = Path(a.out) if a.out else tests[-1]["dir"]
    md, page = build(tests, a2, out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"COMPARE_{tests[0]['name']}.md").write_text(md)
    (out / f"COMPARE_{tests[0]['name']}.html").write_text(page)
    print(md)
    stem = out / f"COMPARE_{tests[0]['name']}"
    print(f"written: {stem}.md and {stem}.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
