# Benchmark `bev3_six`

Architecture **bev**, mode **lockstep**, overlay `configs/bev3.yaml`, merge rule `hybrid`, models npu: `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`, cpu: `gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf`, bev: `bev-decider-0.4B-backbone-Q8_0.gguf`. Agent code ran on the laptop and only model calls on the board, so tick times are laptop times. Energy not measured. All plant data is synthetic.

Group top-1 is the share of scored ticks (fault onset onward) whose published rank-1 cause is in the true case's look-alike group; belief group top-1 is the same for the code-only ranking. A held-out true case has no exact top-1. Unusable = a model answer that was not used (wrong format, failed call, rejected note reading). Settings and every run, stopped ones included: `test.json`. Model calls include the decider's. Decider calls: answered by bev-decide (failed = no answer; rejected = refused by the gate's check). Replay ok: bench/replay_multi rebuilds every published ranking from the saved answers, decider included.

| episode | run | finished | ticks | model calls | decider calls / failed / rejected | unusable | tokens in | group top-1 | belief group top-1 | exact top-1 | faithfulness | actions P / R | lead time min | false alarms /h | tick p95 ms | wall s | chip C | replay ok |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ep_A01_fcv_seize | 1 | 2026-10-08 15:22 | 130 | 146 | 72 / 0 / 0 | 18 | 69,683 | 0.88 | 0.55 | 0.88 | 0.79 | 0.27 / 1.00 | 22.7 | – | 3939 | 209 | 36.8 → 54.6 | yes |
| ep_N01_normal | 1 | 2026-10-08 15:10 | 80 | 0 | 0 / 0 / 0 | 0 | 0 | – | – | – | 1.00 | – | – | 0.00 | 5 | 9 | 35.9 → 36.3 | yes |
