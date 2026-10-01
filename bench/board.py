"""
Board helpers for runs that use the QIDK's llama-server lanes (Phase 0b).
Host side only: shells out to adb and talks HTTP to the forwarded lanes.

  chip_temperature()       every thermal zone (type, degC), plus the max over
                           CPU-named and NPU-named zones. Zones are discovered on
                           the board, not assumed.
  lane_health(url)         True when llama-server's /health says ok.
  lane_speed(url, prompt)  one call; prefill/decode tok/s from the server's own
                           `timings` block (never estimated).
  decode_rate_wallclock()  decode tok/s from CLIENT wall clock by differencing
                           two calls that differ only in max_tokens: an
                           independent route to the same quantity, used to
                           re-derive the server's predicted_per_second.

  .venv/bin/python -m bench.board temp
  .venv/bin/python -m bench.board speed http://localhost:8080 [prompt_file]
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request

# Qualcomm thermal zone type names: CPU clusters are cpu*/cpuss*; the Hexagon
# NPU/DSP shows as nsp*, cdsp*, q6* depending on the kernel. Recorded raw too.
_CPU_KEYS = ("cpu",)
_NPU_KEYS = ("nsp", "cdsp", "q6", "npu")

_ZONE_CMD = ('for z in /sys/class/thermal/thermal_zone*; do '
             'echo "$(cat $z/type 2>/dev/null) $(cat $z/temp 2>/dev/null)"; done')


def _to_c(v: int) -> float:
    # sysfs thermal reports millidegrees C (kernel ABI, Documentation/ABI/testing/
    # sysfs-class-thermal); a few vendor zones report degrees. >= 1000 => milli.
    return v / 1000.0 if abs(v) >= 1000 else float(v)


def parse_zones(text: str) -> list[tuple[str, float]]:
    out = []
    for ln in text.splitlines():
        parts = ln.split()
        if len(parts) != 2:
            continue
        try:
            out.append((parts[0], _to_c(int(parts[1]))))
        except ValueError:
            continue
    return out


def summarise(zones: list[tuple[str, float]]) -> dict:
    def mx(keys):
        v = [t for name, t in zones if any(k in name.lower() for k in keys)
             and -20.0 < t < 150.0]
        return round(max(v), 1) if v else None
    return {"t": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "cpu_max_c": mx(_CPU_KEYS), "npu_max_c": mx(_NPU_KEYS),
            "n_zones": len(zones)}


def chip_temperature(adb_serial: str = "", raw: bool = False) -> dict:
    cmd = ["adb"] + (["-s", adb_serial] if adb_serial else []) + ["shell", _ZONE_CMD]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"error": str(e)}
    zones = parse_zones(p.stdout)
    out = summarise(zones)
    if raw:
        out["zones"] = zones
    return out


def lane_health(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/health", timeout=5) as r:
            return json.loads(r.read().decode()).get("status") == "ok"
    except Exception:
        return False


def _chat(url: str, prompt: str, max_tokens: int, timeout: float = 300) -> tuple[dict, float]:
    body = {"messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
            "temperature": 0.0, "seed": 0, "cache_prompt": False, "stream": False}
    req = urllib.request.Request(f"{url.rstrip('/')}/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode())
    return data, (time.perf_counter() - t0) * 1000


def lane_speed(url: str, prompt: str, max_tokens: int = 64) -> dict:
    data, wall = _chat(url, prompt, max_tokens)
    tm = data.get("timings") or {}
    out = {"url": url, "model": data.get("model"),
           "prompt_tokens": tm.get("prompt_n"), "decode_tokens": tm.get("predicted_n"),
           "prefill_tok_s": tm.get("prompt_per_second"),
           "decode_tok_s": tm.get("predicted_per_second"),
           "ttft_ms_server": tm.get("prompt_ms"), "wall_ms": round(wall, 1)}
    # a field the server did not send stays None and is listed, never filled
    out["missing"] = [k for k, v in out.items() if v is None]
    return out


def mean_rates(samples: list[dict]) -> dict:
    """Mean of each lane_speed() rate field over several calls, skipping None;
    reports how many samples were missing each field."""
    out = {}
    for k in ("prompt_tokens", "decode_tokens", "prefill_tok_s", "decode_tok_s",
              "ttft_ms_server"):
        vals = [s[k] for s in samples if s.get(k) is not None]
        out[k] = round(sum(vals) / len(vals), 2) if vals else None
        out[f"{k}_missing"] = len(samples) - len(vals)
    out["n"] = len(samples)
    return out


def decode_rate_wallclock(url: str, prompt: str, n1: int = 16, n2: int = 80) -> dict:
    """(t2 - t1) / (d2 - d1) from client wall clock. The prompt is identical, so
    the prefill and HTTP overhead cancel; only the extra decoded tokens remain.
    Uses predicted_n only to know how many tokens were actually decoded (a call
    can stop early at EOS), not the server's timing."""
    d1, w1 = _chat(url, prompt, n1)
    d2, w2 = _chat(url, prompt, n2)
    k1 = (d1.get("timings") or {}).get("predicted_n")
    k2 = (d2.get("timings") or {}).get("predicted_n")
    ok = k1 is not None and k2 is not None and k2 > k1 and w2 > w1
    rate = (k2 - k1) / ((w2 - w1) / 1000) if ok else None   # None if a count is missing
    return {"decoded": [k1, k2], "wall_ms": [round(w1, 1), round(w2, 1)],
            "decode_tok_s_wallclock": round(rate, 2) if rate else None,
            "decode_tok_s_server": (d2.get("timings") or {}).get("predicted_per_second")}


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "temp":
        print(json.dumps(chip_temperature(raw=True), indent=1))
    elif len(sys.argv) >= 3 and sys.argv[1] == "speed":
        pr = open(sys.argv[3]).read() if len(sys.argv) > 3 else "Say hello in five words."
        print(json.dumps(lane_speed(sys.argv[2], pr), indent=1))
    else:
        print(__doc__)
