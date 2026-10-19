# Benchmark `bevideas_B_actions`

Architecture **multi**, mode **lockstep**, overlay `configs/bev_ideas.yaml`, merge rule `hybrid`, models npu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`, cpu: `gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf`, bev: `bev-decider-0.4B-backbone-Q8_0.gguf`. Agent code ran on the laptop and only model calls on the board, so tick times are laptop times. Energy not measured. All plant data is synthetic.

bev ideas switches: `actions=on`. bev-decide on npu. bev idea calls: answered by bev-decide (failed = no answer, which makes the run invalid and is not kept; rejected = refused by the gate's check). used = an answer that changed what the agent did; shadow = asked and only logged. Decode tokens per tick: answer tokens written by every model per tick (bev writes none).

Group top-1 is the share of scored ticks (fault onset onward) whose published rank-1 cause is in the true case's look-alike group; belief group top-1 is the same for the code-only ranking. A held-out true case has no exact top-1. Unusable = a model answer that was not used (wrong format, failed call, rejected note reading). Settings and every run, stopped ones included: `test.json`.

| episode | run | finished | ticks | model calls | bev idea calls / failed / rejected | bev used / shadow | decode tokens per tick | unusable | tokens in | group top-1 | belief group top-1 | exact top-1 | faithfulness | actions P / R | lead time min | false alarms /h | tick p95 ms | wall s | chip C | server CPU s npu / cpu / bev | peak RSS MB npu / cpu / bev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | 2026-10-19 16:44 | 130 | 45 | 14 / 0 / 0 | 14 / 0 | 7.92 | 0 | 23,714 | 0.56 | 0.02 | 0.42 | 0.99 | 0.31 / 1.00 | – | – | 3466 | 106 | 47.3 → 59.3 | 137.9 / 0.1 / 2.0 | 523 / 1469 / 1202 |
| dev_A02_fcv_seize_fast | 1 | 2026-10-19 16:47 | 80 | 65 | 14 / 0 / 0 | 14 / 0 | 19.39 | 0 | 35,457 | 0.62 | 0.47 | 0.02 | 1.00 | 0.29 / 1.00 | -9.3 | – | 5077 | 151 | 51.7 → 62.1 | 170.0 / 124.6 / 2.5 | 525 / 1555 / 1206 |
| dev_B01_tube_leak | 1 | 2026-10-19 16:52 | 170 | 67 | 2 / 0 / 0 | 2 / 0 | 10.68 | 0 | 47,085 | 0.95 | 0.47 | 0.95 | 1.00 | 0.57 / 1.00 | – | – | 3317 | 197 | 51.3 → 62.5 | 231.6 / 71.7 / 0.5 | 528 / 1563 / 1207 |
| dev_B02_tube_leak_fast | 1 | 2026-10-19 16:54 | 80 | 24 | 0 / 0 / 0 | 0 / 0 | 8.45 | 0 | 17,132 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 / 0.75 | – | – | 2863 | 75 | 50.2 → 60.8 | 95.3 / 0.1 / 0.0 | 522 / 1469 / 1207 |
| dev_C01_wet_coal | 1 | 2026-10-19 16:57 | 170 | 44 | 17 / 0 / 0 | 17 / 0 | 5.70 | 0 | 26,168 | 0.55 | 0.72 | – | 0.91 | 0.40 / 1.00 | – | – | 3833 | 105 | 51.7 → 59.7 | 129.5 / 0.1 / 3.8 | 522 / 1470 / 1214 |
| dev_C02_feeder_trip | 1 | 2026-10-19 17:01 | 100 | 92 | 34 / 0 / 0 | 34 / 0 | 18.96 | 0 | 46,838 | 0.43 | 0.91 | 0.39 | 0.94 | 0.33 / 1.00 | – | – | 6103 | 192 | 49.8 → 62.4 | 200.7 / 162.8 / 6.9 | 526 / 1558 / 1228 |
| dev_D01_high_cv_coal | 1 | 2026-10-19 17:12 | 310 | 375 | 241 / 0 / 0 | 241 / 0 | 15.89 | 0 | 184,159 | 0.80 | 0.78 | 0.80 | 0.98 | 0.44 / 1.00 | 82.3 | – | 4416 | 587 | 51.3 → 65.2 | 640.5 / 79.7 / 50.2 | 542 / 1562 / 1330 |
| dev_D03_high_cv_severe | 1 | 2026-10-19 17:17 | 150 | 188 | 132 / 0 / 0 | 132 / 0 | 12.33 | 0 | 101,404 | 0.94 | 0.94 | 0.94 | 0.92 | 0.57 / 1.00 | 43.2 | – | 3904 | 242 | 50.2 → 62.9 | 240.6 / 0.2 / 30.4 | 527 / 1469 / 1393 |
| dev_N01_normal | 1 | 2026-10-19 17:19 | 80 | 0 | 0 / 0 / 0 | 0 / 0 | 0.00 | 0 | 0 | – | – | – | 1.00 | – | – | 0.00 | 6 | 7 | 50.9 → 51.3 | 0.0 / 0.0 / 0.0 | 483 / 1469 / 1393 |
| dev_N02_normal | 1 | 2026-10-19 17:19 | 110 | 2 | 1 / 0 / 0 | 1 / 0 | 0.25 | 0 | 958 | – | – | – | 1.00 | – | – | 1.09 | 13 | 10 | 50.5 → 52.9 | 3.7 / 0.0 / 0.2 | 511 / 1469 / 1393 |

## bev ideas per episode

| episode | run | idea | calls | failed | rejected | used | shadow | other counters |
|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | actions | 14 | 0 | 0 | 14 | 0 | over_limit 0 |
| dev_A02_fcv_seize_fast | 1 | actions | 14 | 0 | 0 | 14 | 0 | over_limit 0 |
| dev_B01_tube_leak | 1 | actions | 2 | 0 | 0 | 2 | 0 | over_limit 0 |
| dev_C01_wet_coal | 1 | actions | 17 | 0 | 0 | 17 | 0 | over_limit 0 |
| dev_C02_feeder_trip | 1 | actions | 34 | 0 | 0 | 34 | 0 | over_limit 0 |
| dev_D01_high_cv_coal | 1 | actions | 241 | 0 | 0 | 241 | 0 | over_limit 0 |
| dev_D03_high_cv_severe | 1 | actions | 132 | 0 | 0 | 132 | 0 | over_limit 0 |
| dev_N02_normal | 1 | actions | 1 | 0 | 0 | 1 | 0 | over_limit 0 |

Board resources (on-board sampler, once a second, per episode): CPU seconds and peak memory of each model server. The NPU has no readable usage counter; its work shows as the NPU lane's call time. Supply power, if the board exposes it, is in each summary's `meta.resources`; energy is never estimated.
