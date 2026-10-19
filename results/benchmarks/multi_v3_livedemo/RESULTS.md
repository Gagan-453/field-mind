# Benchmark `multi_v3_livedemo`

Architecture **multi**, mode **lockstep**, overlay `configs/v3.yaml`, merge rule `hybrid`, models npu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`, cpu: `gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf`. Agent code ran on the laptop and only model calls on the board, so tick times are laptop times. Energy not measured. All plant data is synthetic.

Group top-1 is the share of scored ticks (fault onset onward) whose published rank-1 cause is in the true case's look-alike group; belief group top-1 is the same for the code-only ranking. A held-out true case has no exact top-1. Unusable = a model answer that was not used (wrong format, failed call, rejected note reading). Settings and every run, stopped ones included: `test.json`.

| episode | run | finished | ticks | model calls | unusable | tokens in | group top-1 | belief group top-1 | exact top-1 | faithfulness | actions P / R | lead time min | false alarms /h | tick p95 ms | wall s | chip C |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ep_A01_fcv_seize | 1 | 2026-10-08 14:46 | 130 | 74 | 0 | 46,958 | 0.89 | 0.55 | 0.89 | 0.86 | 0.29 / 1.00 | 22.2 | – | 4602 | 209 | 34.1 → 56.3 |
| ep_B01_tube_leak | 1 | 2026-10-08 14:49 | 170 | 60 | 0 | 41,120 | 1.00 | 0.56 | 1.00 | 1.00 | 0.80 / 1.00 | – | – | 2929 | 166 | 43.6 → 57.5 |
| ep_C01_wet_coal | 1 | 2026-10-08 14:52 | 170 | 24 | 0 | 18,255 | 0.67 | 0.98 | – | 1.00 | 0.33 / 0.75 | – | – | 3308 | 86 | 44.6 → 56.7 |
| ep_D01_high_cv_coal | 1 | 2026-10-08 14:58 | 310 | 96 | 0 | 71,934 | 0.83 | 0.82 | 0.83 | 0.99 | 0.44 / 1.00 | 114.8 | – | 3498 | 329 | 43.4 → 59.4 |
| ep_E01_fouling_drift | 1 | 2026-10-08 14:59 | 390 | 0 | 0 | 0 | – | – | – | 1.00 | – | – | – | 5 | 11 | 44.4 → 45.9 |
