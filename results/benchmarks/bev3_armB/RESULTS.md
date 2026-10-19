# Benchmark `bev3_armB`

Architecture **multi**, mode **lockstep**, overlay `configs/bev3.yaml`, merge rule `hybrid`, models npu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`, cpu: `gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf`. Agent code ran on the laptop and only model calls on the board, so tick times are laptop times. Energy not measured. All plant data is synthetic.

Group top-1 is the share of scored ticks (fault onset onward) whose published rank-1 cause is in the true case's look-alike group; belief group top-1 is the same for the code-only ranking. A held-out true case has no exact top-1. Unusable = a model answer that was not used (wrong format, failed call, rejected note reading). Settings and every run, stopped ones included: `test.json`.

| episode | run | finished | ticks | model calls | unusable | tokens in | group top-1 | belief group top-1 | exact top-1 | faithfulness | actions P / R | lead time min | false alarms /h | tick p95 ms | wall s | chip C |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ep_A01_fcv_seize | 1 | 2026-10-08 12:29 | 130 | 146 | 0 | 76,701 | 0.88 | 0.55 | 0.88 | 0.79 | 0.27 / 1.00 | 22.7 | – | 5297 | 248 | 42.8 → 61.7 |
| ep_A02_fcv_seize_fast | 1 | 2026-10-08 12:54 | 80 | 107 | 0 | 51,027 | 0.53 | 0.25 | 0.05 | 0.99 | 0.31 / 1.00 | -5.9 | – | 5238 | 171 | 46.3 → 61.7 |
| ep_A03_bfp_suction | 1 | 2026-10-08 13:00 | 110 | 126 | 0 | 65,086 | 0.80 | 0.45 | 0.11 | 0.99 | 0.36 / 1.00 | -0.5 | – | 5182 | 213 | 46.7 → 62.1 |
| ep_B01_tube_leak | 1 | 2026-10-08 12:35 | 170 | 138 | 0 | 70,935 | 0.92 | 0.56 | 0.92 | 1.00 | 0.50 / 1.00 | – | – | 3501 | 204 | 46.3 → 62.4 |
| ep_B02_tube_leak_fast | 1 | 2026-10-08 13:04 | 80 | 60 | 0 | 32,245 | 0.94 | 0.86 | 0.94 | 1.00 | 0.50 / 0.75 | – | – | 3225 | 92 | 46.3 → 58.3 |
| ep_B03_tube_leak_slow | 1 | 2026-10-08 13:12 | 290 | 259 | 0 | 133,875 | 0.53 | 0.28 | 0.53 | 1.00 | 0.36 / 1.00 | – | – | 5647 | 433 | 46.3 → 62.5 |
| ep_C01_wet_coal | 1 | 2026-10-08 12:39 | 170 | 49 | 0 | 26,658 | 0.67 | 0.98 | – | 1.00 | 0.33 / 0.75 | – | – | 3866 | 100 | 46.7 → 59.8 |
| ep_C02_feeder_trip | 1 | 2026-10-08 13:17 | 100 | 104 | 0 | 55,309 | 0.32 | 0.53 | 0.32 | 0.97 | 0.43 / 1.00 | – | – | 6215 | 195 | 45.5 → 59.8 |
| ep_C03_wet_coal_mild | 1 | 2026-10-08 13:21 | 190 | 55 | 0 | 31,170 | 0.38 | 0.47 | – | 0.93 | 0.50 / 1.00 | – | – | 3867 | 110 | 45.5 → 56.7 |
| ep_D01_high_cv_coal | 1 | 2026-10-08 12:48 | 310 | 196 | 0 | 115,368 | 0.83 | 0.82 | 0.83 | 0.99 | 0.44 / 1.00 | 114.8 | – | 4155 | 392 | 45.5 → 63.3 |
| ep_E01_fouling_drift | 1 | 2026-10-08 12:51 | 390 | 0 | 0 | 0 | – | – | – | 1.00 | – | – | – | 5 | 10 | 46.7 → 46.7 |
| ep_N01_normal | 1 | 2026-10-08 12:25 | 80 | 0 | 0 | 0 | – | – | – | 1.00 | – | – | 0.00 | 5 | 10 | 41.7 → 43.2 |
