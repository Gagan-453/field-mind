# Benchmark comparison: bevideas_A3 vs bevideas_A_meas vs bevideas_B_explain_meas

Baseline **bevideas_A3**. 10 episodes in common: dev_A01_fcv_seize, dev_A02_fcv_seize_fast, dev_B01_tube_leak, dev_B02_tube_leak_fast, dev_C01_wet_coal, dev_C02_feeder_trip, dev_D01_high_cv_coal, dev_D03_high_cv_severe, dev_N01_normal, dev_N02_normal. Stage times are LAPTOP times (agent code runs on the laptop until Phase 4); model call times are as the client saw them. All plant data is synthetic.

| test | settings |
|---|---|
| bevideas_A3 | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `off`, backend llamaserver |
| bevideas_A_meas | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `off`, backend llamaserver |
| bevideas_B_explain_meas | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `explain=on`, backend llamaserver |

## Headline

| metric | bevideas_A3 | bevideas_A_meas | bevideas_B_explain_meas | bevideas_A_meas − bevideas_A3 | bevideas_B_explain_meas − bevideas_A3 |
|---|---|---|---|---|---|
| episodes | 10 | 10 | 10 | 0 | 0 |
| ticks | 1,380 | 1,380 | 1,380 | 0 | 0 |
| wall_s | 1372.1 | 1358 | 872.8 | -14.1 | -499.3 |
| decode_tokens | 14,765 | 14,746 | 4,195 | -19 | -10,570 |
| decode_per_tick | 10.7 | 10.69 | 3.04 | -0.01 | -7.66 |
| library group top-1 | 0.759 | 0.759 | 0.774 | 0 | 0.015 |
| library top-1 | 0.646 | 0.646 | 0.608 | 0 | -0.038 |
| belief group top-1 (code only) | 0.655 | 0.655 | 0.655 | 0 | 0 |
| held-out group top-1 | 0.471 | 0.471 | 0.549 | 0 | 0.078 |
| faithfulness | 0.973 | 0.973 | 0.973 | 0 | 0 |
| citation relevance | 0.658 | 0.659 | 0.641 | 0.001 | -0.017 |
| actions precision | 0.489 | 0.489 | 0.473 | 0 | -0.016 |
| actions recall | 0.969 | 0.969 | 0.969 | 0 | 0 |
| model invocation rate | 0.287 | 0.287 | 0.285 | 0 | -0.002 |

## Time per stage, ms per tick it ran (LAPTOP)

Each blackboard step's own time; a model agent's step includes its call. Hard path = sensor, triage, retriever, gate, scheduler.

| stage | bevideas_A3 mean / p95 / max | bevideas_A_meas mean / p95 / max | bevideas_B_explain_meas mean / p95 / max |
|---|---|---|---|
| gate (hard path) | 0.138 / 0.293 / 0.606 (1380) | 0.138 / 0.292 / 0.445 (1380) | 0.143 / 0.32 / 0.57 (1380) |
| retriever (hard path) | 0.214 / 0.25 / 0.44 (812) | 0.214 / 0.246 / 0.351 (812) | 0.212 / 0.241 / 0.658 (812) |
| scheduler (hard path) | 0.181 / 0.37 / 1.21 (812) | 0.181 / 0.374 / 1.542 (812) | 0.152 / 0.303 / 0.486 (812) |
| sensor (hard path) | 0.54 / 0.898 / 1.47 (1380) | 0.537 / 0.898 / 1.746 (1380) | 0.54 / 0.89 / 1.743 (1380) |
| triage (hard path) | 0.01 / 0.014 / 0.032 (1380) | 0.01 / 0.014 / 0.037 (1380) | 0.01 / 0.014 / 0.027 (1380) |
| bev | – | – | 694.452 / 962.769 / 1201.23 (402) |
| diagnostician | 3119.05 / 3914.7 / 6136.57 (403) | 3090.6 / 3907.65 / 6151.64 (403) | 1205.85 / 1358.32 / 2345.99 (403) |
| verifier | 2008.58 / 2425.52 / 3000.05 (41) | 1947.55 / 2299.22 / 2352.12 (41) | 1859.88 / 2237.05 / 2398.35 (38) |
| whole tick | 994.157 / 3833.81 | 983.947 / 3794.22 | 632.263 / 2293.99 |

## Model calls per agent @ lane

answers = envelopes; stand-ins = bev answering in that agent's place (no call of its own). Read = prefill. bev decodes nothing.

**bevideas_A3**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| diagnostician@npu | 406 | 406 | 0 | 293,352 | 13,727 | 1256.88 | 356.99 | 883.24 | – / – / – |
| verifier@cpu | 41 | 41 | 0 | 17,053 | 1,038 | 82.34 | 51.86 | 29.01 | – / – / – |

**bevideas_A_meas**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| diagnostician@npu | 406 | 406 | 0 | 293,352 | 13,708 | 1245.41 | 351.05 | 877.62 | – / – / – |
| verifier@cpu | 41 | 41 | 0 | 17,053 | 1,038 | 79.84 | 49.76 | 28.64 | – / – / – |

**bevideas_B_explain_meas**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| bev_explain@bev | 405 | 405 | 0 | 279,698 | 0 | 279.11 | 195.96 | 0 | 4.89 / 195.96 / 75.62 |
| diagnostician@npu | 406 | 406 | 0 | 268,180 | 3,231 | 485.87 | 302.49 | 166.84 | – / – / – |
| verifier@cpu | 38 | 38 | 0 | 15,815 | 964 | 70.67 | 43.56 | 25.63 | – / – / – |

## Lane busy share (measured call time / episode wall time)

| lane | bevideas_A3 | bevideas_A_meas | bevideas_B_explain_meas |
|---|---|---|---|
| bev | 0 s (0) | 0 s (0) | 279.1 s (0.32) |
| cpu | 82.3 s (0.06) | 79.8 s (0.059) | 70.7 s (0.081) |
| npu | 1256.9 s (0.916) | 1245.4 s (0.917) | 485.9 s (0.557) |

## Board resources (bench/board_sampler.py)

CPU s = utime + stime of the process; cores busy = CPU s / sampled time. NPU: no hardware counter is read; the NPU lane's work is its call time above. Supply energy is the power supply's, not the chip's, and `–` when the board does not expose it.

| | bevideas_A3 | bevideas_A_meas | bevideas_B_explain_meas |
|---|---|---|---|
| bev: CPU s / cores busy / peak RSS MB | 0.4 / 0 / 763.9 | 0.4 / 0 / 763.1 | 130.6 / 0.143 / 963.4 |
| cpu: CPU s / cores busy / peak RSS MB | 436.5 / 0.31 / 1568.9 | 424.9 / 0.304 / 1560.5 | 375 / 0.411 / 1576.7 |
| npu: CPU s / cores busy / peak RSS MB | 1861.2 / 1.322 / 546 | 1870.3 / 1.337 / 541.5 | 449.8 / 0.493 / 535.6 |
| episodes_sampled | 10 | 10 | 10 |
| board_cpu_busy_pct_mean | 30.1 | 30.4 | 24.9 |
| cpu_max_c | 96.1 | 96.9 | 96.9 |
| npu_max_c | 96.9 | 97.3 | 96.5 |
| supply_energy_j | – | – | – |
| sampler_cpu_s | 1043.61 | 1032.47 | 714.25 |

## bev ideas

**bevideas_A3**: every bev idea off.

**bevideas_A_meas**: every bev idea off.

**bevideas_B_explain_meas**: explain=on

| idea | calls | failed | rejected | used | shadow | other |
|---|---|---|---|---|---|---|
| explain | 405 | 0 | 0 | 405 | 0 | over_limit 0 |

