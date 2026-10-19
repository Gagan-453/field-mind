# Benchmark `bevideas_A2`

Architecture **multi**, mode **lockstep**, overlay `configs/bev_ideas.yaml`, merge rule `hybrid`, models npu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`, cpu: `gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf`, bev: `bev-decider-0.4B-backbone-Q8_0.gguf`. Agent code ran on the laptop and only model calls on the board, so tick times are laptop times. Energy not measured. All plant data is synthetic.

Group top-1 is the share of scored ticks (fault onset onward) whose published rank-1 cause is in the true case's look-alike group; belief group top-1 is the same for the code-only ranking. A held-out true case has no exact top-1. Unusable = a model answer that was not used (wrong format, failed call, rejected note reading). Settings and every run, stopped ones included: `test.json`.

| episode | run | finished | ticks | model calls | unusable | tokens in | group top-1 | belief group top-1 | exact top-1 | faithfulness | actions P / R | lead time min | false alarms /h | tick p95 ms | wall s | chip C | server CPU s npu / cpu / bev | peak RSS MB npu / cpu / bev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | 2026-10-19 19:29 | 130 | 31 | 0 | 21,084 | 0.56 | 0.02 | 0.42 | 0.99 | 0.31 / 1.00 | – | – | 3487 | 107 | 53.6 → 63.7 | 143.1 / 0.1 / 0.0 | 524 / 1469 / 1058 |
| dev_A02_fcv_seize_fast | 1 | 2026-10-19 19:32 | 80 | 51 | 0 | 30,739 | 0.62 | 0.47 | 0.02 | 1.00 | 0.29 / 1.00 | -9.3 | – | 5153 | 153 | 55.2 → 64.5 | 170.4 / 129.6 / 0.1 | 533 / 1553 / 1058 |
| dev_B01_tube_leak | 1 | 2026-10-19 19:36 | 170 | 65 | 0 | 46,317 | 0.95 | 0.47 | 0.95 | 1.00 | 0.57 / 1.00 | – | – | 3443 | 206 | 57.4 → 67.4 | 237.9 / 75.0 / 0.1 | 539 / 1560 / 1058 |
| dev_B02_tube_leak_fast | 1 | 2026-10-19 19:38 | 80 | 24 | 0 | 17,132 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 / 0.75 | – | – | 3090 | 77 | 57.5 → 64.0 | 91.9 / 0.1 / 0.0 | 522 / 1469 / 1058 |
| dev_C01_wet_coal | 1 | 2026-10-19 19:41 | 170 | 27 | 0 | 20,418 | 0.51 | 0.72 | – | 0.90 | 0.33 / 0.75 | – | – | 3894 | 106 | 56.0 → 64.1 | 137.4 / 0.1 / 0.0 | 522 / 1469 / 1058 |
| dev_C02_feeder_trip | 1 | 2026-10-19 19:44 | 100 | 58 | 0 | 36,511 | 0.43 | 0.91 | 0.39 | 0.94 | 0.33 / 1.00 | – | – | 6309 | 189 | 56.7 → 66.7 | 209.7 / 176.2 / 0.1 | 536 / 1563 / 1058 |
| dev_D01_high_cv_coal | 1 | 2026-10-19 19:54 | 310 | 134 | 0 | 97,122 | 0.80 | 0.78 | 0.80 | 0.98 | 0.44 / 1.00 | 82.3 | – | 4291 | 513 | 57.9 → 67.2 | 663.9 / 83.5 / 0.1 | 555 / 1550 / 1058 |
| dev_D03_high_cv_severe | 1 | 2026-10-19 19:58 | 150 | 56 | 0 | 40,405 | 0.94 | 0.94 | 0.94 | 0.92 | 0.57 / 1.00 | 43.2 | – | 3923 | 196 | 56.3 → 66.0 | 257.3 / 0.2 / 0.1 | 528 / 1468 / 1058 |
| dev_N01_normal | 1 | 2026-10-19 19:59 | 80 | 0 | 0 | 0 | – | – | – | 1.00 | – | – | 0.00 | 5 | 7 | 58.3 → 56.7 | 0.0 / 0.0 / 0.0 | 483 / 1468 / 1058 |
| dev_N02_normal | 1 | 2026-10-19 19:59 | 110 | 1 | 0 | 677 | – | – | – | 1.00 | – | – | 1.09 | 11 | 10 | 56.0 → 56.6 | 3.9 / 0.0 / 0.0 | 509 / 1469 / 1058 |

Board resources (on-board sampler, once a second, per episode): CPU seconds and peak memory of each model server. The NPU has no readable usage counter; its work shows as the NPU lane's call time. Supply power, if the board exposes it, is in each summary's `meta.resources`; energy is never estimated.
