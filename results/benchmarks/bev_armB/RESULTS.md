# Benchmark `bev_armB`

Architecture **multi**, mode **lockstep**, overlay `configs/bev.yaml`, merge rule `nudge`, models npu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`, cpu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`. Agent code ran on the laptop and only model calls on the board, so tick times are laptop times. Energy not measured. All plant data is synthetic.

Group top-1 is the share of scored ticks (fault onset onward) whose published rank-1 cause is in the true case's look-alike group; belief group top-1 is the same for the code-only ranking. A held-out true case has no exact top-1. Unusable = a model answer that was not used (wrong format, failed call, rejected note reading). Settings and every run, stopped ones included: `test.json`.

| episode | run | finished | ticks | model calls | unusable | tokens in | group top-1 | belief group top-1 | exact top-1 | faithfulness | actions P / R | lead time min | false alarms /h | tick p95 ms | wall s | chip C |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ep_A01_fcv_seize | 1 | 2026-10-08 11:17 | 130 | 139 | 0 | 72,985 | 0.59 | 0.55 | 0.59 | 0.76 | 0.29 / 1.00 | 21.7 | – | 4123 | 263 | 43.6 → 61.7 |
| ep_A02_fcv_seize_fast | 1 | 2026-10-08 11:45 | 80 | 93 | 0 | 45,360 | 0.27 | 0.25 | 0.00 | 0.99 | 0.23 / 0.75 | – | – | 7710 | 170 | 45.1 → 61.7 |
| ep_A03_bfp_suction | 1 | 2026-10-08 11:52 | 110 | 127 | 0 | 65,726 | 0.45 | 0.45 | 0.00 | 0.98 | 0.36 / 1.00 | – | – | 7974 | 245 | 44.4 → 61.7 |
| ep_B01_tube_leak | 1 | 2026-10-08 11:23 | 170 | 136 | 0 | 72,851 | 0.62 | 0.56 | 0.62 | 1.00 | 0.44 / 1.00 | – | – | 3494 | 217 | 45.1 → 62.5 |
| ep_B02_tube_leak_fast | 1 | 2026-10-08 11:57 | 80 | 68 | 0 | 37,129 | 0.90 | 0.86 | 0.90 | 1.00 | 0.50 / 0.75 | – | – | 3467 | 131 | 45.5 → 60.2 |
| ep_B03_tube_leak_slow | 1 | 2026-10-08 12:06 | 290 | 241 | 0 | 125,255 | 0.28 | 0.28 | 0.28 | 1.00 | 0.36 / 1.00 | – | – | 3933 | 412 | 45.5 → 63.3 |
| ep_C01_wet_coal | 1 | 2026-10-08 11:28 | 170 | 54 | 0 | 28,806 | 0.98 | 0.98 | – | 1.00 | 0.57 / 1.00 | – | – | 3697 | 121 | 45.1 → 60.6 |
| ep_C02_feeder_trip | 1 | 2026-10-08 12:13 | 100 | 102 | 0 | 55,854 | 0.54 | 0.53 | 0.49 | 0.93 | 0.50 / 1.00 | – | – | 7095 | 216 | 45.1 → 64.1 |
| ep_C03_wet_coal_mild | 1 | 2026-10-08 12:19 | 190 | 67 | 0 | 36,540 | 0.47 | 0.47 | – | 0.94 | 0.50 / 1.00 | – | – | 4018 | 166 | 44.8 → 62.1 |
| ep_D01_high_cv_coal | 1 | 2026-10-08 11:37 | 310 | 203 | 0 | 117,279 | 0.82 | 0.82 | 0.82 | 0.98 | 0.57 / 1.00 | 103.3 | – | 3991 | 409 | 45.5 → 62.5 |
| ep_E01_fouling_drift | 1 | 2026-10-08 11:41 | 390 | 10 | 0 | 4,061 | – | – | – | 1.00 | – | – | – | 7 | 57 | 45.5 → 59.7 |
| ep_N01_normal | 1 | 2026-10-08 11:12 | 80 | 5 | 0 | 2,024 | – | – | – | 1.00 | – | – | 0.00 | 7 | 30 | 39.0 → 51.5 |
