# Benchmark `bevideas_C_combo_r3`

Architecture **multi**, mode **lockstep**, overlay `configs/bev_ideas.yaml`, merge rule `hybrid`, models npu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`, cpu: `gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf`, bev: `bev-decider-0.4B-backbone-Q8_0.gguf`. Agent code ran on the laptop and only model calls on the board, so tick times are laptop times. Energy not measured. All plant data is synthetic.

bev ideas switches: `explain=on,clear_skip=on,verifier=on`. bev-decide on npu. bev idea calls: answered by bev-decide (failed = no answer, which makes the run invalid and is not kept; rejected = refused by the gate's check). used = an answer that changed what the agent did; shadow = asked and only logged. Decode tokens per tick: answer tokens written by every model per tick (bev writes none).

Group top-1 is the share of scored ticks (fault onset onward) whose published rank-1 cause is in the true case's look-alike group; belief group top-1 is the same for the code-only ranking. A held-out true case has no exact top-1. Unusable = a model answer that was not used (wrong format, failed call, rejected note reading). Settings and every run, stopped ones included: `test.json`.

| episode | run | finished | ticks | model calls | bev idea calls / failed / rejected | bev used / shadow | decode tokens per tick | unusable | tokens in | group top-1 | belief group top-1 | exact top-1 | faithfulness | actions P / R | lead time min | false alarms /h | tick p95 ms | wall s | chip C | server CPU s npu / cpu / bev | peak RSS MB npu / cpu / bev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | 2026-10-21 02:58 | 130 | 62 | 31 / 0 / 0 | 31 / 0 | 1.89 | 0 | 35,973 | 0.51 | 0.02 | 0.40 | 0.99 | 0.31 / 1.00 | – | – | 1981 | 63 | 37.6 → 50.9 | 32.6 / 0.1 / 10.8 | 522 / 1475 / 599 |
| dev_A02_fcv_seize_fast | 1 | 2026-10-21 03:00 | 80 | 105 | 58 / 0 / 0 | 51 / 0 | 3.48 | 0 | 57,188 | 0.62 | 0.47 | 0.03 | 1.00 | 0.29 / 1.00 | 5.7 | – | 2508 | 82 | 41.7 → 54.8 | 37.9 / 0.1 / 16.2 | 524 / 1475 / 620 |
| dev_B01_tube_leak | 1 | 2026-10-21 03:04 | 170 | 120 | 60 / 0 / 0 | 70 / 0 | 2.49 | 0 | 61,867 | 0.95 | 0.47 | 0.95 | 1.00 | 0.57 / 1.00 | – | – | 1903 | 104 | 42.4 → 58.5 | 60.7 / 0.1 / 14.5 | 527 / 1475 / 638 |
| dev_B02_tube_leak_fast | 1 | 2026-10-21 03:08 | 80 | 39 | 19 / 0 / 0 | 34 / 0 | 1.98 | 0 | 17,202 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 / 0.75 | – | – | 1456 | 35 | 42.4 → 55.2 | 20.4 / 0.1 / 2.4 | 522 / 1474 / 641 |
| dev_C01_wet_coal | 1 | 2026-10-21 03:11 | 170 | 50 | 25 / 0 / 0 | 27 / 0 | 1.18 | 0 | 34,274 | 0.55 | 0.72 | – | 0.91 | 0.40 / 1.00 | – | – | 2134 | 56 | 42.4 → 55.4 | 26.6 / 0.1 / 9.1 | 521 / 1474 / 653 |
| dev_C02_feeder_trip | 1 | 2026-10-21 03:15 | 100 | 117 | 63 / 0 / 0 | 54 / 0 | 3.34 | 0 | 54,318 | 0.60 | 0.91 | 0.13 | 0.93 | 0.27 / 1.00 | – | – | 2784 | 88 | 42.0 → 57.5 | 45.5 / 0.1 / 15.2 | 527 / 1475 / 674 |
| dev_D01_high_cv_coal | 1 | 2026-10-21 03:22 | 310 | 223 | 112 / 0 / 0 | 146 / 0 | 2.69 | 0 | 165,813 | 0.80 | 0.78 | 0.80 | 0.98 | 0.44 / 1.00 | 82.3 | – | 2348 | 245 | 42.0 → 61.4 | 115.4 / 0.2 / 43.0 | 539 / 1475 / 740 |
| dev_D03_high_cv_severe | 1 | 2026-10-21 03:29 | 150 | 90 | 45 / 0 / 0 | 76 / 0 | 2.40 | 0 | 71,487 | 0.94 | 0.94 | 0.94 | 0.92 | 0.57 / 1.00 | 43.2 | – | 2154 | 98 | 42.4 → 57.5 | 49.1 / 0.1 / 16.1 | 525 / 1474 / 764 |
| dev_N01_normal | 1 | 2026-10-21 03:32 | 80 | 0 | 0 / 0 / 0 | 0 / 0 | 0.00 | 0 | 0 | – | – | – | 1.00 | – | – | 0.00 | 3 | 6 | 42.4 → 43.6 | 0.0 / 0.0 / 0.0 | 489 / 1475 / 764 |
| dev_N02_normal | 1 | 2026-10-21 03:33 | 110 | 2 | 1 / 0 / 0 | 1 / 0 | 0.07 | 0 | 788 | – | – | – | 1.00 | – | – | 1.09 | 7 | 8 | 42.0 → 43.6 | 1.3 / 0.0 / 0.2 | 504 / 1475 / 764 |

## bev ideas per episode

| episode | run | idea | calls | failed | rejected | used | shadow | other counters |
|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | explain | 31 | 0 | 0 | 31 | 0 | over_limit 0 |
| dev_A02_fcv_seize_fast | 1 | clear_skip | 0 | 0 | 0 | 4 | 0 | – |
| dev_A02_fcv_seize_fast | 1 | explain | 36 | 0 | 0 | 36 | 0 | over_limit 0 |
| dev_A02_fcv_seize_fast | 1 | verifier | 22 | 0 | 0 | 11 | 0 | over_limit 0 |
| dev_B01_tube_leak | 1 | clear_skip | 0 | 0 | 0 | 10 | 0 | – |
| dev_B01_tube_leak | 1 | explain | 53 | 0 | 0 | 53 | 0 | over_limit 0 |
| dev_B01_tube_leak | 1 | verifier | 7 | 0 | 0 | 7 | 0 | over_limit 0 |
| dev_B02_tube_leak_fast | 1 | clear_skip | 0 | 0 | 0 | 15 | 0 | – |
| dev_B02_tube_leak_fast | 1 | explain | 19 | 0 | 0 | 19 | 0 | over_limit 0 |
| dev_C01_wet_coal | 1 | clear_skip | 0 | 0 | 0 | 2 | 0 | – |
| dev_C01_wet_coal | 1 | explain | 25 | 0 | 0 | 25 | 0 | over_limit 0 |
| dev_C02_feeder_trip | 1 | explain | 42 | 0 | 0 | 42 | 0 | over_limit 0 |
| dev_C02_feeder_trip | 1 | verifier | 21 | 0 | 0 | 12 | 0 | over_limit 0 |
| dev_D01_high_cv_coal | 1 | clear_skip | 0 | 0 | 0 | 36 | 0 | – |
| dev_D01_high_cv_coal | 1 | explain | 103 | 0 | 0 | 103 | 0 | over_limit 0 |
| dev_D01_high_cv_coal | 1 | verifier | 9 | 0 | 0 | 7 | 0 | over_limit 0 |
| dev_D03_high_cv_severe | 1 | clear_skip | 0 | 0 | 0 | 31 | 0 | – |
| dev_D03_high_cv_severe | 1 | explain | 45 | 0 | 0 | 45 | 0 | over_limit 0 |
| dev_N02_normal | 1 | explain | 1 | 0 | 0 | 1 | 0 | over_limit 0 |

Board resources (on-board sampler, once a second, per episode): CPU seconds and peak memory of each model server. The NPU has no readable usage counter; its work shows as the NPU lane's call time. Supply power, if the board exposes it, is in each summary's `meta.resources`; energy is never estimated.
