#!/usr/bin/env python3
"""
Board resource sampler (reports/bev_ideas.md, commit 11): what each server
process on the QIDK costs while a benchmark episode runs.

    .venv/bin/python -m bench.board_sampler probe        # what the board exposes
    .venv/bin/python -m bench.board_sampler parse FILE   # a pulled sample file

bench/benchmark.py calls start() before an episode and stop() after it, and
writes <stem>.resources.json. The sampler (bench/board_sampler.sh, pushed and
sha256-checked) runs on the board at 1 Hz; it stops when the laptop creates a
new stop file (nothing on the board is ever deleted).

What it measures, and what it does NOT:
  cpu_s per process   utime + stime deltas of each llama-server / bev-decide,
                      in /proc clock ticks (CLK_TCK; 100 = Linux USER_HZ,
                      CITED: proc(5); the probe reads the board's own value)
  peak_rss_mb         VmRSS, the largest sample
  cpu_busy_pct        the whole board, from /proc/stat (all cores, any process)
  freq_mhz            each cpufreq policy (cluster), mean and max
  temps               max over CPU / NPU thermal zones (bench.board.summarise rule)
  supply power        current_now x voltage_now of each readable power_supply
                      (kernel ABI: uA and uV). The SUPPLY's power, not the
                      chip's: reported as supply_energy_j, never as the
                      headline energy (summary energy_mwh stays null)
  NPU                 no hardware counter is assumed readable without root; the
                      report uses NPU-lane compute time from the call records
  sampler_cpu_s       the sampler's own cost (itself + its children)
Host-side tool; imports nothing from fieldmind/.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bench import board  # noqa: E402

SCRIPT = ROOT / "bench" / "board_sampler.sh"
DEVICE_SCRIPT = f"{board.DEVICE_MODELS}/board_sampler.sh"
CLK_TCK = 100                       # CITED: proc(5), USER_HZ; the probe reports the board's
PORT_LANE = {**{v: k for k, v in board.LANE_PORT.items()}, board.BEV_PORT: "bev"}
_CPU_KEYS, _NPU_KEYS = board._CPU_KEYS, board._NPU_KEYS


# ------------------------------------------------------------------- board
def push_script(serial: str = "") -> str:
    """Push the sampler and check its sha256 on the board (project rule)."""
    local = hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
    board._adb("push", str(SCRIPT), DEVICE_SCRIPT, serial=serial)
    out = board._adb("shell", f"sha256sum {DEVICE_SCRIPT}", serial=serial).stdout.split()
    if not out or out[0] != local:
        raise RuntimeError(f"board_sampler.sh sha256 mismatch on the board: {out[:1]} vs {local}")
    return local


def start(stem: str, serial: str = "", period_s: float = 1.0) -> dict:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = f"{board.DEVICE_LOGS}/sampler_{stem}_{stamp}.txt"
    stop = f"{board.DEVICE_LOGS}/sampler_{stem}_{stamp}.stop"
    sha = push_script(serial)
    board._adb("shell", f"mkdir -p {board.DEVICE_LOGS}", serial=serial)
    board._adb("shell", f"nohup sh {DEVICE_SCRIPT} {out} {stop} {period_s} > /dev/null 2>&1 &",
               serial=serial)
    return {"out": out, "stop": stop, "sha256": sha, "started_laptop_time": board.laptop_time()}


def stop(handle: dict, local_path: Path, serial: str = "") -> dict:
    """Create the stop file, wait for the loop to see it, pull and parse."""
    board._adb("shell", f"touch {handle['stop']}", serial=serial)
    time.sleep(2.5)
    board._adb("pull", handle["out"], str(local_path), serial=serial)
    if not local_path.exists():
        return {"error": f"sample file not pulled: {handle['out']}"}
    return parse(local_path.read_text())


def probe(serial: str = "") -> dict:
    """What this board exposes to adb: CLK_TCK, readable power supplies,
    devfreq devices (an NPU / cDSP counter would show here), thermal types."""
    sh = lambda c: board._adb("shell", c, serial=serial).stdout.strip()   # noqa: E731
    return {"clk_tck": sh("getconf CLK_TCK 2>/dev/null"),
            "power_supply": sh("for p in /sys/class/power_supply/*; do echo $(basename $p) "
                               "$( [ -r $p/current_now ] && echo current) "
                               "$( [ -r $p/voltage_now ] && echo voltage); done"),
            "devfreq": sh("ls /sys/class/devfreq 2>/dev/null"),
            "thermal_types": sh("cat /sys/class/thermal/thermal_zone*/type 2>/dev/null | sort -u"),
            "pidof": sh("pidof llama-server bev-decide"),
            "laptop_time": board.laptop_time()}


# ------------------------------------------------------------------- parse
def _blocks(text: str):
    blk = None
    for ln in text.splitlines():
        p = ln.split()
        if not p:
            continue
        if p[0] == "T":
            if blk:
                yield blk
            blk = {"t": float(p[1]), "C": None, "P": [], "S": None, "F": {}, "Z": [], "W": []}
        elif blk is None:
            continue
        elif p[0] == "C" and len(p) >= 6:
            blk["C"] = [int(x) for x in p[2:]]                  # after "C cpu"
        elif p[0] == "P" and len(p) >= 7:
            blk["P"].append((p[1], int(p[2]), p[3], int(p[4]) + int(p[5]), int(p[6])))
        elif p[0] == "S" and len(p) >= 6:
            blk["S"] = sum(int(x) for x in p[2:6])
        elif p[0] == "F" and len(p) == 3:
            blk["F"][p[1]] = int(p[2])
        elif p[0] == "Z" and len(p) == 3:
            try:
                blk["Z"].append((p[1], board._to_c(int(p[2]))))
            except ValueError:
                pass
        elif p[0] == "W" and len(p) == 4:
            blk["W"].append((p[1], int(p[2]), int(p[3])))
    if blk:
        yield blk


def parse(text: str, clk_tck: int = CLK_TCK) -> dict:
    b = list(_blocks(text))
    if len(b) < 2:
        return {"samples": len(b), "error": "fewer than two samples"}
    dur = b[-1]["t"] - b[0]["t"]
    procs: dict[str, dict] = {}
    for blk in b:
        for name, pid, port, ticks, rss in blk["P"]:
            key = PORT_LANE.get(int(port), f"{name}:{port}") if port.isdigit() else f"{name}:{pid}"
            d = procs.setdefault(key, {"name": name, "pid": pid, "first": ticks, "last": ticks,
                                       "peak_rss_kb": rss})
            if pid != d["pid"]:                     # restarted mid-episode: keep the newest
                d.update(pid=pid, first=ticks, restarted=True)
            d["last"] = ticks
            d["peak_rss_kb"] = max(d["peak_rss_kb"], rss)
    per = {k: {"process": d["name"], "cpu_s": round((d["last"] - d["first"]) / clk_tck, 2),
               "cores_busy_mean": round((d["last"] - d["first"]) / clk_tck / dur, 3) if dur else None,
               "peak_rss_mb": round(d["peak_rss_kb"] / 1024, 1),
               **({"restarted": True} if d.get("restarted") else {})}
           for k, d in sorted(procs.items())}
    cs = [blk["C"] for blk in b if blk["C"]]
    busy = None
    if len(cs) >= 2:
        tot = sum(cs[-1]) - sum(cs[0])
        idle = (cs[-1][3] + cs[-1][4]) - (cs[0][3] + cs[0][4])      # idle + iowait
        busy = round(100 * (tot - idle) / tot, 1) if tot else None
    freq = {}
    for pol in sorted({k for blk in b for k in blk["F"]}):
        v = [blk["F"][pol] / 1000 for blk in b if pol in blk["F"]]
        freq[pol] = {"mean_mhz": round(sum(v) / len(v), 1), "max_mhz": round(max(v), 1)}
    zones = [z for blk in b for z in blk["Z"]]
    temps = {k: v for k, v in board.summarise(zones).items() if k != "t"}
    power = {}
    for i in range(1, len(b)):
        dt = b[i]["t"] - b[i - 1]["t"]
        for sup, ua, uv in b[i]["W"]:
            w = abs(ua) * 1e-6 * uv * 1e-6                       # uA x uV -> W
            d = power.setdefault(sup, {"energy_j": 0.0, "w": []})
            d["energy_j"] += w * dt
            d["w"].append(w)
    power = {k: {"supply_energy_j": round(v["energy_j"], 2),
                 "mean_w": round(sum(v["w"]) / len(v["w"]), 3)} for k, v in power.items()}
    sv = [blk["S"] for blk in b if blk["S"] is not None]
    return {"samples": len(b), "duration_s": round(dur, 1), "clk_tck": clk_tck,
            "processes": per, "cpu_busy_pct": busy, "freq": freq, "temps": temps,
            "supply_power": power or None,
            "sampler_cpu_s": round((sv[-1] - sv[0]) / clk_tck, 2) if len(sv) >= 2 else None,
            "npu_counter": None}


def main(argv=None) -> int:
    a = (argv if argv is not None else sys.argv[1:])
    if a[:1] == ["probe"]:
        print(json.dumps(probe(), indent=1))
    elif a[:1] == ["parse"] and len(a) == 2:
        print(json.dumps(parse(Path(a[1]).read_text()), indent=1))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
