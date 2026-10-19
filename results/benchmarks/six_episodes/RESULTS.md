# Benchmark `six_episodes`

Architecture **multi**, mode **lockstep**, overlay `configs/fast.yaml`, merge rule `model`, models npu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`, cpu: `gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf`. Agent code ran on the laptop and only model calls on the board, so tick times are laptop times. Energy not measured. All plant data is synthetic.

Group top-1 is the share of scored ticks (fault onset onward) whose published rank-1 cause is in the true case's look-alike group; belief group top-1 is the same for the code-only ranking. A held-out true case has no exact top-1. Unusable = a model answer that was not used (wrong format, failed call, rejected note reading). Settings and every run, stopped ones included: `test.json`.

| episode | run | finished | ticks | model calls | unusable | tokens in | group top-1 | belief group top-1 | exact top-1 | faithfulness | actions P / R | lead time min | false alarms /h | tick p95 ms | wall s | chip C |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ep_A01_fcv_seize | 1 | 2026-10-12 14:48 | 130 | 76 | 0 | 46,955 | 0.52 | 0.55 | 0.17 | 1.00 | 0.31 / 1.00 | 20.2 | – | 4839 | 209 | 35.9 → 52.7 |
| ep_B01_tube_leak | 1 | 2026-10-12 14:54 | 170 | 102 | 0 | 58,017 | 0.87 | 0.56 | 0.87 | 1.00 | 0.67 / 1.00 | – | – | 4525 | 241 | 37.8 → 54.6 |
| ep_C01_wet_coal | 1 | 2026-10-12 14:57 | 170 | 30 | 0 | 20,827 | 0.67 | 0.98 | – | 1.00 | 0.43 / 0.75 | – | – | 3476 | 98 | 37.8 → 51.3 |
| ep_D01_high_cv_coal | 1 | 2026-10-12 15:04 | 310 | 114 | 0 | 79,094 | 0.77 | 0.82 | 0.77 | 1.00 | 0.40 / 1.00 | 114.8 | – | 3494 | 342 | 37.2 → 55.4 |
| ep_E01_fouling_drift | 1 | 2026-10-12 15:06 | 390 | 10 | 0 | 4,035 | – | – | – | 1.00 | – | – | – | 4 | 27 | 37.6 → 48.0 |
| ep_N01_normal | 1 | 2026-10-12 14:44 | 80 | 5 | 0 | 2,013 | – | – | – | 1.00 | – | – | 0.00 | 6 | 17 | 32.5 → 42.2 |
