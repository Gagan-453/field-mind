# Benchmark comparison: bevideas_A3 vs bevideas_A_soak

Baseline **bevideas_A3**, second baseline run **bevideas_A2**. 10 episodes in common: dev_A01_fcv_seize, dev_A02_fcv_seize_fast, dev_B01_tube_leak, dev_B02_tube_leak_fast, dev_C01_wet_coal, dev_C02_feeder_trip, dev_D01_high_cv_coal, dev_D03_high_cv_severe, dev_N01_normal, dev_N02_normal. Stage times are LAPTOP times (agent code runs on the laptop until Phase 4); model call times are as the client saw them. All plant data is synthetic.

| test | settings |
|---|---|
| bevideas_A3 | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `off`, backend llamaserver |
| bevideas_A_soak | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `off`, backend llamaserver |
| bevideas_A2 | overlay `configs/bev_ideas.yaml`, mode lockstep, bev `off`, backend llamaserver |

## Headline

| metric | bevideas_A3 | bevideas_A_soak | bevideas_A2 | bevideas_A_soak − bevideas_A3 |
|---|---|---|---|---|
| episodes | 10 | 10 | 10 | 0 |
| ticks | 1,380 | 1,380 | 1,380 | 0 |
| wall_s | 1372.1 | 1502.9 | 1498.3 | 130.8 |
| decode_tokens | 14,765 | 14,714 | 14,722 | -51 |
| decode_per_tick | 10.7 | 10.66 | 10.67 | -0.04 |
| library group top-1 | 0.759 | 0.759 | 0.759 | 0 |
| library top-1 | 0.646 | 0.646 | 0.646 | 0 |
| belief group top-1 (code only) | 0.655 | 0.655 | 0.655 | 0 |
| held-out group top-1 | 0.471 | 0.451 | 0.51 | -0.02 |
| faithfulness | 0.973 | 0.972 | 0.972 | -0.001 |
| citation relevance | 0.658 | 0.657 | 0.656 | -0.001 |
| actions precision | 0.489 | 0.478 | 0.481 | -0.011 |
| actions recall | 0.969 | 0.938 | 0.938 | -0.031 |
| model invocation rate | 0.287 | 0.287 | 0.287 | 0 |

Run-to-run spread |A1 − A2|: episodes 0, ticks 0, wall_s 126.2, decode_tokens 43, decode_per_tick 0.03, library group top-1 0, library top-1 0, belief group top-1 (code only) 0, held-out group top-1 0.039, faithfulness 0.001, citation relevance 0.002, actions precision 0.008, actions recall 0.031, model invocation rate 0

## Time per stage, ms per tick it ran (LAPTOP)

Each blackboard step's own time; a model agent's step includes its call. Hard path = sensor, triage, retriever, gate, scheduler.

| stage | bevideas_A3 mean / p95 / max | bevideas_A_soak mean / p95 / max |
|---|---|---|
| gate (hard path) | 0.138 / 0.293 / 0.606 (1380) | 0.138 / 0.294 / 0.513 (1380) |
| retriever (hard path) | 0.214 / 0.25 / 0.44 (812) | 0.214 / 0.246 / 0.585 (812) |
| scheduler (hard path) | 0.181 / 0.37 / 1.21 (812) | 0.18 / 0.37 / 1.315 (812) |
| sensor (hard path) | 0.54 / 0.898 / 1.47 (1380) | 0.537 / 0.892 / 1.764 (1380) |
| triage (hard path) | 0.01 / 0.014 / 0.032 (1380) | 0.01 / 0.014 / 0.032 (1380) |
| diagnostician | 3119.05 / 3914.7 / 6136.57 (403) | 3430.36 / 4404.63 / 7345.46 (403) |
| verifier | 2008.58 / 2425.52 / 3000.05 (41) | 2140.65 / 2433.89 / 2460.64 (41) |
| whole tick | 994.157 / 3833.81 | 1088.92 / 4265.54 |

## Model calls per agent @ lane

answers = envelopes; stand-ins = bev answering in that agent's place (no call of its own). Read = prefill. bev decodes nothing.

**bevideas_A3**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| diagnostician@npu | 406 | 406 | 0 | 293,352 | 13,727 | 1256.88 | 356.99 | 883.24 | – / – / – |
| verifier@cpu | 41 | 41 | 0 | 17,053 | 1,038 | 82.34 | 51.86 | 29.01 | – / – / – |

**bevideas_A_soak**

| agent@lane | answers | calls | stand-ins | read tok | decode tok | call s | server read s | server decode s | bev tokenize / transformer / head s |
|---|---|---|---|---|---|---|---|---|---|
| diagnostician@npu | 406 | 406 | 0 | 293,352 | 13,676 | 1382.34 | 404.18 | 961.35 | – / – / – |
| verifier@cpu | 41 | 41 | 0 | 17,053 | 1,038 | 87.76 | 55.22 | 31.03 | – / – / – |

## Lane busy share (measured call time / episode wall time)

| lane | bevideas_A3 | bevideas_A_soak |
|---|---|---|
| bev | 0 s (0) | 0 s (0) |
| cpu | 82.3 s (0.06) | 87.8 s (0.058) |
| npu | 1256.9 s (0.916) | 1382.3 s (0.92) |

## Board resources (bench/board_sampler.py)

CPU s = utime + stime of the process; cores busy = CPU s / sampled time. NPU: no hardware counter is read; the NPU lane's work is its call time above. Supply energy is the power supply's, not the chip's, and `–` when the board does not expose it.

| | bevideas_A3 | bevideas_A_soak |
|---|---|---|
| bev: CPU s / cores busy / peak RSS MB | 0.4 / 0 / 763.9 | 0.4 / 0 / 763.1 |
| cpu: CPU s / cores busy / peak RSS MB | 436.5 / 0.31 / 1568.9 | 466.3 / 0.302 / 1569.8 |
| npu: CPU s / cores busy / peak RSS MB | 1861.2 / 1.322 / 546 | 1918.4 / 1.241 / 547.1 |
| episodes_sampled | 10 | 10 |
| board_cpu_busy_pct_mean | 30.1 | 29.2 |
| cpu_max_c | 96.1 | 96.9 |
| npu_max_c | 96.9 | 97.7 |
| supply_energy_j | – | – |
| sampler_cpu_s | 1043.61 | 1155.33 |

## bev ideas

**bevideas_A3**: every bev idea off.

**bevideas_A_soak**: every bev idea off.

