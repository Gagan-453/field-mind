# Benchmark `bevideas_shadow`

Architecture **multi**, mode **lockstep**, overlay `configs/bev_ideas.yaml`, merge rule `hybrid`, models npu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`, cpu: `gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf`, bev: `bev-decider-0.4B-backbone-Q8_0.gguf`. Agent code ran on the laptop and only model calls on the board, so tick times are laptop times. Energy not measured. All plant data is synthetic.

bev ideas switches: `explain=shadow,first=shadow,actions=shadow,unknown=shadow,verifier=shadow,notes=shadow,clear_skip=shadow`. bev-decide on npu. bev idea calls: answered by bev-decide (failed = no answer, which makes the run invalid and is not kept; rejected = refused by the gate's check). used = an answer that changed what the agent did; shadow = asked and only logged. Decode tokens per tick: answer tokens written by every model per tick (bev writes none).

Group top-1 is the share of scored ticks (fault onset onward) whose published rank-1 cause is in the true case's look-alike group; belief group top-1 is the same for the code-only ranking. A held-out true case has no exact top-1. Unusable = a model answer that was not used (wrong format, failed call, rejected note reading). Settings and every run, stopped ones included: `test.json`.

| episode | run | finished | ticks | model calls | bev idea calls / failed / rejected | bev used / shadow | decode tokens per tick | unusable | tokens in | group top-1 | belief group top-1 | exact top-1 | faithfulness | actions P / R | lead time min | false alarms /h | tick p95 ms | wall s | chip C | server CPU s npu / cpu / bev | peak RSS MB npu / cpu / bev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | 2026-10-19 14:02 | 130 | 31 | 126 / 0 / 0 | 0 / 126 | 8.02 | 0 | 21,084 | 0.56 | 0.02 | 0.42 | 0.99 | 0.31 / 1.00 | – | – | 4770 | 142 | 36.0 → 54.8 | 130.3 / 0.1 / 23.6 | 537 / 1475 / 445 |
| dev_A02_fcv_seize_fast | 1 | 2026-10-19 14:09 | 80 | 51 | 158 / 0 / 0 | 0 / 156 | 19.64 | 0 | 30,739 | 0.62 | 0.47 | 0.02 | 1.00 | 0.29 / 1.00 | -9.3 | – | 6563 | 201 | 39.7 → 59.4 | 159.2 / 112.2 / 31.3 | 531 / 1560 / 483 |
| dev_B01_tube_leak | 1 | 2026-10-19 14:18 | 170 | 65 | 235 / 0 / 0 | 0 / 250 | 10.81 | 0 | 46,317 | 0.95 | 0.47 | 0.95 | 1.00 | 0.57 / 1.00 | – | – | 4059 | 259 | 39.7 → 59.8 | 221.6 / 64.5 / 38.3 | 534 / 1567 / 529 |
| dev_B02_tube_leak_fast | 1 | 2026-10-19 14:25 | 80 | 24 | 76 / 0 / 0 | 0 / 97 | 8.11 | 0 | 17,132 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 / 0.75 | – | – | 3132 | 88 | 39.3 → 54.8 | 84.7 / 0.1 / 10.6 | 529 / 1475 / 540 |
| dev_C01_wet_coal | 1 | 2026-10-19 14:32 | 170 | 27 | 117 / 0 / 0 | 0 / 120 | 5.72 | 0 | 20,418 | 0.53 | 0.72 | – | 0.91 | 0.40 / 1.00 | – | – | 4939 | 140 | 39.3 → 54.8 | 131.8 / 0.1 / 23.7 | 529 / 1475 / 571 |
| dev_C02_feeder_trip | 1 | 2026-10-19 14:41 | 100 | 58 | 222 / 0 / 0 | 0 / 210 | 18.96 | 0 | 36,511 | 0.43 | 0.91 | 0.39 | 0.94 | 0.33 / 1.00 | – | – | 7763 | 250 | 39.7 → 62.0 | 195.4 / 150.2 / 41.8 | 532 / 1586 / 625 |
| dev_D01_high_cv_coal | 1 | 2026-10-19 15:01 | 310 | 134 | 636 / 0 / 0 | 0 / 719 | 15.83 | 0 | 97,122 | 0.80 | 0.78 | 0.80 | 0.98 | 0.44 / 1.00 | 82.3 | – | 5615 | 753 | 39.7 → 64.5 | 629.3 / 75.5 / 141.3 | 549 / 1557 / 846 |
| dev_D03_high_cv_severe | 1 | 2026-10-19 15:13 | 150 | 56 | 332 / 0 / 0 | 0 / 373 | 12.39 | 0 | 40,405 | 0.94 | 0.94 | 0.94 | 0.92 | 0.57 / 1.00 | 43.2 | – | 4950 | 317 | 39.7 → 61.4 | 235.2 / 0.3 / 68.5 | 536 / 1475 / 967 |
| dev_N01_normal | 1 | 2026-10-19 15:20 | 80 | 0 | 0 / 0 / 0 | 0 / 0 | 0.00 | 0 | 0 | – | – | – | 1.00 | – | – | 0.00 | 3 | 6 | 39.7 → 40.9 | 0.0 / 0.0 / 0.0 | 490 / 1475 / 967 |
| dev_N02_normal | 1 | 2026-10-19 15:21 | 110 | 1 | 3 / 0 / 0 | 0 / 3 | 0.25 | 0 | 677 | – | – | – | 1.00 | – | – | 1.09 | 7 | 10 | 39.7 → 43.2 | 3.9 / 0.0 / 0.4 | 517 / 1475 / 968 |

## bev ideas per episode

| episode | run | idea | calls | failed | rejected | used | shadow | other counters |
|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | actions | 14 | 0 | 0 | 0 | 14 | over_limit 0 |
| dev_A01_fcv_seize | 1 | explain | 31 | 0 | 0 | 0 | 31 | over_limit 0 |
| dev_A01_fcv_seize | 1 | first | 23 | 0 | 0 | 0 | 23 | over_limit 0 |
| dev_A01_fcv_seize | 1 | notes | 1 | 0 | 0 | 0 | 1 | over_limit 0 |
| dev_A01_fcv_seize | 1 | unknown | 57 | 0 | 0 | 0 | 57 | over_limit 0 |
| dev_A02_fcv_seize_fast | 1 | actions | 14 | 0 | 0 | 0 | 14 | over_limit 0 |
| dev_A02_fcv_seize_fast | 1 | clear_skip | 0 | 0 | 0 | 0 | 9 | – |
| dev_A02_fcv_seize_fast | 1 | explain | 40 | 0 | 0 | 0 | 40 | over_limit 0 |
| dev_A02_fcv_seize_fast | 1 | first | 18 | 0 | 0 | 0 | 18 | over_limit 0 |
| dev_A02_fcv_seize_fast | 1 | unknown | 64 | 0 | 0 | 0 | 64 | over_limit 0 |
| dev_A02_fcv_seize_fast | 1 | verifier | 22 | 0 | 0 | 0 | 11 | over_limit 0 |
| dev_B01_tube_leak | 1 | actions | 2 | 0 | 0 | 0 | 2 | over_limit 0 |
| dev_B01_tube_leak | 1 | clear_skip | 0 | 0 | 0 | 0 | 15 | – |
| dev_B01_tube_leak | 1 | explain | 58 | 0 | 0 | 0 | 58 | over_limit 0 |
| dev_B01_tube_leak | 1 | first | 39 | 0 | 0 | 0 | 39 | over_limit 0 |
| dev_B01_tube_leak | 1 | notes | 1 | 0 | 0 | 0 | 1 | over_limit 0 |
| dev_B01_tube_leak | 1 | unknown | 128 | 0 | 0 | 0 | 128 | over_limit 0 |
| dev_B01_tube_leak | 1 | verifier | 7 | 0 | 0 | 0 | 7 | over_limit 0 |
| dev_B02_tube_leak_fast | 1 | clear_skip | 0 | 0 | 0 | 0 | 21 | – |
| dev_B02_tube_leak_fast | 1 | explain | 23 | 0 | 0 | 0 | 23 | over_limit 0 |
| dev_B02_tube_leak_fast | 1 | first | 2 | 0 | 0 | 0 | 2 | over_limit 0 |
| dev_B02_tube_leak_fast | 1 | unknown | 51 | 0 | 0 | 0 | 51 | over_limit 0 |
| dev_C01_wet_coal | 1 | actions | 17 | 0 | 0 | 0 | 17 | over_limit 0 |
| dev_C01_wet_coal | 1 | clear_skip | 0 | 0 | 0 | 0 | 3 | – |
| dev_C01_wet_coal | 1 | explain | 27 | 0 | 0 | 0 | 27 | over_limit 0 |
| dev_C01_wet_coal | 1 | first | 20 | 0 | 0 | 0 | 20 | over_limit 0 |
| dev_C01_wet_coal | 1 | notes | 1 | 0 | 0 | 0 | 1 | over_limit 0 |
| dev_C01_wet_coal | 1 | unknown | 52 | 0 | 0 | 0 | 52 | over_limit 0 |
| dev_C02_feeder_trip | 1 | actions | 34 | 0 | 0 | 0 | 34 | over_limit 0 |
| dev_C02_feeder_trip | 1 | explain | 42 | 0 | 0 | 0 | 42 | over_limit 0 |
| dev_C02_feeder_trip | 1 | first | 41 | 0 | 0 | 0 | 41 | over_limit 0 |
| dev_C02_feeder_trip | 1 | unknown | 77 | 0 | 0 | 0 | 77 | over_limit 0 |
| dev_C02_feeder_trip | 1 | verifier | 28 | 0 | 0 | 0 | 16 | over_limit 0 |
| dev_D01_high_cv_coal | 1 | actions | 241 | 0 | 0 | 0 | 241 | over_limit 0 |
| dev_D01_high_cv_coal | 1 | clear_skip | 0 | 0 | 0 | 0 | 85 | – |
| dev_D01_high_cv_coal | 1 | explain | 127 | 0 | 0 | 0 | 127 | over_limit 0 |
| dev_D01_high_cv_coal | 1 | first | 8 | 0 | 0 | 0 | 8 | over_limit 0 |
| dev_D01_high_cv_coal | 1 | notes | 1 | 0 | 0 | 0 | 1 | over_limit 0 |
| dev_D01_high_cv_coal | 1 | unknown | 250 | 0 | 0 | 0 | 250 | over_limit 0 |
| dev_D01_high_cv_coal | 1 | verifier | 9 | 0 | 0 | 0 | 7 | over_limit 0 |
| dev_D03_high_cv_severe | 1 | actions | 132 | 0 | 0 | 0 | 132 | over_limit 0 |
| dev_D03_high_cv_severe | 1 | clear_skip | 0 | 0 | 0 | 0 | 41 | – |
| dev_D03_high_cv_severe | 1 | explain | 56 | 0 | 0 | 0 | 56 | over_limit 0 |
| dev_D03_high_cv_severe | 1 | first | 11 | 0 | 0 | 0 | 11 | over_limit 0 |
| dev_D03_high_cv_severe | 1 | notes | 1 | 0 | 0 | 0 | 1 | over_limit 0 |
| dev_D03_high_cv_severe | 1 | unknown | 132 | 0 | 0 | 0 | 132 | over_limit 0 |
| dev_N02_normal | 1 | actions | 1 | 0 | 0 | 0 | 1 | over_limit 0 |
| dev_N02_normal | 1 | explain | 1 | 0 | 0 | 0 | 1 | over_limit 0 |
| dev_N02_normal | 1 | unknown | 1 | 0 | 0 | 0 | 1 | over_limit 0 |

Board resources (on-board sampler, once a second, per episode): CPU seconds and peak memory of each model server. The NPU has no readable usage counter; its work shows as the NPU lane's call time. Supply power, if the board exposes it, is in each summary's `meta.resources`; energy is never estimated.
