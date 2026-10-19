# Benchmark `bevideas_B_explain`

Architecture **multi**, mode **lockstep**, overlay `configs/bev_ideas.yaml`, merge rule `hybrid`, models npu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`, cpu: `gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf`, bev: `bev-decider-0.4B-backbone-Q8_0.gguf`. Agent code ran on the laptop and only model calls on the board, so tick times are laptop times. Energy not measured. All plant data is synthetic.

bev ideas switches: `explain=on`. bev-decide on npu. bev idea calls: answered by bev-decide (failed = no answer, which makes the run invalid and is not kept; rejected = refused by the gate's check). used = an answer that changed what the agent did; shadow = asked and only logged. Decode tokens per tick: answer tokens written by every model per tick (bev writes none).

Group top-1 is the share of scored ticks (fault onset onward) whose published rank-1 cause is in the true case's look-alike group; belief group top-1 is the same for the code-only ranking. A held-out true case has no exact top-1. Unusable = a model answer that was not used (wrong format, failed call, rejected note reading). Settings and every run, stopped ones included: `test.json`.

| episode | run | finished | ticks | model calls | bev idea calls / failed / rejected | bev used / shadow | decode tokens per tick | unusable | tokens in | group top-1 | belief group top-1 | exact top-1 | faithfulness | actions P / R | lead time min | false alarms /h | tick p95 ms | wall s | chip C | server CPU s npu / cpu / bev | peak RSS MB npu / cpu / bev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | 2026-10-19 16:16 | 130 | 62 | 31 / 0 / 0 | 31 / 0 | 1.89 | 0 | 35,994 | 0.51 | 0.02 | 0.40 | 0.99 | 0.29 / 1.00 | – | – | 2032 | 66 | 43.4 → 53.6 | 33.2 / 0.1 / 10.2 | 522 / 1476 / 984 |
| dev_A02_fcv_seize_fast | 1 | 2026-10-19 16:19 | 80 | 91 | 40 / 0 / 0 | 40 / 0 | 7.36 | 0 | 57,824 | 0.62 | 0.47 | 0.03 | 1.00 | 0.29 / 1.00 | 5.7 | – | 3472 | 103 | 46.7 → 58.3 | 40.9 / 116.1 / 12.4 | 526 / 1559 / 1004 |
| dev_B01_tube_leak | 1 | 2026-10-19 16:22 | 170 | 123 | 58 / 0 / 0 | 58 / 0 | 3.76 | 0 | 66,813 | 0.95 | 0.47 | 0.95 | 1.00 | 0.57 / 1.00 | – | – | 1951 | 128 | 46.7 → 61.2 | 64.5 / 66.8 / 13.3 | 528 / 1562 / 1028 |
| dev_B02_tube_leak_fast | 1 | 2026-10-19 16:24 | 80 | 47 | 23 / 0 / 0 | 23 / 0 | 2.38 | 0 | 20,603 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 / 0.75 | – | – | 1545 | 44 | 48.2 → 57.1 | 25.9 / 0.1 / 3.2 | 522 / 1475 / 1033 |
| dev_C01_wet_coal | 1 | 2026-10-19 16:26 | 170 | 54 | 27 / 0 / 0 | 27 / 0 | 1.27 | 0 | 37,142 | 0.55 | 0.72 | – | 0.91 | 0.40 / 1.00 | – | – | 2182 | 64 | 47.5 → 57.1 | 29.2 / 0.1 / 9.8 | 522 / 1475 / 1053 |
| dev_C02_feeder_trip | 1 | 2026-10-19 16:29 | 100 | 98 | 42 / 0 / 0 | 42 / 0 | 6.89 | 0 | 53,373 | 0.57 | 0.91 | 0.10 | 0.93 | 0.23 / 1.00 | – | – | 3947 | 112 | 47.5 → 61.4 | 46.3 / 137.4 / 11.1 | 526 / 1556 / 1074 |
| dev_D01_high_cv_coal | 1 | 2026-10-19 16:36 | 310 | 261 | 127 / 0 / 0 | 127 / 0 | 3.85 | 0 | 202,408 | 0.80 | 0.78 | 0.80 | 0.98 | 0.44 / 1.00 | 82.3 | – | 2433 | 319 | 46.7 → 62.5 | 142.5 / 74.6 / 50.2 | 539 / 1555 / 1165 |
| dev_D03_high_cv_severe | 1 | 2026-10-19 16:40 | 150 | 112 | 56 / 0 / 0 | 56 / 0 | 2.99 | 0 | 89,321 | 0.94 | 0.94 | 0.94 | 0.92 | 0.57 / 1.00 | 43.2 | – | 2244 | 127 | 47.1 → 60.5 | 61.1 / 0.1 / 19.7 | 524 / 1469 / 1198 |
| dev_N01_normal | 1 | 2026-10-19 16:42 | 80 | 0 | 0 / 0 / 0 | 0 / 0 | 0.00 | 0 | 0 | – | – | – | 1.00 | – | – | 0.00 | 5 | 7 | 46.7 → 47.5 | 0.0 / 0.0 / 0.0 | 484 / 1470 / 1198 |
| dev_N02_normal | 1 | 2026-10-19 16:42 | 110 | 2 | 1 / 0 / 0 | 1 / 0 | 0.07 | 0 | 788 | – | – | – | 1.00 | – | – | 1.09 | 12 | 9 | 47.1 → 47.8 | 1.4 / 0.0 / 0.1 | 498 / 1469 / 1198 |

## bev ideas per episode

| episode | run | idea | calls | failed | rejected | used | shadow | other counters |
|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | explain | 31 | 0 | 0 | 31 | 0 | over_limit 0 |
| dev_A02_fcv_seize_fast | 1 | explain | 40 | 0 | 0 | 40 | 0 | over_limit 0 |
| dev_B01_tube_leak | 1 | explain | 58 | 0 | 0 | 58 | 0 | over_limit 0 |
| dev_B02_tube_leak_fast | 1 | explain | 23 | 0 | 0 | 23 | 0 | over_limit 0 |
| dev_C01_wet_coal | 1 | explain | 27 | 0 | 0 | 27 | 0 | over_limit 0 |
| dev_C02_feeder_trip | 1 | explain | 42 | 0 | 0 | 42 | 0 | over_limit 0 |
| dev_D01_high_cv_coal | 1 | explain | 127 | 0 | 0 | 127 | 0 | over_limit 0 |
| dev_D03_high_cv_severe | 1 | explain | 56 | 0 | 0 | 56 | 0 | over_limit 0 |
| dev_N02_normal | 1 | explain | 1 | 0 | 0 | 1 | 0 | over_limit 0 |

Board resources (on-board sampler, once a second, per episode): CPU seconds and peak memory of each model server. The NPU has no readable usage counter; its work shows as the NPU lane's call time. Supply power, if the board exposes it, is in each summary's `meta.resources`; energy is never estimated.
