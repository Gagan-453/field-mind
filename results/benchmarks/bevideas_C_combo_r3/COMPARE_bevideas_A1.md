# Benchmark comparison: bevideas_A1 vs bevideas_C_combo_r1 vs bevideas_C_combo_r2 vs bevideas_C_combo_r3

Baseline **bevideas_A1**, second baseline run **bevideas_A3**. 10 episodes in common: dev_A01_fcv_seize, dev_A02_fcv_seize_fast, dev_B01_tube_leak, dev_B02_tube_leak_fast, dev_C01_wet_coal, dev_C02_feeder_trip, dev_D01_high_cv_coal, dev_D03_high_cv_severe, dev_N01_normal, dev_N02_normal. Stage times are LAPTOP times (agent code runs on the laptop until Phase 4); model call times are as the client saw them. All plant data is synthetic.

| test | settings |
|---|---|
| bevideas_A1 | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `off`, backend llamaserver |
| bevideas_C_combo_r1 | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `explain=on,clear_skip=on,verifier=on`, backend llamaserver |
| bevideas_C_combo_r2 | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `explain=on,clear_skip=on,verifier=on`, backend llamaserver |
| bevideas_C_combo_r3 | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `explain=on,clear_skip=on,verifier=on`, backend llamaserver |
| bevideas_A3 | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `off`, backend llamaserver |

## Headline

| metric | bevideas_A1 | bevideas_C_combo_r1 | bevideas_C_combo_r2 | bevideas_C_combo_r3 | bevideas_A3 | bevideas_C_combo_r1 − bevideas_A1 | bevideas_C_combo_r2 − bevideas_A1 | bevideas_C_combo_r3 − bevideas_A1 |
|---|---|---|---|---|---|---|---|---|
| episodes | 10 | 10 | 10 | 10 | 10 | 0 | 0 | 0 |
| ticks | 1,380 | 1,380 | 1,380 | 1,380 | 1,380 | 0 | 0 | 0 |
| wall_s | 1350 | 744.1 | 729.1 | 725.2 | 1372.1 | -605.9 | -620.9 | -624.8 |
| decode_tokens | 14,735 | 2,855 | 2,865 | 2,842 | 14,765 | -11,880 | -11,870 | -11,893 |
| decode_per_tick | 10.68 | 2.07 | 2.08 | 2.06 | 10.7 | -8.61 | -8.6 | -8.62 |
| library group top-1 | 0.759 | 0.775 | 0.775 | 0.775 | 0.759 | 0.016 | 0.016 | 0.016 |
| library top-1 | 0.646 | 0.609 | 0.611 | 0.609 | 0.646 | -0.037 | -0.035 | -0.037 |
| belief group top-1 (code only) | 0.655 | 0.655 | 0.655 | 0.655 | 0.655 | 0 | 0 | 0 |
| held-out group top-1 | 0.451 | 0.549 | 0.549 | 0.549 | 0.471 | 0.098 | 0.098 | 0.098 |
| faithfulness | 0.972 | 0.973 | 0.973 | 0.973 | 0.973 | 0.001 | 0.001 | 0.001 |
| citation relevance | 0.657 | 0.642 | 0.64 | 0.643 | 0.658 | -0.015 | -0.017 | -0.014 |
| actions precision | 0.481 | 0.479 | 0.482 | 0.482 | 0.489 | -0.002 | 0.001 | 0.001 |
| actions recall | 0.938 | 0.969 | 0.969 | 0.969 | 0.969 | 0.031 | 0.031 | 0.031 |
| model invocation rate | 0.287 | 0.257 | 0.257 | 0.256 | 0.287 | -0.03 | -0.03 | -0.031 |

Run-to-run spread |A1 − A2|: episodes 0, ticks 0, wall_s 22.1, decode_tokens 30, decode_per_tick 0.02, library group top-1 0, library top-1 0, belief group top-1 (code only) 0, held-out group top-1 0.02, faithfulness 0.001, citation relevance 0.001, actions precision 0.008, actions recall 0.031, model invocation rate 0

## Time per stage, ms per tick it ran (LAPTOP)

Each blackboard step's own time; a model agent's step includes its call. Hard path = sensor, triage, retriever, gate, scheduler.

| stage | bevideas_A1 mean / p95 / max | bevideas_C_combo_r1 mean / p95 / max | bevideas_C_combo_r2 mean / p95 / max | bevideas_C_combo_r3 mean / p95 / max |
|---|---|---|---|---|
| gate (hard path) | 0.284 / 0.622 / 1.224 (1380) | 0.142 / 0.321 / 0.702 (1380) | 0.139 / 0.32 / 0.65 (1380) | 0.139 / 0.32 / 0.568 (1380) |
| retriever (hard path) | 0.391 / 0.471 / 1.159 (812) | 0.215 / 0.248 / 0.578 (812) | 0.212 / 0.244 / 0.551 (812) | 0.213 / 0.249 / 0.486 (812) |
| scheduler (hard path) | 0.327 / 0.697 / 2.373 (812) | 0.144 / 0.304 / 0.591 (812) | 0.142 / 0.302 / 0.526 (812) | 0.142 / 0.305 / 0.542 (812) |
| sensor (hard path) | 0.98 / 1.624 / 3.672 (1380) | 0.567 / 0.901 / 1.361 (1380) | 0.54 / 0.896 / 1.56 (1380) | 0.539 / 0.895 / 1.63 (1380) |
| triage (hard path) | 0.019 / 0.03 / 0.075 (1380) | 0.011 / 0.015 / 0.041 (1380) | 0.01 / 0.014 / 0.026 (1380) | 0.01 / 0.014 / 0.029 (1380) |
| bev | – | 737.006 / 1088.28 / 1821.8 (368) | 738.064 / 1102.2 / 1793.11 (369) | 737.905 / 1124.96 / 1861.81 (366) |
| diagnostician | 3007.01 / 3792.42 / 5945.49 (403) | 1224.48 / 1386.76 / 2473.6 (356) | 1180.7 / 1328.15 / 2307.2 (356) | 1183.01 / 1337.9 / 2332.07 (354) |
| verifier | 1928.4 / 2184.68 / 2221.42 (41) | – | – | – |
| whole tick | 977.996 / 3689.6 | 539.071 / 2291.41 | 528.171 / 2220.76 | 525.347 / 2235.97 |

## Model calls per agent @ lane

answers = envelopes; stand-ins = bev answering in that agent's place (no call of its own). Read = prefill. bev decodes nothing.

**bevideas_A1**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| diagnostician@npu | 406 | 406 | 0 | 293,352 | 13,697 | 1211.68 | 345.39 | 848.83 | – / – / – |
| verifier@cpu | 41 | 41 | 0 | 17,053 | 1,038 | 79.05 | 48.89 | 28.52 | – / – / – |

**bevideas_C_combo_r1**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| bev_explain@bev | 357 | 357 | 0 | 241,729 | 0 | 243.15 | 170.32 | 0 | 4.2 / 170.32 / 66.45 |
| bev_verifier@bev | 59 | 59 | 0 | 22,900 | 0 | 28.01 | 18.99 | 0 | 0.32 / 18.99 / 8.3 |
| diagnostician@npu | 359 | 359 | 0 | 236,965 | 2,855 | 435.83 | 277.7 | 143.56 | – / – / – |
| verifier@bev | 37 | 0 | 37 | 0 | 0 | 0 | 0 | 0 | – / – / – |

**bevideas_C_combo_r2**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| bev_explain@bev | 358 | 358 | 0 | 243,254 | 0 | 244.33 | 171.57 | 0 | 4.17 / 171.57 / 66.31 |
| bev_verifier@bev | 59 | 59 | 0 | 22,900 | 0 | 27.95 | 19.01 | 0 | 0.28 / 19.01 / 8.24 |
| diagnostician@npu | 359 | 359 | 0 | 236,969 | 2,865 | 420.25 | 262.86 | 142.66 | – / – / – |
| verifier@bev | 37 | 0 | 37 | 0 | 0 | 0 | 0 | 0 | – / – / – |

**bevideas_C_combo_r3**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| bev_explain@bev | 355 | 355 | 0 | 240,319 | 0 | 242.03 | 169.15 | 0 | 4.16 / 169.15 / 66.55 |
| bev_verifier@bev | 59 | 59 | 0 | 22,900 | 0 | 27.98 | 19.03 | 0 | 0.29 / 19.03 / 8.24 |
| diagnostician@npu | 357 | 357 | 0 | 235,691 | 2,842 | 418.7 | 261.35 | 142.34 | – / – / – |
| verifier@bev | 37 | 0 | 37 | 0 | 0 | 0 | 0 | 0 | – / – / – |

## Lane busy share (measured call time / episode wall time)

| lane | bevideas_A1 | bevideas_C_combo_r1 | bevideas_C_combo_r2 | bevideas_C_combo_r3 |
|---|---|---|---|---|
| bev | 0 s (0) | 271.2 s (0.364) | 272.3 s (0.373) | 270 s (0.372) |
| cpu | 79.1 s (0.059) | 0 s (0) | 0 s (0) | 0 s (0) |
| npu | 1211.7 s (0.898) | 435.8 s (0.586) | 420.2 s (0.576) | 418.7 s (0.577) |

## Board resources (bench/board_sampler.py)

CPU s = utime + stime of the process; cores busy = CPU s / sampled time. NPU: no hardware counter is read; the NPU lane's work is its call time above. Supply energy is the power supply's, not the chip's, and `–` when the board does not expose it.

| | bevideas_A1 | bevideas_C_combo_r1 | bevideas_C_combo_r2 | bevideas_C_combo_r3 |
|---|---|---|---|---|
| bev: CPU s / cores busy / peak RSS MB | 0.4 / 0 / 967.8 | 127.5 / 0.163 / 584.7 | 127.2 / 0.166 / 584.9 | 127.4 / 0.166 / 763.9 |
| cpu: CPU s / cores busy / peak RSS MB | 419.5 / 0.302 / 1570.8 | 0.9 / 0.001 / 1475.6 | 0.9 / 0.001 / 1475.7 | 0.8 / 0.001 / 1475.1 |
| npu: CPU s / cores busy / peak RSS MB | 1839.7 / 1.323 / 551.3 | 393.5 / 0.503 / 539.8 | 394.5 / 0.514 / 539.5 | 389.5 / 0.507 / 539.1 |
| episodes_sampled | 10 | 10 | 10 | 10 |
| board_cpu_busy_pct_mean | 29.8 | 21.2 | 21.4 | 21.3 |
| cpu_max_c | 96.9 | 79.1 | 81.4 | 76.8 |
| npu_max_c | 96.5 | 96.9 | 96.1 | 95.7 |
| supply_energy_j | – | – | – | – |
| sampler_cpu_s | 1026.95 | 617.21 | 607.63 | 607.4 |

## bev ideas

**bevideas_A1**: every bev idea off.

**bevideas_C_combo_r1**: explain=on, verifier=on, clear_skip=on

| idea | calls | failed | rejected | used | shadow | other |
|---|---|---|---|---|---|---|
| clear_skip | 0 | 0 | 0 | 99 | 0 | – |
| explain | 357 | 0 | 0 | 357 | 0 | over_limit 0 |
| verifier | 59 | 0 | 0 | 37 | 0 | over_limit 0 |

**bevideas_C_combo_r2**: explain=on, verifier=on, clear_skip=on

| idea | calls | failed | rejected | used | shadow | other |
|---|---|---|---|---|---|---|
| clear_skip | 0 | 0 | 0 | 98 | 0 | – |
| explain | 358 | 0 | 0 | 358 | 0 | over_limit 0 |
| verifier | 59 | 0 | 0 | 37 | 0 | over_limit 0 |

**bevideas_C_combo_r3**: explain=on, verifier=on, clear_skip=on

| idea | calls | failed | rejected | used | shadow | other |
|---|---|---|---|---|---|---|
| clear_skip | 0 | 0 | 0 | 98 | 0 | – |
| explain | 355 | 0 | 0 | 355 | 0 | over_limit 0 |
| verifier | 59 | 0 | 0 | 37 | 0 | over_limit 0 |

