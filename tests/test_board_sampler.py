"""bench/board_sampler.py: the parse of the on-board sample file, on a
hand-written file whose answers are worked out by hand below."""
from bench.board_sampler import parse

# 3 samples, 2 s apart. NPU llama-server (port 8080): 0 -> 150 -> 400 ticks;
# bev-decide (8082): 10 -> 10 -> 60; RSS peaks 2,048,000 kB and 900,000 kB.
# /proc/stat totals: +1000 jiffies per step, idle+iowait +600 (iowait +100 of it)
# -> busy 40 % (50 % if iowait were counted as busy).
# Supply: 1.5 A x 4.0 V = 6 W for 2 x 2 s -> 24 J. Sampler: 4 -> 10 ticks.
SAMPLE = """\
T 100.0 50.0
C cpu 1000 0 1000 5000 0 0 0 0 0 0
P llama-server 11 8080 0 0 2000000
P bev-decide 13 8082 5 5 900000
S 99 1 1 1 1
F policy0 1800000
Z cpu-0-0 45000
Z nsp0 50000
T 102.0 51.0
C cpu 1200 0 1200 5500 100 0 0 0 0 0
P llama-server 11 8080 100 50 2048000
P bev-decide 13 8082 5 5 900000
S 99 2 2 1 1
F policy0 2200000
Z cpu-0-0 61000
Z nsp0 58000
W battery 1500000 4000000
T 104.0 52.0
C cpu 1400 0 1400 6000 200 0 0 0 0 0
P llama-server 11 8080 250 150 1024000
P bev-decide 13 8082 30 30 800000
S 99 3 3 2 2
F policy0 2000000
Z cpu-0-0 55000
Z nsp0 52000
W battery -1500000 4000000
"""


def test_parse_per_process_cpu_rss_and_board_load():
    r = parse(SAMPLE)
    assert r["samples"] == 3 and r["duration_s"] == 4.0
    npu, bev = r["processes"]["npu"], r["processes"]["bev"]
    assert npu["cpu_s"] == 4.0 and npu["peak_rss_mb"] == 2000.0       # 400 ticks / 100
    assert npu["cores_busy_mean"] == 1.0                               # 4 s of CPU in 4 s
    assert bev["cpu_s"] == 0.5 and bev["peak_rss_mb"] == 878.9
    assert r["cpu_busy_pct"] == 40.0
    assert r["freq"]["policy0"] == {"mean_mhz": 2000.0, "max_mhz": 2200.0}
    assert r["temps"]["cpu_max_c"] == 61.0 and r["temps"]["npu_max_c"] == 58.0
    assert r["sampler_cpu_s"] == 0.06


def test_parse_supply_energy_and_its_absence():
    r = parse(SAMPLE)
    assert r["supply_power"]["battery"] == {"supply_energy_j": 24.0, "mean_w": 6.0}
    no_w = "\n".join(l for l in SAMPLE.splitlines() if not l.startswith("W"))
    assert parse(no_w)["supply_power"] is None and parse(no_w)["npu_counter"] is None


def test_parse_needs_two_samples_and_follows_a_restart():
    assert "error" in parse(SAMPLE.split("T 102.0")[0])
    restarted = SAMPLE.replace("P llama-server 11 8080 250 150", "P llama-server 12 8080 20 10")
    r = parse(restarted)
    assert r["processes"]["npu"]["restarted"] and r["processes"]["npu"]["cpu_s"] == 0.0
