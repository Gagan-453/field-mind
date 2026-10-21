# Benchmark comparison: bevideas_B_explain vs bevideas_B_explain_bevcpu

Baseline **bevideas_B_explain**. 10 episodes in common: dev_A01_fcv_seize, dev_A02_fcv_seize_fast, dev_B01_tube_leak, dev_B02_tube_leak_fast, dev_C01_wet_coal, dev_C02_feeder_trip, dev_D01_high_cv_coal, dev_D03_high_cv_severe, dev_N01_normal, dev_N02_normal. Stage times are LAPTOP times (agent code runs on the laptop until Phase 4); model call times are as the client saw them. All plant data is synthetic.

| test | settings |
|---|---|
| bevideas_B_explain | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `explain=on`, backend llamaserver |
| bevideas_B_explain_bevcpu | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `explain=on`, backend llamaserver |

## Headline

| metric | bevideas_B_explain | bevideas_B_explain_bevcpu | bevideas_B_explain_bevcpu − bevideas_B_explain |
|---|---|---|---|
| episodes | 10 | 10 | 0 |
| ticks | 1,380 | 1,380 | 0 |
| wall_s | 913 | 1505.9 | 592.9 |
| decode_tokens | 4,221 | 4,201 | -20 |
| decode_per_tick | 3.06 | 3.04 | -0.02 |
| library group top-1 | 0.772 | 0.774 | 0.002 |
| library top-1 | 0.605 | 0.608 | 0.003 |
| belief group top-1 (code only) | 0.655 | 0.655 | 0 |
| held-out group top-1 | 0.549 | 0.569 | 0.02 |
| faithfulness | 0.973 | 0.973 | 0 |
| citation relevance | 0.642 | 0.643 | 0.001 |
| actions precision | 0.474 | 0.478 | 0.004 |
| actions recall | 0.969 | 0.969 | 0 |
| model invocation rate | 0.286 | 0.285 | -0.001 |

## Time per stage, ms per tick it ran (LAPTOP)

Each blackboard step's own time; a model agent's step includes its call. Hard path = sensor, triage, retriever, gate, scheduler.

| stage | bevideas_B_explain mean / p95 / max | bevideas_B_explain_bevcpu mean / p95 / max |
|---|---|---|
| gate (hard path) | 0.293 / 0.659 / 1.104 (1380) | 0.167 / 0.532 / 1.151 (1380) |
| retriever (hard path) | 0.389 / 0.47 / 0.722 (812) | 0.237 / 0.387 / 0.838 (812) |
| scheduler (hard path) | 0.282 / 0.576 / 0.995 (812) | 0.172 / 0.423 / 0.607 (812) |
| sensor (hard path) | 0.964 / 1.653 / 4.18 (1380) | 0.594 / 0.94 / 2.057 (1380) |
| triage (hard path) | 0.019 / 0.029 / 0.077 (1380) | 0.011 / 0.021 / 0.035 (1380) |
| bev | 694.345 / 958.017 / 1065.84 (402) | 2103.15 / 3527.76 / 4515.05 (402) |
| diagnostician | 1224.1 / 1365.42 / 2414.91 (403) | 1337.64 / 1625.66 / 2374.36 (403) |
| verifier | 1908.74 / 2139.96 / 2197.97 (39) | 2119.89 / 2659.93 / 2714.05 (38) |
| whole tick | 661.32 / 2347.31 | 1091.06 / 4830.77 |

## Model calls per agent @ lane

answers = envelopes; stand-ins = bev answering in that agent's place (no call of its own). Read = prefill. bev decodes nothing.

**bevideas_B_explain**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| bev_explain@bev | 405 | 405 | 0 | 279,689 | 0 | 279.04 | 195.51 | 0 | 5.14 / 195.51 / 75.14 |
| diagnostician@npu | 406 | 406 | 0 | 268,180 | 3,231 | 493.18 | 312.04 | 163.83 | – / – / – |
| verifier@cpu | 39 | 39 | 0 | 16,397 | 990 | 74.43 | 46.08 | 26.8 | – / – / – |

**bevideas_B_explain_bevcpu**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| bev_explain@bev | 405 | 405 | 0 | 280,308 | 0 | 845.4 | 809.83 | 0 | 2.74 / 809.83 / 30.39 |
| diagnostician@npu | 406 | 406 | 0 | 268,180 | 3,238 | 538.97 | 338.89 | 183.28 | – / – / – |
| verifier@cpu | 38 | 38 | 0 | 15,890 | 963 | 80.55 | 51.32 | 27.86 | – / – / – |

## Lane busy share (measured call time / episode wall time)

| lane | bevideas_B_explain | bevideas_B_explain_bevcpu |
|---|---|---|
| bev | 279 s (0.306) | 845.4 s (0.561) |
| cpu | 74.4 s (0.082) | 80.5 s (0.053) |
| npu | 493.2 s (0.54) | 539 s (0.358) |

## Board resources (bench/board_sampler.py)

CPU s = utime + stime of the process; cores busy = CPU s / sampled time. NPU: no hardware counter is read; the NPU lane's work is its call time above. Supply energy is the power supply's, not the chip's, and `–` when the board does not expose it.

| | bevideas_B_explain | bevideas_B_explain_bevcpu |
|---|---|---|
| bev: CPU s / cores busy / peak RSS MB | 130 / 0.137 / 1198.2 | 4585.9 / 2.971 / 1675.3 |
| cpu: CPU s / cores busy / peak RSS MB | 395.3 / 0.415 / 1562.2 | 431 / 0.279 / 1562 |
| npu: CPU s / cores busy / peak RSS MB | 444.9 / 0.467 / 539.2 | 461 / 0.299 / 543 |
| episodes_sampled | 10 | 10 |
| board_cpu_busy_pct_mean | 24.4 | 47.8 |
| cpu_max_c | 97.3 | 97.7 |
| npu_max_c | 96.9 | 96.5 |
| supply_energy_j | – | – |
| sampler_cpu_s | 746.97 | 1146.12 |

## bev ideas

**bevideas_B_explain**: explain=on

| idea | calls | failed | rejected | used | shadow | other |
|---|---|---|---|---|---|---|
| explain | 405 | 0 | 0 | 405 | 0 | over_limit 0 |

**bevideas_B_explain_bevcpu**: explain=on

| idea | calls | failed | rejected | used | shadow | other |
|---|---|---|---|---|---|---|
| explain | 405 | 0 | 0 | 405 | 0 | over_limit 0 |

