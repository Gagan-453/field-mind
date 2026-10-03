# Multi-agent Phase 2: progress

Updated and committed after every commit. Mock backend only; no accuracy claim.

| commit | what | state | check |
|---|---|---|---|
| 0 | human decisions, pre-registered dev gate, expected-change statement | done | no measurement or code before it |
| 1 | Phase 1 close-out: hard-stage timing script committed and re-run | done | `bench/time_single_hard.py`; mean 0.276 -> 0.299 / 0.290 ms, p50 0.252 -> 0.256 / 0.257; max does not reproduce (0.778 -> 1.808 / 1.609, unexplained, one tick); over 200 ms: 0 |
| 2 | fixed placement in the scheduler | done | dev, mock: fixed vs earliest finish 0 differences, prompt logs byte-identical (sha `6e9b748a`, same as Phase 1); fixed vs Phase 1 multi and single 0 differences; jobs on lanes: diagnostician npu 1,982, verifier cpu 192; 15 new tests, 169 pass; 5 mutations caught |
| 3 | real tokenizer counts; 60-token answer check. **STOP and report** | done, **stop rule tripped** | `bench/token_count.py`, 4 tokenizers pinned by sha256; Phase 1 dev diagnostician prompts: mean 1,866 to 1,894, max 2,103 to 2,150 real tokens, 1,980 of 1,982 over on every tokenizer; llama.cpp cross-check 0 of 81 texts differ on 3 tokenizers; 28 new tests, 197 pass; 8 mutations caught. **Worst-case ID answer is 89 / 105 / 111 / 105 tokens against a cap of 60** |
| 4 | text reader (notes), record-facts by code, note-fact coverage check | pending | |
| 5 | compact diagnostician with per-section switches | pending | |
| 6 | compact verifier | pending | |
| 7 | dev gate and report. **STOP and report** | pending | |

## Stops hit
1. **After commit 3 (planned stop, and the answer-cap stop rule tripped).** The plan's ID-only answer format
   needs 89 to 111 tokens for a legal 3-case answer (72 to 84 for the plan's own example) against a cap of 60;
   the verifier's needs 33 to 41 against 30. Options and their measured sizes are in
   `reports/multi_phase2_prompt_shrink.md`, "Blocked / needs a decision". Commits 4 to 7 wait on the choice.
2. **Before commit 4 (the human's condition: stop if (a) or (b) changes the gate).** Format B' is decided and
   recorded as an amendment. Answering question (a) showed G1 cannot be 0 differences: with no model confidence,
   `model_only` confidences, the rank-1 confidence on about 580 dev ticks and the verifier trigger (192 calls ->
   140 or 327) must move on the mock. Question (b): the retrieval budget does not differ between mock and
   llamaserver; the 2,484 figure is not reproduced here. Two questions are open in
   `reports/multi_phase2_prompt_shrink.md`, "Blocked / needs a decision". No code changed.
