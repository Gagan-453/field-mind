# Benchmark `bevideas_B_notes`

Architecture **multi**, mode **lockstep**, overlay `configs/bev_ideas.yaml`, merge rule `hybrid`, models npu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`, cpu: `gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf`, bev: `bev-decider-0.4B-backbone-Q8_0.gguf`. Agent code ran on the laptop and only model calls on the board, so tick times are laptop times. Energy not measured. All plant data is synthetic.

bev ideas switches: `notes=on`. bev-decide on npu. bev idea calls: answered by bev-decide (failed = no answer, which makes the run invalid and is not kept; rejected = refused by the gate's check). used = an answer that changed what the agent did; shadow = asked and only logged. Decode tokens per tick: answer tokens written by every model per tick (bev writes none).

Group top-1 is the share of scored ticks (fault onset onward) whose published rank-1 cause is in the true case's look-alike group; belief group top-1 is the same for the code-only ranking. A held-out true case has no exact top-1. Unusable = a model answer that was not used (wrong format, failed call, rejected note reading). Settings and every run, stopped ones included: `test.json`.

| episode | run | finished | ticks | model calls | bev idea calls / failed / rejected | bev used / shadow | decode tokens per tick | unusable | tokens in | group top-1 | belief group top-1 | exact top-1 | faithfulness | actions P / R | lead time min | false alarms /h | tick p95 ms | wall s | chip C | server CPU s npu / cpu / bev | peak RSS MB npu / cpu / bev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | 2026-10-19 18:29 | 130 | 32 | 1 / 0 / 0 | 1 / 0 | 7.47 | 0 | 20,074 | 0.56 | 0.02 | 0.42 | 0.99 | 0.31 / 1.00 | – | – | 3133 | 100 | 53.1 → 61.0 | 135.9 / 0.1 / 0.3 | 523 / 1469 / 1056 |
| dev_A02_fcv_seize_fast | 1 | 2026-10-19 18:33 | 80 | 51 | 0 / 0 / 0 | 0 / 0 | 19.57 | 0 | 30,739 | 0.62 | 0.47 | 0.02 | 1.00 | 0.29 / 1.00 | -9.3 | – | 5080 | 152 | 53.2 → 63.7 | 173.8 / 133.8 / 0.0 | 524 / 1554 / 1056 |
| dev_B01_tube_leak | 1 | 2026-10-19 18:36 | 170 | 66 | 1 / 0 / 0 | 1 / 0 | 10.58 | 0 | 44,451 | 0.95 | 0.47 | 0.95 | 1.00 | 0.57 / 1.00 | – | – | 3304 | 197 | 54.8 → 64.1 | 232.4 / 74.2 / 0.2 | 528 / 1547 / 1056 |
| dev_B02_tube_leak_fast | 1 | 2026-10-19 18:38 | 80 | 24 | 0 / 0 / 0 | 0 / 0 | 8.11 | 0 | 17,132 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 / 0.75 | – | – | 2896 | 74 | 56.0 → 62.5 | 92.5 / 0.1 / 0.0 | 521 / 1469 / 1056 |
| dev_C01_wet_coal | 1 | 2026-10-19 18:41 | 170 | 28 | 1 / 0 / 0 | 1 / 0 | 5.55 | 0 | 19,635 | 0.45 | 0.72 | – | 0.90 | 0.33 / 0.75 | – | – | 3773 | 100 | 54.0 → 61.7 | 132.5 / 0.1 / 0.3 | 528 / 1469 / 1057 |
| dev_C02_feeder_trip | 1 | 2026-10-19 18:44 | 100 | 58 | 0 / 0 / 0 | 0 / 0 | 18.85 | 0 | 36,511 | 0.43 | 0.91 | 0.39 | 0.94 | 0.33 / 1.00 | – | – | 6056 | 183 | 54.4 → 64.1 | 206.6 / 171.1 / 0.1 | 529 / 1556 / 1057 |
| dev_D01_high_cv_coal | 1 | 2026-10-19 18:53 | 310 | 135 | 1 / 0 / 0 | 1 / 0 | 15.69 | 0 | 94,402 | 0.80 | 0.78 | 0.80 | 0.98 | 0.44 / 1.00 | 82.3 | – | 4192 | 495 | 56.7 → 65.2 | 649.6 / 81.2 / 0.4 | 542 / 1553 / 1057 |
| dev_D03_high_cv_severe | 1 | 2026-10-19 18:57 | 150 | 56 | 1 / 0 / 0 | 1 / 0 | 12.23 | 0 | 39,739 | 0.94 | 0.94 | 0.94 | 0.92 | 0.57 / 1.00 | 43.2 | – | 3751 | 191 | 57.1 → 65.2 | 253.3 / 0.2 / 0.3 | 527 / 1469 / 1058 |
| dev_N01_normal | 1 | 2026-10-19 18:58 | 80 | 0 | 0 / 0 / 0 | 0 / 0 | 0.00 | 0 | 0 | – | – | – | 1.00 | – | – | 0.00 | 5 | 7 | 56.7 → 55.2 | 0.0 / 0.0 / 0.0 | 483 / 1469 / 1058 |
| dev_N02_normal | 1 | 2026-10-19 18:59 | 110 | 1 | 0 / 0 / 0 | 0 / 0 | 0.25 | 0 | 677 | – | – | – | 1.00 | – | – | 1.09 | 13 | 10 | 54.4 → 55.6 | 3.8 / 0.0 / 0.0 | 510 / 1469 / 1058 |

## bev ideas per episode

| episode | run | idea | calls | failed | rejected | used | shadow | other counters |
|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | notes | 1 | 0 | 0 | 1 | 0 | over_limit 0 |
| dev_B01_tube_leak | 1 | notes | 1 | 0 | 0 | 1 | 0 | over_limit 0 |
| dev_C01_wet_coal | 1 | notes | 1 | 0 | 0 | 1 | 0 | over_limit 0 |
| dev_D01_high_cv_coal | 1 | notes | 1 | 0 | 0 | 1 | 0 | over_limit 0 |
| dev_D03_high_cv_severe | 1 | notes | 1 | 0 | 0 | 1 | 0 | over_limit 0 |

Board resources (on-board sampler, once a second, per episode): CPU seconds and peak memory of each model server. The NPU has no readable usage counter; its work shows as the NPU lane's call time. Supply power, if the board exposes it, is in each summary's `meta.resources`; energy is never estimated.
