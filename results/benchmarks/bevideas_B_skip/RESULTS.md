# Benchmark `bevideas_B_skip`

Architecture **multi**, mode **lockstep**, overlay `configs/bev_ideas.yaml`, merge rule `hybrid`, models npu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`, cpu: `gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf`, bev: `bev-decider-0.4B-backbone-Q8_0.gguf`. Agent code ran on the laptop and only model calls on the board, so tick times are laptop times. Energy not measured. All plant data is synthetic.

bev ideas switches: `clear_skip=on`. bev-decide on npu. bev idea calls: answered by bev-decide (failed = no answer, which makes the run invalid and is not kept; rejected = refused by the gate's check). used = an answer that changed what the agent did; shadow = asked and only logged. Decode tokens per tick: answer tokens written by every model per tick (bev writes none).

Group top-1 is the share of scored ticks (fault onset onward) whose published rank-1 cause is in the true case's look-alike group; belief group top-1 is the same for the code-only ranking. A held-out true case has no exact top-1. Unusable = a model answer that was not used (wrong format, failed call, rejected note reading). Settings and every run, stopped ones included: `test.json`.

| episode | run | finished | ticks | model calls | bev idea calls / failed / rejected | bev used / shadow | decode tokens per tick | unusable | tokens in | group top-1 | belief group top-1 | exact top-1 | faithfulness | actions P / R | lead time min | false alarms /h | tick p95 ms | wall s | chip C | server CPU s npu / cpu / bev | peak RSS MB npu / cpu / bev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | 2026-10-19 19:01 | 130 | 31 | 0 / 0 / 0 | 0 / 0 | 8.21 | 0 | 21,084 | 0.61 | 0.02 | 0.47 | 0.99 | 0.31 / 1.00 | – | – | 3670 | 111 | 53.5 → 61.7 | 153.2 / 0.1 / 0.0 | 524 / 1469 / 1058 |
| dev_A02_fcv_seize_fast | 1 | 2026-10-19 19:04 | 80 | 46 | 0 / 0 / 0 | 7 / 0 | 17.52 | 0 | 27,650 | 0.62 | 0.47 | 0.02 | 1.00 | 0.29 / 1.00 | -9.3 | – | 5077 | 136 | 54.0 → 63.7 | 153.9 / 127.9 / 0.0 | 523 / 1558 / 1058 |
| dev_B01_tube_leak | 1 | 2026-10-19 19:08 | 170 | 60 | 0 / 0 / 0 | 11 / 0 | 9.99 | 0 | 42,635 | 0.95 | 0.47 | 0.95 | 1.00 | 0.57 / 1.00 | – | – | 3400 | 188 | 55.2 → 64.1 | 219.2 / 72.8 / 0.1 | 530 / 1547 / 1058 |
| dev_B02_tube_leak_fast | 1 | 2026-10-19 19:09 | 80 | 19 | 0 / 0 / 0 | 16 / 0 | 6.45 | 0 | 13,470 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 / 0.75 | – | – | 2831 | 60 | 56.3 → 63.3 | 70.2 / 0.1 / 0.0 | 524 / 1469 / 1058 |
| dev_C01_wet_coal | 1 | 2026-10-19 19:12 | 170 | 25 | 0 / 0 / 0 | 2 / 0 | 5.40 | 0 | 18,875 | 0.47 | 0.72 | – | 0.90 | 0.40 / 1.00 | – | – | 3797 | 96 | 54.8 → 62.5 | 125.7 / 0.1 / 0.0 | 523 / 1469 / 1058 |
| dev_C02_feeder_trip | 1 | 2026-10-19 19:15 | 100 | 58 | 0 / 0 / 0 | 0 / 0 | 18.96 | 0 | 36,511 | 0.43 | 0.91 | 0.39 | 0.94 | 0.33 / 1.00 | – | – | 6183 | 185 | 54.4 → 65.5 | 208.7 / 172.1 / 0.1 | 525 / 1556 / 1058 |
| dev_D01_high_cv_coal | 1 | 2026-10-19 19:22 | 310 | 99 | 0 / 0 / 0 | 52 / 0 | 11.52 | 0 | 71,010 | 0.80 | 0.78 | 0.80 | 0.98 | 0.44 / 1.00 | 82.3 | – | 4037 | 363 | 56.3 → 65.2 | 467.2 / 80.7 / 0.1 | 535 / 1545 / 1058 |
| dev_D03_high_cv_severe | 1 | 2026-10-19 19:25 | 150 | 45 | 0 / 0 / 0 | 30 / 0 | 10.07 | 0 | 32,342 | 0.94 | 0.94 | 0.94 | 0.92 | 0.57 / 1.00 | 43.2 | – | 3619 | 156 | 56.7 → 65.6 | 206.1 / 0.2 / 0.0 | 525 / 1469 / 1058 |
| dev_N01_normal | 1 | 2026-10-19 19:26 | 80 | 0 | 0 / 0 / 0 | 0 / 0 | 0.00 | 0 | 0 | – | – | – | 1.00 | – | – | 0.00 | 5 | 6 | 56.7 → 55.2 | 0.0 / 0.0 / 0.0 | 484 / 1469 / 1058 |
| dev_N02_normal | 1 | 2026-10-19 19:27 | 110 | 1 | 0 / 0 / 0 | 0 / 0 | 0.25 | 0 | 677 | – | – | – | 1.00 | – | – | 1.09 | 11 | 10 | 54.3 → 56.0 | 3.9 / 0.0 / 0.0 | 509 / 1470 / 1058 |

## bev ideas per episode

| episode | run | idea | calls | failed | rejected | used | shadow | other counters |
|---|---|---|---|---|---|---|---|---|
| dev_A02_fcv_seize_fast | 1 | clear_skip | 0 | 0 | 0 | 7 | 0 | – |
| dev_B01_tube_leak | 1 | clear_skip | 0 | 0 | 0 | 11 | 0 | – |
| dev_B02_tube_leak_fast | 1 | clear_skip | 0 | 0 | 0 | 16 | 0 | – |
| dev_C01_wet_coal | 1 | clear_skip | 0 | 0 | 0 | 2 | 0 | – |
| dev_D01_high_cv_coal | 1 | clear_skip | 0 | 0 | 0 | 52 | 0 | – |
| dev_D03_high_cv_severe | 1 | clear_skip | 0 | 0 | 0 | 30 | 0 | – |

Board resources (on-board sampler, once a second, per episode): CPU seconds and peak memory of each model server. The NPU has no readable usage counter; its work shows as the NPU lane's call time. Supply power, if the board exposes it, is in each summary's `meta.resources`; energy is never estimated.
