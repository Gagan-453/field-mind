# Benchmark comparison: bevideas_A3 vs bevideas_C_combo_r1

Baseline **bevideas_A3**. 10 episodes in common: dev_A01_fcv_seize, dev_A02_fcv_seize_fast, dev_B01_tube_leak, dev_B02_tube_leak_fast, dev_C01_wet_coal, dev_C02_feeder_trip, dev_D01_high_cv_coal, dev_D03_high_cv_severe, dev_N01_normal, dev_N02_normal. Stage times are LAPTOP times (agent code runs on the laptop until Phase 4); model call times are as the client saw them. All plant data is synthetic.

| test | settings |
|---|---|
| bevideas_A3 | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `off`, backend llamaserver |
| bevideas_C_combo_r1 | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `explain=on,clear_skip=on,verifier=on`, backend llamaserver |

## Headline

| metric | bevideas_A3 | bevideas_C_combo_r1 | bevideas_C_combo_r1 − bevideas_A3 |
|---|---|---|---|
| episodes | 10 | 10 | 0 |
| ticks | 1,380 | 1,380 | 0 |
| wall_s | 1372.1 | 744.1 | -628 |
| decode_tokens | 14,765 | 2,855 | -11,910 |
| decode_per_tick | 10.7 | 2.07 | -8.63 |
| library group top-1 | 0.759 | 0.775 | 0.016 |
| library top-1 | 0.646 | 0.609 | -0.037 |
| belief group top-1 (code only) | 0.655 | 0.655 | 0 |
| held-out group top-1 | 0.471 | 0.549 | 0.078 |
| faithfulness | 0.973 | 0.973 | 0 |
| citation relevance | 0.658 | 0.642 | -0.016 |
| actions precision | 0.489 | 0.479 | -0.01 |
| actions recall | 0.969 | 0.969 | 0 |
| model invocation rate | 0.287 | 0.257 | -0.03 |

## Time per stage, ms per tick it ran (LAPTOP)

Each blackboard step's own time; a model agent's step includes its call. Hard path = sensor, triage, retriever, gate, scheduler.

| stage | bevideas_A3 mean / p95 / max | bevideas_C_combo_r1 mean / p95 / max |
|---|---|---|
| gate (hard path) | 0.138 / 0.293 / 0.606 (1380) | 0.142 / 0.321 / 0.702 (1380) |
| retriever (hard path) | 0.214 / 0.25 / 0.44 (812) | 0.215 / 0.248 / 0.578 (812) |
| scheduler (hard path) | 0.181 / 0.37 / 1.21 (812) | 0.144 / 0.304 / 0.591 (812) |
| sensor (hard path) | 0.54 / 0.898 / 1.47 (1380) | 0.567 / 0.901 / 1.361 (1380) |
| triage (hard path) | 0.01 / 0.014 / 0.032 (1380) | 0.011 / 0.015 / 0.041 (1380) |
| bev | – | 737.006 / 1088.28 / 1821.8 (368) |
| diagnostician | 3119.05 / 3914.7 / 6136.57 (403) | 1224.48 / 1386.76 / 2473.6 (356) |
| verifier | 2008.58 / 2425.52 / 3000.05 (41) | – |
| whole tick | 994.157 / 3833.81 | 539.071 / 2291.41 |

## Model calls per agent @ lane

answers = envelopes; stand-ins = bev answering in that agent's place (no call of its own). Read = prefill. bev decodes nothing.

**bevideas_A3**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| diagnostician@npu | 406 | 406 | 0 | 293,352 | 13,727 | 1256.88 | 356.99 | 883.24 | – / – / – |
| verifier@cpu | 41 | 41 | 0 | 17,053 | 1,038 | 82.34 | 51.86 | 29.01 | – / – / – |

**bevideas_C_combo_r1**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| bev_explain@bev | 357 | 357 | 0 | 241,729 | 0 | 243.15 | 170.32 | 0 | 4.2 / 170.32 / 66.45 |
| bev_verifier@bev | 59 | 59 | 0 | 22,900 | 0 | 28.01 | 18.99 | 0 | 0.32 / 18.99 / 8.3 |
| diagnostician@npu | 359 | 359 | 0 | 236,965 | 2,855 | 435.83 | 277.7 | 143.56 | – / – / – |
| verifier@bev | 37 | 0 | 37 | 0 | 0 | 0 | 0 | 0 | – / – / – |

## Lane busy share (measured call time / episode wall time)

| lane | bevideas_A3 | bevideas_C_combo_r1 |
|---|---|---|
| bev | 0 s (0) | 271.2 s (0.364) |
| cpu | 82.3 s (0.06) | 0 s (0) |
| npu | 1256.9 s (0.916) | 435.8 s (0.586) |

## Board resources (bench/board_sampler.py)

CPU s = utime + stime of the process; cores busy = CPU s / sampled time. NPU: no hardware counter is read; the NPU lane's work is its call time above. Supply energy is the power supply's, not the chip's, and `–` when the board does not expose it.

| | bevideas_A3 | bevideas_C_combo_r1 |
|---|---|---|
| bev: CPU s / cores busy / peak RSS MB | 0.4 / 0 / 763.9 | 127.5 / 0.163 / 584.7 |
| cpu: CPU s / cores busy / peak RSS MB | 436.5 / 0.31 / 1568.9 | 0.9 / 0.001 / 1475.6 |
| npu: CPU s / cores busy / peak RSS MB | 1861.2 / 1.322 / 546 | 393.5 / 0.503 / 539.8 |
| episodes_sampled | 10 | 10 |
| board_cpu_busy_pct_mean | 30.1 | 21.2 |
| cpu_max_c | 96.1 | 79.1 |
| npu_max_c | 96.9 | 96.9 |
| supply_energy_j | – | – |
| sampler_cpu_s | 1043.61 | 617.21 |

## bev ideas

**bevideas_A3**: every bev idea off.

**bevideas_C_combo_r1**: explain=on, verifier=on, clear_skip=on

| idea | calls | failed | rejected | used | shadow | other |
|---|---|---|---|---|---|---|
| clear_skip | 0 | 0 | 0 | 99 | 0 | – |
| explain | 357 | 0 | 0 | 357 | 0 | over_limit 0 |
| verifier | 59 | 0 | 0 | 37 | 0 | over_limit 0 |

