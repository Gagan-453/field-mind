# Benchmark `bevideas_B_verifier`

Architecture **multi**, mode **lockstep**, overlay `configs/bev_ideas.yaml`, merge rule `hybrid`, models npu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`, cpu: `gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf`, bev: `bev-decider-0.4B-backbone-Q8_0.gguf`. Agent code ran on the laptop and only model calls on the board, so tick times are laptop times. Energy not measured. All plant data is synthetic.

bev ideas switches: `verifier=on`. bev-decide on npu. bev idea calls: answered by bev-decide (failed = no answer, which makes the run invalid and is not kept; rejected = refused by the gate's check). used = an answer that changed what the agent did; shadow = asked and only logged. Decode tokens per tick: answer tokens written by every model per tick (bev writes none).

Group top-1 is the share of scored ticks (fault onset onward) whose published rank-1 cause is in the true case's look-alike group; belief group top-1 is the same for the code-only ranking. A held-out true case has no exact top-1. Unusable = a model answer that was not used (wrong format, failed call, rejected note reading). Settings and every run, stopped ones included: `test.json`.

| episode | run | finished | ticks | model calls | bev idea calls / failed / rejected | bev used / shadow | decode tokens per tick | unusable | tokens in | group top-1 | belief group top-1 | exact top-1 | faithfulness | actions P / R | lead time min | false alarms /h | tick p95 ms | wall s | chip C | server CPU s npu / cpu / bev | peak RSS MB npu / cpu / bev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | 2026-10-19 17:59 | 130 | 31 | 0 / 0 / 0 | 0 / 0 | 8.07 | 0 | 21,084 | 0.56 | 0.02 | 0.46 | 0.99 | 0.31 / 1.00 | – | – | 3675 | 109 | 52.9 → 64.3 | 148.9 / 0.1 / 0.0 | 528 / 1469 / 1009 |
| dev_A02_fcv_seize_fast | 1 | 2026-10-19 18:02 | 80 | 73 | 22 / 0 / 0 | 11 / 0 | 15.81 | 0 | 34,873 | 0.62 | 0.47 | 0.02 | 1.00 | 0.29 / 1.00 | -9.3 | – | 3838 | 135 | 54.0 → 64.1 | 171.2 / 0.1 / 5.1 | 529 / 1469 / 1022 |
| dev_B01_tube_leak | 1 | 2026-10-19 18:06 | 170 | 72 | 7 / 0 / 0 | 7 / 0 | 9.72 | 0 | 46,817 | 0.95 | 0.47 | 0.95 | 1.00 | 0.57 / 1.00 | – | – | 3316 | 192 | 55.6 → 64.5 | 234.8 / 0.2 / 2.2 | 530 / 1469 / 1029 |
| dev_B02_tube_leak_fast | 1 | 2026-10-19 18:07 | 80 | 24 | 0 / 0 / 0 | 0 / 0 | 8.29 | 0 | 17,132 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 / 0.75 | – | – | 3013 | 76 | 56.7 → 63.3 | 94.7 / 0.1 / 0.0 | 529 / 1469 / 1029 |
| dev_C01_wet_coal | 1 | 2026-10-19 18:10 | 170 | 27 | 0 / 0 / 0 | 0 / 0 | 5.78 | 0 | 20,418 | 0.45 | 0.72 | – | 0.90 | 0.33 / 0.75 | – | – | 3889 | 104 | 55.6 → 62.8 | 138.0 / 0.1 / 0.0 | 527 / 1469 / 1029 |
| dev_C02_feeder_trip | 1 | 2026-10-19 18:13 | 100 | 87 | 29 / 0 / 0 | 16 / 0 | 14.91 | 0 | 39,344 | 0.43 | 0.91 | 0.39 | 0.94 | 0.33 / 1.00 | – | – | 4769 | 162 | 55.2 → 63.3 | 203.6 / 0.2 / 6.1 | 530 / 1469 / 1048 |
| dev_D01_high_cv_coal | 1 | 2026-10-19 18:22 | 310 | 143 | 9 / 0 / 0 | 7 / 0 | 15.36 | 0 | 98,073 | 0.80 | 0.78 | 0.80 | 0.98 | 0.44 / 1.00 | 82.3 | – | 4144 | 485 | 55.6 → 64.5 | 656.1 / 0.5 / 2.5 | 542 / 1469 / 1055 |
| dev_D03_high_cv_severe | 1 | 2026-10-19 18:26 | 150 | 56 | 0 / 0 / 0 | 0 / 0 | 12.39 | 0 | 40,405 | 0.94 | 0.94 | 0.94 | 0.92 | 0.57 / 1.00 | 43.2 | – | 3783 | 192 | 56.7 → 64.8 | 254.2 / 0.2 / 0.1 | 537 / 1469 / 1055 |
| dev_N01_normal | 1 | 2026-10-19 18:27 | 80 | 0 | 0 / 0 / 0 | 0 / 0 | 0.00 | 0 | 0 | – | – | – | 1.00 | – | – | 0.00 | 5 | 6 | 56.3 → 54.4 | 0.0 / 0.0 / 0.0 | 484 / 1469 / 1055 |
| dev_N02_normal | 1 | 2026-10-19 18:27 | 110 | 1 | 0 / 0 / 0 | 0 / 0 | 0.25 | 0 | 677 | – | – | – | 1.00 | – | – | 1.09 | 11 | 10 | 53.6 → 55.2 | 3.6 / 0.0 / 0.0 | 510 / 1469 / 1055 |

## bev ideas per episode

| episode | run | idea | calls | failed | rejected | used | shadow | other counters |
|---|---|---|---|---|---|---|---|---|
| dev_A02_fcv_seize_fast | 1 | verifier | 22 | 0 | 0 | 11 | 0 | over_limit 0 |
| dev_B01_tube_leak | 1 | verifier | 7 | 0 | 0 | 7 | 0 | over_limit 0 |
| dev_C02_feeder_trip | 1 | verifier | 29 | 0 | 0 | 16 | 0 | over_limit 0 |
| dev_D01_high_cv_coal | 1 | verifier | 9 | 0 | 0 | 7 | 0 | over_limit 0 |

Board resources (on-board sampler, once a second, per episode): CPU seconds and peak memory of each model server. The NPU has no readable usage counter; its work shows as the NPU lane's call time. Supply power, if the board exposes it, is in each summary's `meta.resources`; energy is never estimated.
