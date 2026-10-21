# Benchmark `bevideas_A_soak`

Architecture **multi**, mode **lockstep**, overlay `configs/bev_ideas.yaml`, merge rule `hybrid`, models npu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`, cpu: `gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf`, bev: `bev-decider-0.4B-backbone-Q8_0.gguf`. Agent code ran on the laptop and only model calls on the board, so tick times are laptop times. Energy not measured. All plant data is synthetic.

Group top-1 is the share of scored ticks (fault onset onward) whose published rank-1 cause is in the true case's look-alike group; belief group top-1 is the same for the code-only ranking. A held-out true case has no exact top-1. Unusable = a model answer that was not used (wrong format, failed call, rejected note reading). Settings and every run, stopped ones included: `test.json`.

| episode | run | finished | ticks | model calls | unusable | tokens in | group top-1 | belief group top-1 | exact top-1 | faithfulness | actions P / R | lead time min | false alarms /h | tick p95 ms | wall s | chip C | server CPU s npu / cpu / bev | peak RSS MB npu / cpu / bev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | 2026-10-21 04:55 | 130 | 31 | 0 | 21,084 | 0.56 | 0.02 | 0.42 | 0.99 | 0.29 / 1.00 | – | – | 3370 | 98 | 37.8 → 55.6 | 143.2 / 0.1 / 0.0 | 527 / 1474 / 763 |
| dev_A02_fcv_seize_fast | 1 | 2026-10-21 04:58 | 80 | 51 | 0 | 30,739 | 0.62 | 0.47 | 0.02 | 1.00 | 0.29 / 1.00 | -9.3 | – | 4908 | 144 | 54.0 → 62.5 | 168.7 / 123.3 / 0.0 | 529 / 1559 / 763 |
| dev_B01_tube_leak | 1 | 2026-10-21 05:02 | 170 | 65 | 0 | 46,317 | 0.95 | 0.47 | 0.95 | 1.00 | 0.57 / 1.00 | – | – | 3383 | 202 | 59.8 → 65.9 | 236.5 / 75.6 / 0.1 | 538 / 1552 / 763 |
| dev_B02_tube_leak_fast | 1 | 2026-10-21 05:03 | 80 | 24 | 0 | 17,132 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 / 0.75 | – | – | 3236 | 79 | 63.3 → 65.2 | 95.5 / 0.1 / 0.0 | 527 / 1474 / 763 |
| dev_C01_wet_coal | 1 | 2026-10-21 05:05 | 170 | 27 | 0 | 20,418 | 0.45 | 0.72 | – | 0.90 | 0.33 / 0.75 | – | – | 4029 | 106 | 62.9 → 65.6 | 136.1 / 0.1 / 0.0 | 527 / 1474 / 763 |
| dev_C02_feeder_trip | 1 | 2026-10-21 05:09 | 100 | 58 | 0 | 36,511 | 0.43 | 0.91 | 0.39 | 0.94 | 0.33 / 1.00 | – | – | 6646 | 195 | 63.3 → 67.2 | 211.7 / 181.0 / 0.1 | 533 / 1570 / 763 |
| dev_D01_high_cv_coal | 1 | 2026-10-21 05:18 | 310 | 134 | 0 | 97,122 | 0.80 | 0.78 | 0.80 | 0.98 | 0.44 / 1.00 | 82.3 | – | 4439 | 522 | 64.8 → 67.2 | 664.9 / 85.9 / 0.2 | 547 / 1555 / 763 |
| dev_D03_high_cv_severe | 1 | 2026-10-21 05:22 | 150 | 56 | 0 | 40,405 | 0.94 | 0.94 | 0.94 | 0.92 | 0.57 / 1.00 | 43.2 | – | 3799 | 202 | 64.8 → 67.9 | 258.4 / 0.2 / 0.1 | 532 / 1474 / 763 |
| dev_N01_normal | 1 | 2026-10-21 05:22 | 80 | 0 | 0 | 0 | – | – | – | 1.00 | – | – | 0.00 | 3 | 6 | 64.8 → 60.6 | 0.0 / 0.0 / 0.0 | 488 / 1474 / 763 |
| dev_N02_normal | 1 | 2026-10-21 05:23 | 110 | 1 | 0 | 677 | – | – | – | 1.00 | – | – | 1.09 | 7 | 10 | 59.8 → 59.8 | 3.5 / 0.0 / 0.0 | 514 / 1474 / 763 |

Board resources (on-board sampler, once a second, per episode): CPU seconds and peak memory of each model server. The NPU has no readable usage counter; its work shows as the NPU lane's call time. Supply power, if the board exposes it, is in each summary's `meta.resources`; energy is never estimated.
