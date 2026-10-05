#!/usr/bin/env python3
"""
=============================================================================
 STAGE MONITOR, MULTI-AGENT  --  live view of a real-time multi-agent run
=============================================================================

  python bench/stage_monitor_multi.py                 # the newest multi-agent run
  python bench/stage_monitor_multi.py --episode ep_A01_fcv_seize
  python bench/stage_monitor_multi.py --once          # print one frame and exit

A VIEWER, not a runner. Start the run with scripts/presentation_multi_all.sh
(or run_demo.py --live-ticks <file>) and this in a second terminal or tmux
pane. It changes nothing in the run: it reads the <ep>_multi.ticks.jsonl file the
run appends to on every tick, and asks each lane's llama-server whether it is
working right now (GET /slots, about once a second; --no-poll turns that off).
When the run moves on to the next episode, the viewer follows it.

It shows, live:

  * the three compute units and what each is doing now: the tick code on the
    LAPTOP, the NPU lane and the CPU lane on the board -- which job of which
    tick;
  * every tick: state, triage, the time of the tick's code path, and one cell
    per model job (water diagnosis, heat diagnosis, verifier, note reader).

WHAT IS LIVE AND WHAT IS NOT. A lane's busy / idle comes from the board and is
live. WHICH job it is working on comes from the tick file, which only says a
job was sent (at its tick) and, at the tick its answer is folded, how long it
ran. So "running" names the oldest job sent to that lane whose answer has not
been folded yet. Laptop times of the tick code are not board times.

BACK-TO-BACK RUNS (lockstep, scripts/benchmark_multi_lockstep_all.sh). A tick
waits for its own model answers, so its line reaches the file only when all of
them are in. The cells then show each call's real time (the envelope's
latency_ms; the scheduler's job times are a simulated clock in that mode and
are not shown). While a tick is running, the lanes' busy / idle is still live,
but which job it is cannot be known until the tick completes.
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import socket
import statistics
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BENCH_DIR = ROOT / "results/presentation_benchmark"     # multi_agent*/ folders in it
SUFFIX = "_multi"            # every multi-agent result file: <ep>_multi.<kind>
COLS = ("diag_water", "diag_heat", "verifier", "text_reader")
LABEL = {"diag_water": "water diagnosis", "diag_heat": "heat diagnosis",
         "verifier": "verifier", "text_reader": "note reader"}
HARD_LIMIT_MS = 200          # CITED: CLAUDE.md, the hard path's limit per tick
ANSI = {"reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m", "yellow": "\033[33m",
        "green": "\033[32m", "magenta": "\033[35m", "red": "\033[31m"}


def _c(text: str, *styles: str) -> str:
    return "".join(ANSI[s] for s in styles) + text + ANSI["reset"] if styles else text


def _clock(s: float) -> str:
    s = int(max(0, s))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


# ===========================================================================
#  The tick file -> rows and jobs
# ===========================================================================
def build(records: list[dict]) -> dict:
    """Rows (one per tick) and jobs (one per model call) from the tick records.
    A job's verdict is read from the gate's own record of its answer:
      ok      the answer was well-formed and used
      empty   well-formed, but it ranked no case the prompt showed
      bad     not the asked format, or the call failed (the tick's code-only
              ranking stands)
      stale   arrived too late, dropped
    and for the note reader: ok (note-fact accepted) or bad (rejected)."""
    rows, jobs, verdict = [], {}, {}
    for d in records:
        m = d.get("multi") or {}
        hyp = d.get("hypotheses") or []
        row = {"tick": d["tick"], "plant": str(d.get("timestamp", ""))[11:19],
               "state": d.get("state", ""), "triage": d.get("triage", ""),
               "p0_ms": m.get("p0_ms"), "cause": hyp[0]["cause"] if hyp else "",
               "reused": set()}
        rows.append(row)
        if "submitted" not in m:           # lockstep: every job of the tick is done
            jobs.update(_lockstep_jobs(d, m))
            for c in m.get("compact", []):
                if c.get("agent") == "merge":
                    row["reused"] = set(c.get("reused") or [])
            continue
        for j in m.get("submitted", []):
            jobs[j["job"]] = {"id": j["job"], "agent": j["agent"], "side": j.get("side"),
                              "tick": d["tick"], "sent_s": j.get("wall_s"), "lane": None,
                              "start_s": None, "finish_s": None, "verdict": None}
        for r in m.get("results", []):
            j = jobs.setdefault(r["job_id"], {
                "id": r["job_id"], "agent": r["agent"], "side": None,
                "tick": r["evidence_tick"], "sent_s": None, "verdict": None})
            j.update(lane=r.get("lane"), start_s=r.get("start_s"), finish_s=r.get("finish_s"),
                     queue_ms=r.get("queue_wait_ms"))
            if r.get("stale"):
                j["verdict"] = "stale"
        for t in m.get("text", []):
            j = jobs.get((t.get("result") or {}).get("job_id"))
            if j is not None:
                j["verdict"] = "ok" if (t.get("notefact") or {}).get("status") == "ok" else "bad"
        for c in m.get("compact", []):
            if c.get("agent") == "merge":
                row["reused"] = set(c.get("reused") or [])
            elif c.get("agent") == "diagnostician":
                v = "bad" if "answer" not in c else "empty" if c.get("empty_ranking") else "ok"
                verdict[("diag_" + str(c.get("side")), c["evidence_tick"])] = v
            elif c.get("agent") == "verifier":
                verdict[("verifier", c["evidence_tick"])] = "ok" if "answer" in c else "bad"
    for j in jobs.values():
        if j["verdict"] is None:
            j["verdict"] = verdict.get((j["agent"], j["tick"]))
    return {"rows": rows, "jobs": list(jobs.values())}


def is_lockstep(records: list[dict]) -> bool:
    """Real-time ticks always record what they submitted; lockstep ticks never do."""
    return bool(records) and "submitted" not in (records[0].get("multi") or {})


def _lockstep_jobs(d: dict, m: dict) -> dict:
    """A lockstep tick's model calls, with their REAL times: the envelopes of
    the tick (latency_ms), paired in order with the gate's record of each
    answer. The job times in `multi.results` are simulated and not used."""
    out, tick = {}, d["tick"]

    def add(agent, side, env, verdict):
        run = float(env.get("latency_ms") or 0.0) / 1000
        out[f"t{tick}-{agent}-{len(out)}"] = {
            "id": f"t{tick}-{agent}-{len(out)}", "agent": agent, "side": side, "tick": tick,
            "sent_s": None, "lane": env.get("backend"), "start_s": 0.0, "finish_s": run,
            "queue_ms": None, "verdict": verdict}

    envs = d.get("envelopes") or []
    for kind in ("diagnostician", "verifier"):
        recs = [c for c in m.get("compact", []) if c.get("agent") == kind]
        for env, c in zip([e for e in envs if e.get("agent") == kind], recs):
            used = "answer" in c and env.get("status") == "ok"
            if kind == "verifier":
                add("verifier", None, env, "ok" if used else "bad")
            else:
                add("diag_" + str(c.get("side")), c.get("side"), env,
                    "bad" if not used else "empty" if c.get("empty_ranking") else "ok")
    for t in m.get("text", []):
        add("text_reader", None, t.get("envelope") or {},
            "ok" if (t.get("notefact") or {}).get("status") == "ok" else "bad")
    return out


def lane_of(job: dict, placement: dict) -> str | None:
    return job.get("lane") or placement.get(job["agent"])


def lane_now(lane: str, jobs: list[dict], placement: dict, busy: bool | None,
             now_s: float, running_tick: int | None = None) -> tuple[str, bool]:
    """What a lane is doing: (text, working). `busy` is the board's own answer
    (True / False), or None when it was not asked or did not answer."""
    out = sorted((j for j in jobs if j.get("finish_s") is None
                  and lane_of(j, placement) == lane and j.get("sent_s") is not None),
                 key=lambda j: j["sent_s"])
    if not out:
        if busy and running_tick is not None:    # lockstep: the tick is not in the file yet
            return f"tick {running_tick:<4} working (the job is named when the tick completes)", True
        return ("working (job not in the tick file yet)", True) if busy else ("idle", False)
    j = out[0]
    what = f"tick {j['tick']:<4} {LABEL.get(j['agent'], j['agent'])}"
    more = f"  (+{len(out) - 1} waiting)" if len(out) > 1 else ""
    if busy is False:
        return f"idle · {what}: answered, folded at the next tick", False
    ago = f"sent {max(0.0, now_s - j['sent_s']):.1f} s ago"
    if busy is None:
        return f"{what}  {ago}, answer not folded yet (lane not asked){more}", True
    return f"{what}  running, {ago}{more}", True


MARK = {"ok": "✓", "empty": "∅", "bad": "✗", "stale": "~", None: ""}


def cell(row: dict, agent: str, jobs: list[dict], now_s: float,
         lane_busy: bool | None = None) -> str:
    """`lane_busy`: the board's answer for this agent's lane (None: not asked)."""
    mine = [j for j in jobs if j["agent"] == agent and j["tick"] == row["tick"]]
    if not mine:
        if agent.startswith("diag_") and agent[5:] in row["reused"]:
            return "reuse"
        return "—" if row["triage"] == "QUIET" else "·"
    running = [j for j in mine if j.get("finish_s") is None]
    if running and lane_busy is False:
        return "answered"                  # the lane is idle: folded at the next tick
    if running:
        sent = min((j["sent_s"] for j in running if j.get("sent_s") is not None), default=now_s)
        return f"▶{max(0.0, now_s - sent):.0f}s"
    run = max(j["finish_s"] - j["start_s"] for j in mine)
    return f"{run:.1f}s" + "".join(MARK.get(j["verdict"], "") for j in mine)


# ===========================================================================
#  The screen
# ===========================================================================
HDR = (f"{'tick':>5}  {'plant':<8}  {'state':<13} {'triage':<11} {'code':>6}  "
       f"{'water·NPU':>10} {'heat·NPU':>10} {'verify·CPU':>10} {'notes·CPU':>10}  top cause")


def render(model: dict, meta: dict, slots: dict, now_s: float,
           size: tuple[int, int], colour: bool = True) -> list[str]:
    cols, lines = size
    c = _c if colour else (lambda text, *styles: text)
    rows, jobs, placement = model["rows"], model["jobs"], meta["placement"]
    done = [j for j in jobs if j.get("finish_s") is not None]
    out = [c(f"FieldMind stage monitor, multi-agent   {meta['episode']}   "
             f"{'FINISHED' if meta.get('finished') else 'elapsed ' + _clock(now_s)}", "bold")]
    last = rows[-1]["tick"] if rows else "-"
    lock = bool(meta.get("lockstep"))
    nxt = rows[-1]["tick"] + 1 if rows and not meta.get("finished") else None
    pace = ("BACK TO BACK (lockstep): a tick waits for its answers, the next starts at once"
            if lock else f"real time · tick period {meta['tick_s']:g} s")
    out.append(f"{pace} · tick {last} of {meta.get('last_tick', '?')} · model calls "
               f"answered {len(done)}" + ("" if lock else f" · still out {len(jobs) - len(done)}"))
    stats = []
    for a in COLS:
        mine = [j for j in done if j["agent"] == a]
        if mine:
            med = statistics.median(j["finish_s"] - j["start_s"] for j in mine)
            bad = sum(j["verdict"] in ("bad", "stale") for j in mine)
            stats.append(f"{LABEL[a]} {len(mine)} (median {med:.1f} s, {bad} not usable)")
    if stats:
        out.append(c(" · ".join(stats), "dim"))
    out.append("")

    # ---- the three compute units ------------------------------------------
    out.append(f" {'UNIT':<46} NOW")
    p0 = rows[-1]["p0_ms"] if rows else None
    worst = max((r["p0_ms"] for r in rows if r["p0_ms"] is not None), default=None)
    wait = meta["tick_s"] - (now_s % meta["tick_s"])
    code = ("waiting for the first tick" if p0 is None else
            f"tick {last:<4} code path took {p0:.0f} ms (worst {worst:.0f}, limit "
            f"{HARD_LIMIT_MS}) · "
            + (f"tick {nxt} running for {meta.get('since_last_s', 0):.0f} s" if lock
               else f"next tick in {wait:.0f} s"))
    if meta.get("finished"):
        code = "episode finished"
    out.append(f" {('CODE  ' + meta['host'])[:46]:<46} "
               + c(code, *(("red",) if worst and worst > HARD_LIMIT_MS else ())))
    for lane in ("npu", "cpu"):
        text, working = lane_now(lane, jobs, placement, slots.get(lane), now_s,
                                 nxt if lock else None)
        unit = f"{lane.upper():<5} board · {meta['models'].get(lane, '?')}"
        if slots.get(lane) is None and meta.get("poll"):
            text += "   [lane did not answer]"
        out.append(f" {unit[:46]:<46} "
                   + c(text, *(("magenta", "bold") if working else ("dim",))))
        mine = [j for j in done if lane_of(j, placement) == lane]
        if mine:
            j = max(mine, key=lambda j: (j["tick"], j["finish_s"]))
            queue = ("" if j.get("queue_ms") is None
                     else f", waited {j['queue_ms']:.0f} ms in the queue")
            out.append(c(f"   last answer: tick {j['tick']} {LABEL.get(j['agent'], j['agent'])}, "
                         f"ran {j['finish_s'] - j['start_s']:.1f} s{queue}"
                         f"{', ' + j['verdict'] if j['verdict'] else ''}", "dim"))
    out.append("")

    # ---- tick list ---------------------------------------------------------
    out.append(c(HDR[:cols - 1], "bold"))
    body = []
    for r in rows:
        cells = [cell(r, a, jobs, now_s, slots.get(placement.get(a))) for a in COLS]
        code_ms = "" if r["p0_ms"] is None else f"{r['p0_ms']:.0f}ms"
        line = (f"{r['tick']:>5}  {r['plant']:<8}  {r['state']:<13} {r['triage']:<11} "
                f"{code_ms:>6}  " + " ".join(f"{x:>10}" for x in cells) + f"  {r['cause']}")
        style = (("yellow", "bold") if any(x.startswith("▶") or x == "answered" for x in cells)
                 else ("red",) if any("✗" in x or "~" in x for x in cells)
                 else ("dim",) if r["triage"] == "QUIET" else ())
        body.append((line[:cols - 1], style))
    room = max(3, lines - len(out) - 3)
    if len(body) > room:
        body = [(f"  … {len(body) - room + 1} earlier ticks (all in the tick file)", ("dim",))] \
            + body[-(room - 1):]
    out += [c(line, *style) for line, style in body]
    out.append(c("cells: ▶ running · answered = waits for the next tick · 2.5s time the call ran · ✓ used · ∅ ranked no "
                 "shown case · ✗ wrong format or failed · ~ stale · reuse = kept the earlier "
                 "answer · · not asked · — quiet tick"[:cols - 1], "dim"))
    return out


# ===========================================================================
#  Reading the run
# ===========================================================================
class Tail:
    """The complete lines of a growing JSONL file, read incrementally."""

    def __init__(self, path: Path):
        self.path, self.pos, self.records = path, 0, []

    def poll(self) -> None:
        with self.path.open("rb") as f:
            f.seek(self.pos)
            data = f.read()
        end = data.rfind(b"\n") + 1            # a half-written last line waits
        for line in data[:end].splitlines():
            if line.strip():
                self.records.append(json.loads(line))
        self.pos += end


class SlotPoller(threading.Thread):
    """Asks each lane's llama-server whether its slot is processing."""

    def __init__(self, urls: dict, period_s: float):
        super().__init__(daemon=True, name="slot-poller")
        self.urls, self.period_s, self.busy = urls, period_s, {k: None for k in urls}

    def run(self) -> None:
        while True:
            for lane, url in self.urls.items():
                try:
                    with urllib.request.urlopen(url.rstrip("/") + "/slots", timeout=1.0) as r:
                        self.busy[lane] = any(s.get("is_processing") for s in json.load(r))
                except Exception:
                    self.busy[lane] = None
            time.sleep(self.period_s)


def newest(run_dir: Path | None) -> Path | None:
    """The tick file written to last: in `run_dir`, or (None) in any
    multi-agent folder of the presentation benchmark."""
    found = run_dir.glob("*.ticks.jsonl") if run_dir else BENCH_DIR.glob("multi_agent*/*.ticks.jsonl")
    files = [p for p in found if ".interrupted-" not in p.name]
    return max(files, key=lambda p: p.stat().st_mtime, default=None)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", default=None,
                    help="the run's result folder (default: whichever multi_agent* folder "
                         "of results/presentation_benchmark was written to last)")
    ap.add_argument("--episode", default=None, help="default: the newest tick file in --dir")
    ap.add_argument("--config", default=str(ROOT / "configs/base.yaml"))
    ap.add_argument("--overlay", default=str(ROOT / "configs/fast.yaml"))
    ap.add_argument("--tick-s", type=float, default=30.0, help="the run's --tick-s")
    ap.add_argument("--refresh", type=float, default=0.5, help="screen refresh, seconds")
    ap.add_argument("--no-poll", action="store_true",
                    help="do not ask the lanes whether they are busy")
    ap.add_argument("--once", action="store_true", help="print one frame and exit")
    args = ap.parse_args()

    from run_demo import load_config
    cfg = load_config(args.config, None, args.overlay)
    lanes = cfg["multi"]["lanes"]
    run_dir = Path(args.dir) if args.dir else None
    poller = None
    if not args.no_poll:
        poller = SlotPoller({k: v["url"] for k, v in lanes.items()}, 1.0)
        poller.start()
        time.sleep(0.3 if args.once else 0.0)

    def frame(tail: Tail, size) -> list[str]:
        stem = tail.path.name[:-len(".ticks.jsonl")]       # <ep>_multi (older runs: <ep>)
        ep = stem.removesuffix(SUFFIX)
        gt = ROOT / cfg["paths"]["episodes"] / ep / "ground_truth.json"
        finished = (tail.path.parent / f"{stem}.summary.json").exists()
        n = len(tail.records)
        lock = is_lockstep(tail.records)
        since = 0.0 if finished or not n else time.time() - tail.path.stat().st_mtime
        if lock:
            # back to back: the ticks' own real times, plus the tick now running
            now_s = sum(r.get("tick_latency_ms") or 0.0 for r in tail.records) / 1000 + since
        else:
            # the run's own clock: tick i of the file is due at i * tick_s
            now_s = max(0, n - 1) * args.tick_s + since
        meta = {"episode": ep + ("   [" + tail.path.parent.name + "]"), "tick_s": args.tick_s,
                "finished": finished, "lockstep": lock, "since_last_s": since,
                "host": f"laptop {socket.gethostname()} ({platform.machine()})",
                "placement": cfg["multi"]["fixed_placement"], "poll": poller is not None,
                "models": {k: str(v.get("model_file", "?")).split("-Q4_0")[0]
                           for k, v in lanes.items()}}
        if gt.exists():
            dur = json.loads(gt.read_text())["duration_min"] * 60
            meta["last_tick"] = int(dur // cfg["agent"]["tick_period_s"]) - 1
        slots = dict(poller.busy) if poller is not None and not finished else {}
        return render(build(tail.records), meta, slots, now_s, size,
                      colour=sys.stdout.isatty())

    def pick() -> Path | None:
        if args.episode:
            ep = args.episode.removesuffix(SUFFIX)
            found = [p for d in ([run_dir] if run_dir else BENCH_DIR.glob("multi_agent*"))
                     for p in (d / f"{ep}{SUFFIX}.ticks.jsonl", d / f"{ep}.ticks.jsonl")
                     if p.exists()]
            return max(found, key=lambda p: p.stat().st_mtime, default=None)
        return newest(run_dir)

    path = pick()
    if path is None or not path.exists():
        print(f"no tick file in {run_dir or BENCH_DIR / 'multi_agent*'} yet: start the run "
              f"first (scripts/presentation_multi_all.sh or "
              f"scripts/benchmark_multi_lockstep_all.sh)", file=sys.stderr)
        return 2
    tail = Tail(path)
    tail.poll()
    if args.once or not sys.stdout.isatty():
        print("\n".join(frame(tail, shutil.get_terminal_size((150, 45)))))
        return 0
    term = sys.stdout
    term.write("\033[?1049h\033[?25l")                 # alternate screen, hide cursor
    try:
        while True:
            now = pick()
            if now is not None and now != tail.path and now.exists():
                tail = Tail(now)                       # the run moved to the next episode
            tail.poll()
            lines = frame(tail, shutil.get_terminal_size((150, 45)))
            term.write("\033[H" + "".join(l + "\033[K\n" for l in lines) + "\033[J")
            term.flush()
            time.sleep(args.refresh)
    except KeyboardInterrupt:
        return 0
    finally:
        term.write("\033[?25h\033[?1049l")
        term.flush()


if __name__ == "__main__":
    raise SystemExit(main())
