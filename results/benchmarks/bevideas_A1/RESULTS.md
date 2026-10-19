# Benchmark `bevideas_A1`

Architecture **multi**, mode **lockstep**, overlay `configs/bev_ideas.yaml`, merge rule `hybrid`, models npu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`, cpu: `gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf`, bev: `bev-decider-0.4B-backbone-Q8_0.gguf`. Agent code ran on the laptop and only model calls on the board, so tick times are laptop times. Energy not measured. All plant data is synthetic.

Group top-1 is the share of scored ticks (fault onset onward) whose published rank-1 cause is in the true case's look-alike group; belief group top-1 is the same for the code-only ranking. A held-out true case has no exact top-1. Unusable = a model answer that was not used (wrong format, failed call, rejected note reading). Settings and every run, stopped ones included: `test.json`.

| episode | run | finished | ticks | model calls | unusable | tokens in | group top-1 | belief group top-1 | exact top-1 | faithfulness | actions P / R | lead time min | false alarms /h | tick p95 ms | wall s | chip C | server CPU s npu / cpu / bev | peak RSS MB npu / cpu / bev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | 2026-10-19 15:28 | 130 | 31 | 0 | 21,084 | 0.56 | 0.02 | 0.42 | 0.99 | 0.31 / 1.00 | – | – | 3389 | 99 | 38.6 → 56.0 | 142.0 / 0.1 / 0.0 | 530 / 1476 / 968 |
| dev_A02_fcv_seize_fast | 1 | 2026-10-19 15:32 | 80 | 51 | 0 | 30,739 | 0.62 | 0.47 | 0.02 | 1.00 | 0.29 / 1.00 | -9.3 | – | 4809 | 139 | 42.0 → 59.8 | 168.6 / 118.0 / 0.0 | 534 / 1567 / 968 |
| dev_B01_tube_leak | 1 | 2026-10-19 15:39 | 170 | 65 | 0 | 46,317 | 0.95 | 0.47 | 0.95 | 1.00 | 0.57 / 1.00 | – | – | 3081 | 186 | 42.0 → 60.6 | 231.6 / 66.8 / 0.1 | 534 / 1562 / 968 |
| dev_B02_tube_leak_fast | 1 | 2026-10-19 15:43 | 80 | 24 | 0 | 17,132 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 / 0.75 | – | – | 2639 | 68 | 42.0 → 56.0 | 91.7 / 0.1 / 0.0 | 530 / 1475 / 968 |
| dev_C01_wet_coal | 1 | 2026-10-19 15:47 | 170 | 27 | 0 | 20,418 | 0.45 | 0.72 | – | 0.90 | 0.33 / 0.75 | – | – | 3534 | 96 | 42.0 → 56.7 | 131.8 / 0.1 / 0.0 | 529 / 1475 / 968 |
| dev_C02_feeder_trip | 1 | 2026-10-19 15:53 | 100 | 58 | 0 | 36,511 | 0.43 | 0.91 | 0.39 | 0.94 | 0.33 / 1.00 | – | – | 5779 | 172 | 42.0 → 61.0 | 203.0 / 156.8 / 0.1 | 532 / 1571 / 968 |
| dev_D01_high_cv_coal | 1 | 2026-10-19 16:03 | 310 | 134 | 0 | 97,122 | 0.80 | 0.78 | 0.80 | 0.98 | 0.44 / 1.00 | 82.3 | – | 3837 | 464 | 41.8 → 63.7 | 627.9 / 77.5 / 0.1 | 551 / 1556 / 968 |
| dev_D03_high_cv_severe | 1 | 2026-10-19 16:10 | 150 | 56 | 0 | 40,405 | 0.94 | 0.94 | 0.94 | 0.92 | 0.57 / 1.00 | 43.2 | – | 3317 | 172 | 42.0 → 62.5 | 239.2 / 0.2 / 0.1 | 533 / 1475 / 968 |
| dev_N01_normal | 1 | 2026-10-19 16:14 | 80 | 0 | 0 | 0 | – | – | – | 1.00 | – | – | 0.00 | 5 | 7 | 42.0 → 43.2 | 0.0 / 0.0 / 0.0 | 490 / 1476 / 968 |
| dev_N02_normal | 1 | 2026-10-19 16:15 | 110 | 1 | 0 | 677 | – | – | – | 1.00 | – | – | 1.09 | 16 | 10 | 41.7 → 45.3 | 4.0 / 0.0 / 0.0 | 516 / 1475 / 968 |

Board resources (on-board sampler, once a second, per episode): CPU seconds and peak memory of each model server. The NPU has no readable usage counter; its work shows as the NPU lane's call time. Supply power, if the board exposes it, is in each summary's `meta.resources`; energy is never estimated.
