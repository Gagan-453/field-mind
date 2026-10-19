# Benchmark comparison: bevideas_A1 vs bevideas_B_explain vs bevideas_B_actions vs bevideas_B_unknown vs bevideas_B_verifier vs bevideas_B_notes vs bevideas_B_skip

Baseline **bevideas_A1**, second baseline run **bevideas_A2**. 10 episodes in common: dev_A01_fcv_seize, dev_A02_fcv_seize_fast, dev_B01_tube_leak, dev_B02_tube_leak_fast, dev_C01_wet_coal, dev_C02_feeder_trip, dev_D01_high_cv_coal, dev_D03_high_cv_severe, dev_N01_normal, dev_N02_normal. Stage times are LAPTOP times (agent code runs on the laptop until Phase 4); model call times are as the client saw them. All plant data is synthetic.

| test | settings |
|---|---|
| bevideas_A1 | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `off`, backend llamaserver |
| bevideas_B_explain | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `explain=on`, backend llamaserver |
| bevideas_B_actions | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `actions=on`, backend llamaserver |
| bevideas_B_unknown | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `unknown=on`, backend llamaserver |
| bevideas_B_verifier | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `verifier=on`, backend llamaserver |
| bevideas_B_notes | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `notes=on`, backend llamaserver |
| bevideas_B_skip | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `clear_skip=on`, backend llamaserver |
| bevideas_A2 | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `off`, backend llamaserver |

## Headline

| metric | bevideas_A1 | bevideas_B_explain | bevideas_B_actions | bevideas_B_unknown | bevideas_B_verifier | bevideas_B_notes | bevideas_B_skip | bevideas_A2 | bevideas_B_explain − bevideas_A1 | bevideas_B_actions − bevideas_A1 | bevideas_B_unknown − bevideas_A1 | bevideas_B_verifier − bevideas_A1 | bevideas_B_notes − bevideas_A1 | bevideas_B_skip − bevideas_A1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| episodes | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 0 |
| ticks | 1,380 | 1,380 | 1,380 | 1,380 | 1,380 | 1,380 | 1,380 | 1,380 | 0 | 0 | 0 | 0 | 0 | 0 |
| wall_s | 1350 | 913 | 1608.8 | 1707.9 | 1404.8 | 1444.1 | 1248.6 | 1498.3 | -437 | 258.8 | 357.9 | 54.8 | 94.1 | -101.4 |
| decode_tokens | 14,735 | 4,221 | 14,739 | 14,793 | 13,751 | 14,538 | 12,605 | 14,722 | -10,514 | 4 | 58 | -984 | -197 | -2,130 |
| decode_per_tick | 10.68 | 3.06 | 10.68 | 10.72 | 9.96 | 10.53 | 9.13 | 10.67 | -7.62 | 0 | 0.04 | -0.72 | -0.15 | -1.55 |
| library group top-1 | 0.759 | 0.772 | 0.759 | 0.77 | 0.759 | 0.759 | 0.766 | 0.759 | 0.013 | 0 | 0.011 | 0 | 0 | 0.007 |
| library top-1 | 0.646 | 0.605 | 0.646 | 0.654 | 0.651 | 0.646 | 0.654 | 0.646 | -0.041 | 0 | 0.008 | 0.005 | 0 | 0.008 |
| belief group top-1 (code only) | 0.655 | 0.655 | 0.655 | 0.655 | 0.655 | 0.655 | 0.655 | 0.655 | 0 | 0 | 0 | 0 | 0 | 0 |
| held-out group top-1 | 0.451 | 0.549 | 0.549 | 0.451 | 0.451 | 0.451 | 0.471 | 0.51 | 0.098 | 0.098 | 0 | 0 | 0 | 0.02 |
| faithfulness | 0.972 | 0.973 | 0.973 | 0.972 | 0.972 | 0.972 | 0.973 | 0.972 | 0.001 | 0.001 | 0 | 0 | 0 | 0.001 |
| citation relevance | 0.657 | 0.642 | 0.66 | 0.659 | 0.654 | 0.666 | 0.665 | 0.656 | -0.015 | 0.003 | 0.002 | -0.003 | 0.009 | 0.008 |
| actions precision | 0.481 | 0.474 | 0.489 | 0.481 | 0.481 | 0.481 | 0.489 | 0.481 | -0.007 | 0.008 | 0 | 0 | 0 | 0.008 |
| actions recall | 0.938 | 0.969 | 0.969 | 0.938 | 0.938 | 0.938 | 0.969 | 0.938 | 0.031 | 0.031 | 0 | 0 | 0 | 0.031 |
| model invocation rate | 0.287 | 0.286 | 0.409 | 0.54 | 0.287 | 0.286 | 0.251 | 0.287 | -0.001 | 0.122 | 0.253 | 0 | -0.001 | -0.036 |

Run-to-run spread |A1 − A2|: episodes 0, ticks 0, wall_s 148.3, decode_tokens 13, decode_per_tick 0.01, library group top-1 0, library top-1 0, belief group top-1 (code only) 0, held-out group top-1 0.059, faithfulness 0, citation relevance 0.001, actions precision 0, actions recall 0, model invocation rate 0

## Time per stage, ms per tick it ran (LAPTOP)

Each blackboard step's own time; a model agent's step includes its call. Hard path = sensor, triage, retriever, gate, scheduler.

| stage | bevideas_A1 mean / p95 / max | bevideas_B_explain mean / p95 / max | bevideas_B_actions mean / p95 / max | bevideas_B_unknown mean / p95 / max | bevideas_B_verifier mean / p95 / max | bevideas_B_notes mean / p95 / max | bevideas_B_skip mean / p95 / max |
|---|---|---|---|---|---|---|---|
| gate (hard path) | 0.284 / 0.622 / 1.224 (1380) | 0.293 / 0.659 / 1.104 (1380) | 0.301 / 0.648 / 0.952 (1380) | 0.339 / 0.694 / 1.065 (1380) | 0.273 / 0.599 / 0.976 (1380) | 0.272 / 0.588 / 0.981 (1380) | 0.255 / 0.581 / 0.752 (1380) |
| retriever (hard path) | 0.391 / 0.471 / 1.159 (812) | 0.389 / 0.47 / 0.722 (812) | 0.379 / 0.439 / 0.749 (812) | 0.384 / 0.428 / 1.131 (812) | 0.376 / 0.433 / 0.989 (812) | 0.378 / 0.451 / 1.049 (812) | 0.371 / 0.429 / 0.672 (812) |
| scheduler (hard path) | 0.327 / 0.697 / 2.373 (812) | 0.282 / 0.576 / 0.995 (812) | 0.345 / 0.678 / 2.8 (812) | 0.373 / 0.727 / 2.232 (812) | 0.307 / 0.632 / 2.438 (812) | 0.305 / 0.635 / 1.504 (812) | 0.278 / 0.643 / 2.254 (812) |
| sensor (hard path) | 0.98 / 1.624 / 3.672 (1380) | 0.964 / 1.653 / 4.18 (1380) | 0.968 / 1.582 / 2.588 (1380) | 0.968 / 1.563 / 3.178 (1380) | 0.934 / 1.557 / 4.328 (1380) | 0.947 / 1.567 / 4.234 (1380) | 0.935 / 1.568 / 2.361 (1380) |
| triage (hard path) | 0.019 / 0.03 / 0.075 (1380) | 0.019 / 0.029 / 0.077 (1380) | 0.018 / 0.027 / 0.06 (1380) | 0.019 / 0.026 / 0.064 (1380) | 0.018 / 0.026 / 0.08 (1380) | 0.018 / 0.025 / 0.062 (1380) | 0.017 / 0.025 / 0.038 (1380) |
| bev | – | 694.345 / 958.017 / 1065.84 (402) | 433.333 / 550.649 / 638.821 (455) | 303.753 / 357.385 / 401.159 (812) | 784.582 / 1014.11 / 1103.09 (41) | 417.553 / 471.09 / 471.09 (5) | – |
| diagnostician | 3007.01 / 3792.42 / 5945.49 (403) | 1224.1 / 1365.42 / 2414.91 (403) | 3125.91 / 3870.78 / 6419.2 (403) | 3218.83 / 4008.69 / 6421.58 (403) | 3259.6 / 4057.06 / 6538.01 (403) | 3224.13 / 4073.77 / 6424.45 (402) | 3252.69 / 4005.06 / 6580.19 (340) |
| verifier | 1928.4 / 2184.68 / 2221.42 (41) | 1908.74 / 2139.96 / 2197.97 (39) | 2019.04 / 2268.81 / 2313.57 (41) | 2058.85 / 2309.03 / 2362.39 (41) | – | 2120.21 / 2318.39 / 3764.01 (41) | 2089.38 / 2337.07 / 2350 (41) |
| whole tick | 977.996 / 3689.6 | 661.32 / 2347.31 | 1165.46 / 4270.97 | 1237.28 / 4293.04 | 1017.74 / 3933.84 | 1046.19 / 3978.38 | 904.496 / 3884.95 |

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

**bevideas_B_actions**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| bev_actions@bev | 455 | 455 | 0 | 172,510 | 0 | 197.08 | 134.36 | 0 | 3.49 / 134.36 / 55.45 |
| diagnostician@npu | 406 | 406 | 0 | 293,352 | 13,701 | 1259.61 | 362.75 | 877.79 | – / – / – |
| verifier@cpu | 41 | 41 | 0 | 17,053 | 1,038 | 82.77 | 51.66 | 29.47 | – / – / – |

**bevideas_B_unknown**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| bev_unknown@bev | 812 | 812 | 0 | 237,449 | 0 | 246.5 | 164.74 | 0 | 8.44 / 164.74 / 66.22 |
| diagnostician@npu | 406 | 406 | 0 | 293,352 | 13,755 | 1297.05 | 373.67 | 904.91 | – / – / – |
| verifier@cpu | 41 | 41 | 0 | 17,053 | 1,038 | 84.4 | 52.5 | 30.1 | – / – / – |

**bevideas_B_verifier**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| bev_verifier@bev | 67 | 67 | 0 | 25,471 | 0 | 32.15 | 21.74 | 0 | 0.5 / 21.74 / 9.31 |
| diagnostician@npu | 406 | 406 | 0 | 293,352 | 13,751 | 1313.48 | 382.91 | 913.01 | – / – / – |
| verifier@bev | 41 | 0 | 41 | 0 | 0 | 0 | 0 | 0 | – / – / – |

**bevideas_B_notes**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| bev_notes@bev | 5 | 5 | 0 | 808 | 0 | 2.09 | 1.24 | 0 | 0.03 / 1.24 / 0.73 |
| diagnostician@npu | 405 | 405 | 0 | 285,499 | 13,500 | 1295.96 | 373.39 | 905.44 | – / – / – |
| verifier@cpu | 41 | 41 | 0 | 17,053 | 1,038 | 86.92 | 55.28 | 30.03 | – / – / – |

**bevideas_B_skip**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| diagnostician@npu | 343 | 343 | 0 | 247,208 | 11,567 | 1105.8 | 321.11 | 770.1 | – / – / – |
| verifier@cpu | 41 | 41 | 0 | 17,046 | 1,038 | 85.65 | 53.58 | 30.41 | – / – / – |

## Lane busy share (measured call time / episode wall time)

| lane | bevideas_A1 | bevideas_B_explain | bevideas_B_actions | bevideas_B_unknown | bevideas_B_verifier | bevideas_B_notes | bevideas_B_skip |
|---|---|---|---|---|---|---|---|
| bev | 0 s (0) | 279 s (0.306) | 197.1 s (0.123) | 246.5 s (0.144) | 32.2 s (0.023) | 2.1 s (0.001) | 0 s (0) |
| cpu | 79.1 s (0.059) | 74.4 s (0.082) | 82.8 s (0.051) | 84.4 s (0.049) | 0 s (0) | 86.9 s (0.06) | 85.7 s (0.069) |
| npu | 1211.7 s (0.898) | 493.2 s (0.54) | 1259.6 s (0.783) | 1297.1 s (0.759) | 1313.5 s (0.935) | 1296 s (0.897) | 1105.8 s (0.886) |

## Board resources (bench/board_sampler.py)

CPU s = utime + stime of the process; cores busy = CPU s / sampled time. NPU: no hardware counter is read; the NPU lane's work is its call time above. Supply energy is the power supply's, not the chip's, and `–` when the board does not expose it.

| | bevideas_A1 | bevideas_B_explain | bevideas_B_actions | bevideas_B_unknown | bevideas_B_verifier | bevideas_B_notes | bevideas_B_skip |
|---|---|---|---|---|---|---|---|
| bev: CPU s / cores busy / peak RSS MB | 0.4 / 0 / 967.8 | 130 / 0.137 / 1198.2 | 96.5 / 0.059 / 1393.1 | 120.6 / 0.069 / 1008.9 | 16.1 / 0.011 / 1054.7 | 1.6 / 0.001 / 1057.9 | 0.4 / 0 / 1057.9 |
| cpu: CPU s / cores busy / peak RSS MB | 419.5 / 0.302 / 1570.8 | 395.3 / 0.415 / 1562.2 | 439.3 / 0.267 / 1563 | 446.3 / 0.256 / 1556.2 | 1.6 / 0.001 / 1469.4 | 460.8 / 0.31 / 1555.9 | 454 / 0.352 / 1557.7 |
| npu: CPU s / cores busy / peak RSS MB | 1839.7 / 1.323 / 551.3 | 444.9 / 0.467 / 539.2 | 1849.8 / 1.123 / 542 | 1898.4 / 1.087 / 540.4 | 1905.1 / 1.312 / 542.5 | 1880.4 / 1.266 / 541.5 | 1608.1 / 1.246 / 535.4 |
| episodes_sampled | 10 | 10 | 10 | 10 | 10 | 10 | 10 |
| board_cpu_busy_pct_mean | 29.8 | 24.4 | 28.4 | 27.7 | 26.8 | 29.3 | 29.2 |
| cpu_max_c | 96.9 | 97.3 | 96.5 | 96.9 | 92.7 | 96.9 | 96.9 |
| npu_max_c | 96.5 | 96.9 | 97.3 | 97.7 | 96.9 | 97.3 | 98.1 |
| supply_energy_j | – | – | – | – | – | – | – |
| sampler_cpu_s | 1026.95 | 746.97 | 1232.29 | 1313.19 | 1079.45 | 1098.37 | 954.69 |

## bev ideas

**bevideas_A1**: every bev idea off.

**bevideas_B_explain**: explain=on

| idea | calls | failed | rejected | used | shadow | other |
|---|---|---|---|---|---|---|
| explain | 405 | 0 | 0 | 405 | 0 | over_limit 0 |

**bevideas_B_actions**: actions=on

| idea | calls | failed | rejected | used | shadow | other |
|---|---|---|---|---|---|---|
| actions | 455 | 0 | 0 | 455 | 0 | over_limit 0 |

| logged per answer | n | mean |
|---|---|---|
| actions.would_drop_per_ask | 455 | 0.002 |

**bevideas_B_unknown**: unknown=on

| idea | calls | failed | rejected | used | shadow | other |
|---|---|---|---|---|---|---|
| unknown | 812 | 0 | 0 | 812 | 0 | over_limit 0 |

| logged per answer | n | mean |
|---|---|---|
| unknown.unknown_fault | 812 | 0.969 |

**bevideas_B_verifier**: verifier=on

| idea | calls | failed | rejected | used | shadow | other |
|---|---|---|---|---|---|---|
| verifier | 67 | 0 | 0 | 41 | 0 | over_limit 0 |

**bevideas_B_notes**: notes=on

| idea | calls | failed | rejected | used | shadow | other |
|---|---|---|---|---|---|---|
| notes | 5 | 0 | 0 | 5 | 0 | over_limit 0 |

**bevideas_B_skip**: clear_skip=on

| idea | calls | failed | rejected | used | shadow | other |
|---|---|---|---|---|---|---|
| clear_skip | 0 | 0 | 0 | 118 | 0 | – |

