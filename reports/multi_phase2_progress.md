# Multi-agent Phase 2: progress

Updated and committed after every commit. Mock backend only; no accuracy claim.

| commit | what | state | check |
|---|---|---|---|
| 0 | human decisions, pre-registered dev gate, expected-change statement | done | no measurement or code before it |
| 1 | Phase 1 close-out: hard-stage timing script committed and re-run | done | `bench/time_single_hard.py`; mean 0.276 -> 0.299 / 0.290 ms, p50 0.252 -> 0.256 / 0.257; max does not reproduce (0.778 -> 1.808 / 1.609, unexplained, one tick); over 200 ms: 0 |
| 2 | fixed placement in the scheduler | pending | |
| 3 | real tokenizer counts; 60-token answer check. **STOP and report** | pending | |
| 4 | text reader (notes), record-facts by code, note-fact coverage check | pending | |
| 5 | compact diagnostician with per-section switches | pending | |
| 6 | compact verifier | pending | |
| 7 | dev gate and report. **STOP and report** | pending | |

## Stops hit
None yet.
