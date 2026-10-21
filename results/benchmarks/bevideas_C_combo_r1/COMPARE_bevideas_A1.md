# Benchmark comparison: bevideas_A1 vs bevideas_B_explain vs bevideas_B_skip vs bevideas_B_verifier vs bevideas_C_combo_r1

Baseline **bevideas_A1**, second baseline run **bevideas_A3**. 10 episodes in common: dev_A01_fcv_seize, dev_A02_fcv_seize_fast, dev_B01_tube_leak, dev_B02_tube_leak_fast, dev_C01_wet_coal, dev_C02_feeder_trip, dev_D01_high_cv_coal, dev_D03_high_cv_severe, dev_N01_normal, dev_N02_normal. Stage times are LAPTOP times (agent code runs on the laptop until Phase 4); model call times are as the client saw them. All plant data is synthetic.

| test | settings |
|---|---|
| bevideas_A1 | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `off`, backend llamaserver |
| bevideas_B_explain | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `explain=on`, backend llamaserver |
| bevideas_B_skip | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `clear_skip=on`, backend llamaserver |
| bevideas_B_verifier | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `verifier=on`, backend llamaserver |
| bevideas_C_combo_r1 | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `explain=on,clear_skip=on,verifier=on`, backend llamaserver |
| bevideas_A3 | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `off`, backend llamaserver |

## Headline

| metric | bevideas_A1 | bevideas_B_explain | bevideas_B_skip | bevideas_B_verifier | bevideas_C_combo_r1 | bevideas_A3 | bevideas_B_explain − bevideas_A1 | bevideas_B_skip − bevideas_A1 | bevideas_B_verifier − bevideas_A1 | bevideas_C_combo_r1 − bevideas_A1 |
|---|---|---|---|---|---|---|---|---|---|---|
| episodes | 10 | 10 | 10 | 10 | 10 | 10 | 0 | 0 | 0 | 0 |
| ticks | 1,380 | 1,380 | 1,380 | 1,380 | 1,380 | 1,380 | 0 | 0 | 0 | 0 |
| wall_s | 1350 | 913 | 1248.6 | 1404.8 | 744.1 | 1372.1 | -437 | -101.4 | 54.8 | -605.9 |
| decode_tokens | 14,735 | 4,221 | 12,605 | 13,751 | 2,855 | 14,765 | -10,514 | -2,130 | -984 | -11,880 |
| decode_per_tick | 10.68 | 3.06 | 9.13 | 9.96 | 2.07 | 10.7 | -7.62 | -1.55 | -0.72 | -8.61 |
| library group top-1 | 0.759 | 0.772 | 0.766 | 0.759 | 0.775 | 0.759 | 0.013 | 0.007 | 0 | 0.016 |
| library top-1 | 0.646 | 0.605 | 0.654 | 0.651 | 0.609 | 0.646 | -0.041 | 0.008 | 0.005 | -0.037 |
| belief group top-1 (code only) | 0.655 | 0.655 | 0.655 | 0.655 | 0.655 | 0.655 | 0 | 0 | 0 | 0 |
| held-out group top-1 | 0.451 | 0.549 | 0.471 | 0.451 | 0.549 | 0.471 | 0.098 | 0.02 | 0 | 0.098 |
| faithfulness | 0.972 | 0.973 | 0.973 | 0.972 | 0.973 | 0.973 | 0.001 | 0.001 | 0 | 0.001 |
| citation relevance | 0.657 | 0.642 | 0.665 | 0.654 | 0.642 | 0.658 | -0.015 | 0.008 | -0.003 | -0.015 |
| actions precision | 0.481 | 0.474 | 0.489 | 0.481 | 0.479 | 0.489 | -0.007 | 0.008 | 0 | -0.002 |
| actions recall | 0.938 | 0.969 | 0.969 | 0.938 | 0.969 | 0.969 | 0.031 | 0.031 | 0 | 0.031 |
| model invocation rate | 0.287 | 0.286 | 0.251 | 0.287 | 0.257 | 0.287 | -0.001 | -0.036 | 0 | -0.03 |

Run-to-run spread |A1 − A2|: episodes 0, ticks 0, wall_s 22.1, decode_tokens 30, decode_per_tick 0.02, library group top-1 0, library top-1 0, belief group top-1 (code only) 0, held-out group top-1 0.02, faithfulness 0.001, citation relevance 0.001, actions precision 0.008, actions recall 0.031, model invocation rate 0

## Time per stage, ms per tick it ran (LAPTOP)

Each blackboard step's own time; a model agent's step includes its call. Hard path = sensor, triage, retriever, gate, scheduler.

| stage | bevideas_A1 mean / p95 / max | bevideas_B_explain mean / p95 / max | bevideas_B_skip mean / p95 / max | bevideas_B_verifier mean / p95 / max | bevideas_C_combo_r1 mean / p95 / max |
|---|---|---|---|---|---|
| gate (hard path) | 0.284 / 0.622 / 1.224 (1380) | 0.293 / 0.659 / 1.104 (1380) | 0.255 / 0.581 / 0.752 (1380) | 0.273 / 0.599 / 0.976 (1380) | 0.142 / 0.321 / 0.702 (1380) |
| retriever (hard path) | 0.391 / 0.471 / 1.159 (812) | 0.389 / 0.47 / 0.722 (812) | 0.371 / 0.429 / 0.672 (812) | 0.376 / 0.433 / 0.989 (812) | 0.215 / 0.248 / 0.578 (812) |
| scheduler (hard path) | 0.327 / 0.697 / 2.373 (812) | 0.282 / 0.576 / 0.995 (812) | 0.278 / 0.643 / 2.254 (812) | 0.307 / 0.632 / 2.438 (812) | 0.144 / 0.304 / 0.591 (812) |
| sensor (hard path) | 0.98 / 1.624 / 3.672 (1380) | 0.964 / 1.653 / 4.18 (1380) | 0.935 / 1.568 / 2.361 (1380) | 0.934 / 1.557 / 4.328 (1380) | 0.567 / 0.901 / 1.361 (1380) |
| triage (hard path) | 0.019 / 0.03 / 0.075 (1380) | 0.019 / 0.029 / 0.077 (1380) | 0.017 / 0.025 / 0.038 (1380) | 0.018 / 0.026 / 0.08 (1380) | 0.011 / 0.015 / 0.041 (1380) |
| bev | – | 694.345 / 958.017 / 1065.84 (402) | – | 784.582 / 1014.11 / 1103.09 (41) | 737.006 / 1088.28 / 1821.8 (368) |
| diagnostician | 3007.01 / 3792.42 / 5945.49 (403) | 1224.1 / 1365.42 / 2414.91 (403) | 3252.69 / 4005.06 / 6580.19 (340) | 3259.6 / 4057.06 / 6538.01 (403) | 1224.48 / 1386.76 / 2473.6 (356) |
| verifier | 1928.4 / 2184.68 / 2221.42 (41) | 1908.74 / 2139.96 / 2197.97 (39) | 2089.38 / 2337.07 / 2350 (41) | – | – |
| whole tick | 977.996 / 3689.6 | 661.32 / 2347.31 | 904.496 / 3884.95 | 1017.74 / 3933.84 | 539.071 / 2291.41 |

## Model calls per agent @ lane

answers = envelopes; stand-ins = bev answering in that agent's place (no call of its own). Read = prefill. bev decodes nothing.

**bevideas_A1**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| diagnostician@npu | 406 | 406 | 0 | 293,352 | 13,697 | 1211.68 | 345.39 | 848.83 | – / – / – |
| verifier@cpu | 41 | 41 | 0 | 17,053 | 1,038 | 79.05 | 48.89 | 28.52 | – / – / – |

**bevideas_B_explain**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| bev_explain@bev | 405 | 405 | 0 | 279,689 | 0 | 279.04 | 195.51 | 0 | 5.14 / 195.51 / 75.14 |
| diagnostician@npu | 406 | 406 | 0 | 268,180 | 3,231 | 493.18 | 312.04 | 163.83 | – / – / – |
| verifier@cpu | 39 | 39 | 0 | 16,397 | 990 | 74.43 | 46.08 | 26.8 | – / – / – |

**bevideas_B_skip**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| diagnostician@npu | 343 | 343 | 0 | 247,208 | 11,567 | 1105.8 | 321.11 | 770.1 | – / – / – |
| verifier@cpu | 41 | 41 | 0 | 17,046 | 1,038 | 85.65 | 53.58 | 30.41 | – / – / – |

**bevideas_B_verifier**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| bev_verifier@bev | 67 | 67 | 0 | 25,471 | 0 | 32.15 | 21.74 | 0 | 0.5 / 21.74 / 9.31 |
| diagnostician@npu | 406 | 406 | 0 | 293,352 | 13,751 | 1313.48 | 382.91 | 913.01 | – / – / – |
| verifier@bev | 41 | 0 | 41 | 0 | 0 | 0 | 0 | 0 | – / – / – |

**bevideas_C_combo_r1**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| bev_explain@bev | 357 | 357 | 0 | 241,729 | 0 | 243.15 | 170.32 | 0 | 4.2 / 170.32 / 66.45 |
| bev_verifier@bev | 59 | 59 | 0 | 22,900 | 0 | 28.01 | 18.99 | 0 | 0.32 / 18.99 / 8.3 |
| diagnostician@npu | 359 | 359 | 0 | 236,965 | 2,855 | 435.83 | 277.7 | 143.56 | – / – / – |
| verifier@bev | 37 | 0 | 37 | 0 | 0 | 0 | 0 | 0 | – / – / – |

## Lane busy share (measured call time / episode wall time)

| lane | bevideas_A1 | bevideas_B_explain | bevideas_B_skip | bevideas_B_verifier | bevideas_C_combo_r1 |
|---|---|---|---|---|---|
| bev | 0 s (0) | 279 s (0.306) | 0 s (0) | 32.2 s (0.023) | 271.2 s (0.364) |
| cpu | 79.1 s (0.059) | 74.4 s (0.082) | 85.7 s (0.069) | 0 s (0) | 0 s (0) |
| npu | 1211.7 s (0.898) | 493.2 s (0.54) | 1105.8 s (0.886) | 1313.5 s (0.935) | 435.8 s (0.586) |

## Board resources (bench/board_sampler.py)

CPU s = utime + stime of the process; cores busy = CPU s / sampled time. NPU: no hardware counter is read; the NPU lane's work is its call time above. Supply energy is the power supply's, not the chip's, and `–` when the board does not expose it.

| | bevideas_A1 | bevideas_B_explain | bevideas_B_skip | bevideas_B_verifier | bevideas_C_combo_r1 |
|---|---|---|---|---|---|
| bev: CPU s / cores busy / peak RSS MB | 0.4 / 0 / 967.8 | 130 / 0.137 / 1198.2 | 0.4 / 0 / 1057.9 | 16.1 / 0.011 / 1054.7 | 127.5 / 0.163 / 584.7 |
| cpu: CPU s / cores busy / peak RSS MB | 419.5 / 0.302 / 1570.8 | 395.3 / 0.415 / 1562.2 | 454 / 0.352 / 1557.7 | 1.6 / 0.001 / 1469.4 | 0.9 / 0.001 / 1475.6 |
| npu: CPU s / cores busy / peak RSS MB | 1839.7 / 1.323 / 551.3 | 444.9 / 0.467 / 539.2 | 1608.1 / 1.246 / 535.4 | 1905.1 / 1.312 / 542.5 | 393.5 / 0.503 / 539.8 |
| episodes_sampled | 10 | 10 | 10 | 10 | 10 |
| board_cpu_busy_pct_mean | 29.8 | 24.4 | 29.2 | 26.8 | 21.2 |
| cpu_max_c | 96.9 | 97.3 | 96.9 | 92.7 | 79.1 |
| npu_max_c | 96.5 | 96.9 | 98.1 | 96.9 | 96.9 |
| supply_energy_j | – | – | – | – | – |
| sampler_cpu_s | 1026.95 | 746.97 | 954.69 | 1079.45 | 617.21 |

## bev ideas

**bevideas_A1**: every bev idea off.

**bevideas_B_explain**: explain=on

| idea | calls | failed | rejected | used | shadow | other |
|---|---|---|---|---|---|---|
| explain | 405 | 0 | 0 | 405 | 0 | over_limit 0 |

**bevideas_B_skip**: clear_skip=on

| idea | calls | failed | rejected | used | shadow | other |
|---|---|---|---|---|---|---|
| clear_skip | 0 | 0 | 0 | 118 | 0 | – |

**bevideas_B_verifier**: verifier=on

| idea | calls | failed | rejected | used | shadow | other |
|---|---|---|---|---|---|---|
| verifier | 67 | 0 | 0 | 41 | 0 | over_limit 0 |

**bevideas_C_combo_r1**: explain=on, verifier=on, clear_skip=on

| idea | calls | failed | rejected | used | shadow | other |
|---|---|---|---|---|---|---|
| clear_skip | 0 | 0 | 0 | 99 | 0 | – |
| explain | 357 | 0 | 0 | 357 | 0 | over_limit 0 |
| verifier | 59 | 0 | 0 | 37 | 0 | over_limit 0 |

