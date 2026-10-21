# Benchmark `bevideas_B_explain_bevcpu`

Architecture **multi**, mode **lockstep**, overlay `configs/bev_ideas.yaml`, merge rule `hybrid`, models npu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`, cpu: `gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf`, bev: `bev-decider-0.4B-backbone-Q8_0.gguf`. Agent code ran on the laptop and only model calls on the board, so tick times are laptop times. Energy not measured. All plant data is synthetic.

bev ideas switches: `explain=on`. bev-decide on cpu. bev idea calls: answered by bev-decide (failed = no answer, which makes the run invalid and is not kept; rejected = refused by the gate's check). used = an answer that changed what the agent did; shadow = asked and only logged. Decode tokens per tick: answer tokens written by every model per tick (bev writes none).

Group top-1 is the share of scored ticks (fault onset onward) whose published rank-1 cause is in the true case's look-alike group; belief group top-1 is the same for the code-only ranking. A held-out true case has no exact top-1. Unusable = a model answer that was not used (wrong format, failed call, rejected note reading). Settings and every run, stopped ones included: `test.json`.

| episode | run | finished | ticks | model calls | bev idea calls / failed / rejected | bev used / shadow | decode tokens per tick | unusable | tokens in | group top-1 | belief group top-1 | exact top-1 | faithfulness | actions P / R | lead time min | false alarms /h | tick p95 ms | wall s | chip C | server CPU s npu / cpu / bev | peak RSS MB npu / cpu / bev |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev_A01_fcv_seize | 1 | 2026-10-21 00:56 | 130 | 62 | 31 / 0 / 0 | 31 / 0 | 1.89 | 0 | 35,973 | 0.51 | 0.02 | 0.40 | 0.99 | 0.31 / 1.00 | – | – | 3092 | 90 | 38.2 → 58.9 | 31.4 / 0.1 / 236.6 | 523 / 1475 / 1570 |
| dev_A02_fcv_seize_fast | 1 | 2026-10-21 01:01 | 80 | 91 | 40 / 0 / 0 | 40 / 0 | 7.36 | 0 | 57,824 | 0.62 | 0.47 | 0.03 | 1.00 | 0.29 / 1.00 | 5.7 | – | 4518 | 165 | 41.1 → 64.5 | 42.8 / 129.1 / 455.3 | 527 / 1556 / 1660 |
| dev_B01_tube_leak | 1 | 2026-10-21 01:09 | 170 | 124 | 58 / 0 / 0 | 58 / 0 | 3.90 | 0 | 67,236 | 0.94 | 0.47 | 0.94 | 1.00 | 0.50 / 1.00 | – | – | 2841 | 172 | 41.3 → 64.1 | 66.7 / 81.5 / 365.1 | 528 / 1560 / 1660 |
| dev_B02_tube_leak_fast | 1 | 2026-10-21 01:14 | 80 | 47 | 23 / 0 / 0 | 23 / 0 | 2.38 | 0 | 20,603 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 / 0.75 | – | – | 1858 | 48 | 41.1 → 57.1 | 24.9 / 0.1 / 68.5 | 523 / 1476 / 1660 |
| dev_C01_wet_coal | 1 | 2026-10-21 01:18 | 170 | 54 | 27 / 0 / 0 | 27 / 0 | 1.27 | 0 | 37,143 | 0.57 | 0.72 | – | 0.91 | 0.44 / 1.00 | – | – | 3784 | 94 | 40.9 → 61.0 | 31.8 / 0.1 / 273.3 | 522 / 1475 / 1660 |
| dev_C02_feeder_trip | 1 | 2026-10-21 01:24 | 100 | 96 | 42 / 0 / 0 | 42 / 0 | 6.38 | 0 | 52,465 | 0.60 | 0.91 | 0.13 | 0.93 | 0.27 / 1.00 | – | – | 5254 | 144 | 41.1 → 64.0 | 47.4 / 127.2 / 307.8 | 528 / 1562 / 1660 |
| dev_D01_high_cv_coal | 1 | 2026-10-21 01:38 | 310 | 261 | 127 / 0 / 0 | 127 / 0 | 3.88 | 0 | 203,037 | 0.80 | 0.78 | 0.80 | 0.98 | 0.44 / 1.00 | 82.3 | – | 5118 | 601 | 41.1 → 70.6 | 149.3 / 92.8 / 2026.2 | 543 / 1556 / 1665 |
| dev_D03_high_cv_severe | 1 | 2026-10-21 01:49 | 150 | 112 | 56 / 0 / 0 | 56 / 0 | 2.99 | 0 | 89,309 | 0.94 | 0.94 | 0.94 | 0.92 | 0.57 / 1.00 | 43.2 | – | 5216 | 239 | 40.7 → 66.8 | 65.5 / 0.2 / 850.6 | 530 / 1475 / 1675 |
| dev_N01_normal | 1 | 2026-10-21 01:54 | 80 | 0 | 0 / 0 / 0 | 0 / 0 | 0.00 | 0 | 0 | – | – | – | 1.00 | – | – | 0.00 | 3 | 6 | 41.3 → 43.6 | 0.0 / 0.0 / 0.0 | 490 / 1476 / 1675 |
| dev_N02_normal | 1 | 2026-10-21 01:55 | 110 | 2 | 1 / 0 / 0 | 1 / 0 | 0.07 | 0 | 788 | – | – | – | 1.00 | – | – | 1.09 | 7 | 8 | 40.3 → 43.2 | 1.3 / 0.0 / 2.4 | 505 / 1476 / 1675 |

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
