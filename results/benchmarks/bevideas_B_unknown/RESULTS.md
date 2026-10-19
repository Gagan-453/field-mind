# Benchmark `bevideas_B_unknown`

Architecture **multi**, mode **lockstep**, overlay `configs/bev_ideas.yaml`, merge rule `hybrid`, models npu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`, cpu: `gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf`, bev: `bev-decider-0.4B-backbone-Q8_0.gguf`. Agent code ran on the laptop and only model calls on the board, so tick times are laptop times. Energy not measured. All plant data is synthetic.

bev ideas switches: `unknown=on`. bev-decide on npu. bev idea calls: answered by bev-decide (failed = no answer, which makes the run invalid and is not kept; rejected = refused by the gate's check). used = an answer that changed what the agent did; shadow = asked and only logged. Decode tokens per tick: answer tokens written by every model per tick (bev writes none).

Group top-1 is the share of scored ticks (fault onset onward) whose published rank-1 cause is in the true case's look-alike group; belief group top-1 is the same for the code-only ranking. A held-out true case has no exact top-1. Unusable = a model answer that was not used (wrong format, failed call, rejected note reading). Settings and every run, stopped ones included: `test.json`.

| episode | run | finished | ticks | model calls | bev idea calls / failed / rejected | bev used / shadow | decode tokens per tick | unusable | tokens in | group top-1 | belief group top-1 | exact top-1 | faithfulness | actions P / R | lead time min | false alarms /h | tick p95 ms | wall s | chip C | server CPU s npu / cpu / bev | peak RSS MB npu / cpu / bev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | 2026-10-19 17:22 | 130 | 88 | 57 / 0 / 0 | 57 / 0 | 8.08 | 0 | 35,245 | 0.61 | 0.02 | 0.47 | 0.99 | 0.31 / 1.00 | – | – | 3911 | 124 | 51.3 → 61.0 | 148.4 / 0.1 / 8.3 | 528 / 1469 / 980 |
| dev_A02_fcv_seize_fast | 1 | 2026-10-19 17:25 | 80 | 115 | 64 / 0 / 0 | 64 / 0 | 19.50 | 0 | 50,598 | 0.62 | 0.47 | 0.02 | 1.00 | 0.29 / 1.00 | -9.3 | – | 5472 | 170 | 53.6 → 61.7 | 172.7 / 126.2 / 9.8 | 525 / 1554 / 816 |
| dev_B01_tube_leak | 1 | 2026-10-19 17:30 | 170 | 193 | 128 / 0 / 0 | 128 / 0 | 10.80 | 0 | 83,283 | 0.95 | 0.47 | 0.95 | 1.00 | 0.57 / 1.00 | – | – | 3650 | 239 | 54.4 → 66.7 | 234.2 / 72.2 / 18.3 | 527 / 1556 / 846 |
| dev_B02_tube_leak_fast | 1 | 2026-10-19 17:33 | 80 | 75 | 51 / 0 / 0 | 51 / 0 | 8.22 | 0 | 31,361 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 / 0.75 | – | – | 3192 | 90 | 52.9 → 61.4 | 88.9 / 0.1 / 7.3 | 522 / 1469 / 859 |
| dev_C01_wet_coal | 1 | 2026-10-19 17:35 | 170 | 79 | 52 / 0 / 0 | 52 / 0 | 5.90 | 0 | 33,752 | 0.45 | 0.72 | – | 0.90 | 0.33 / 0.75 | – | – | 4099 | 117 | 54.0 → 61.7 | 134.7 / 0.1 / 7.4 | 522 / 1469 / 872 |
| dev_C02_feeder_trip | 1 | 2026-10-19 17:39 | 100 | 135 | 77 / 0 / 0 | 77 / 0 | 18.95 | 0 | 56,811 | 0.46 | 0.91 | 0.39 | 0.94 | 0.33 / 1.00 | – | – | 6416 | 209 | 54.8 → 64.8 | 210.4 / 167.5 / 11.5 | 528 / 1548 / 891 |
| dev_D01_high_cv_coal | 1 | 2026-10-19 17:50 | 310 | 384 | 250 / 0 / 0 | 250 / 0 | 15.82 | 0 | 170,736 | 0.80 | 0.78 | 0.80 | 0.98 | 0.44 / 1.00 | 82.3 | – | 4459 | 575 | 53.2 → 64.8 | 654.1 / 79.7 / 37.9 | 540 / 1556 / 968 |
| dev_D03_high_cv_severe | 1 | 2026-10-19 17:55 | 150 | 188 | 132 / 0 / 0 | 132 / 0 | 12.41 | 0 | 85,144 | 0.94 | 0.94 | 0.94 | 0.92 | 0.57 / 1.00 | 43.2 | – | 3991 | 232 | 54.4 → 64.1 | 251.8 / 0.2 / 19.9 | 527 / 1468 / 1009 |
| dev_N01_normal | 1 | 2026-10-19 17:56 | 80 | 0 | 0 / 0 / 0 | 0 / 0 | 0.00 | 0 | 0 | – | – | – | 1.00 | – | – | 0.00 | 6 | 7 | 53.2 → 53.6 | 0.0 / 0.0 / 0.0 | 484 / 1469 / 1009 |
| dev_N02_normal | 1 | 2026-10-19 17:57 | 110 | 2 | 1 / 0 / 0 | 1 / 0 | 0.25 | 0 | 924 | – | – | – | 1.00 | – | – | 1.09 | 13 | 10 | 52.9 → 53.5 | 3.3 / 0.0 / 0.2 | 509 / 1469 / 1009 |

## bev ideas per episode

| episode | run | idea | calls | failed | rejected | used | shadow | other counters |
|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | unknown | 57 | 0 | 0 | 57 | 0 | over_limit 0 |
| dev_A02_fcv_seize_fast | 1 | unknown | 64 | 0 | 0 | 64 | 0 | over_limit 0 |
| dev_B01_tube_leak | 1 | unknown | 128 | 0 | 0 | 128 | 0 | over_limit 0 |
| dev_B02_tube_leak_fast | 1 | unknown | 51 | 0 | 0 | 51 | 0 | over_limit 0 |
| dev_C01_wet_coal | 1 | unknown | 52 | 0 | 0 | 52 | 0 | over_limit 0 |
| dev_C02_feeder_trip | 1 | unknown | 77 | 0 | 0 | 77 | 0 | over_limit 0 |
| dev_D01_high_cv_coal | 1 | unknown | 250 | 0 | 0 | 250 | 0 | over_limit 0 |
| dev_D03_high_cv_severe | 1 | unknown | 132 | 0 | 0 | 132 | 0 | over_limit 0 |
| dev_N02_normal | 1 | unknown | 1 | 0 | 0 | 1 | 0 | over_limit 0 |

Board resources (on-board sampler, once a second, per episode): CPU seconds and peak memory of each model server. The NPU has no readable usage counter; its work shows as the NPU lane's call time. Supply power, if the board exposes it, is in each summary's `meta.resources`; energy is never estimated.
