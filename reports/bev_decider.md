# bev-decider (Part A: host build) — report

## Status
PARTIAL — Part A built and tested on the host (Mac): weight split, `bev-decide` (C++ server on llama.cpp), backend
client, decider agent with gate check and capped `nudge`, decider lane, board tooling, conformance tool. **Nothing has
run on the board, and bev-decider's real weights have not been downloaded or run anywhere.** No accuracy number exists
for bev-decider. Every agent number below is from the mock backend, which measures plumbing only (its decider backs
belief's leader; it does not read the state). All plant data is synthetic.

Human sign-off (2026-10-07): add bev-decider as a third model under the project rules; skip the laptop accuracy test and
go to the board. Branch `bev-decider` (from `multi-agent-fix` 8acbc13), commits 8cb31d5, 35360eb, 1aaeaec, 9d21d47,
eb59296, local only.

## What was built
| part | files | what it does |
|---|---|---|
| weight split | `bench/bev_convert.py` | `model.safetensors` -> a plain 20-layer Qwen3 folder (`backbone.*` -> `model.*`, bytes unchanged) for llama.cpp's converter, and the decision head as one fp32 blob + manifest with the encoding constants. Stdlib only. Refuses a git-lfs pointer, a different file (sha256), any tensor whose name or shape differs from what the configs imply |
| board server | `device/bev_decide/` (`bev_core.hpp`, `bev_decide.cpp`, `CMakeLists.txt`, `build_android.sh`, `build_gguf.sh`) | bev's token layout and decision head in C++; the transformer on llama.cpp: prompt in seq 0, option i in seq i+1 from the same position after copying the prompt's cells, the answer in seq N+1 after copying the prompt's and every option's cells; embeddings with pooling none; `POST /v1/systemone`, `GET /health`. Links the INSTALLED llama.cpp package that is on the board; builds in the board's container |
| backend | `BevDeciderBackend` in `fieldmind/runtime/llm_backend.py` | stdlib HTTP client; every failure is a failed call, including a dropped connection (the `RemoteDisconnected` case `LlamaServerBackend` does not catch; that class is unchanged) |
| agent | `fieldmind/multi/agents/decider.py`, gate, blackboard, lanes, scheduler, merge rules, orchestrator | when its evidence changes (offered cases, signature, open findings), asks bev-decide to choose among belief's top 3 live cases; the gate checks the answer and adds it to `nudge` as one more fresh answer in its own section; the diagnosticians' and the decider's offsets are summed, the SUM capped at 1.2 |
| config | `configs/base.yaml` (`multi.decider`, off), `configs/bev.yaml` | `bev.yaml` = `accuracy.yaml` + `merge_rule: nudge` + decider + bev lane, nothing else (test-enforced) |
| board tooling | `bench/board.py` (`start bev`, `log bev`, `stop bev`), `/board-up` skill, `bench/bev_conformance.py` | third lane on port 8082 under the CANDIDATES rule (sha256 recorded and matched, else refused); conformance requests / reference / compare |

## Verification
| step | result |
|---|---|
| ran the module | converter: stops cleanly on the lfs pointer in `bev-decider-0.4B/` (weights not downloaded). Mock dev episode `dev_D01_high_cv_coal` with `bev.yaml`: 135 decider calls on lane `bev`, 0 failed, 0 rejected, every summed offset <= 1.2. 24 conformance requests built from the 8 dev quick-set fault episodes (`reports/data/bev_requests.json`) |
| self-tests | 71 new tests, all passing (convert 10, core 12, manifest 1 [runs when `BEV_LLAMA_SRC` is set; ran here against the pinned headers], backend 11, decider 25, conformance 7, board 5). Full suite after task 5: **513 passed, 1 skipped, 1 deselected** (the known-flaky `test_kill_minus_9_mid_episode_then_resume_is_identical`, which passed 2 of 3 alone before this work) |
| independent re-derivation | (1) parameter counts: closed-form per-layer algebra from the configs vs element counts summed over the 263 tensors of the REAL header (range request, 29,632 bytes): head 7,364,608 = 7,364,608, layers + final norm 314,619,904 = 314,619,904, rel. diff 0; header + data = 969,892,808 B = the lfs pointer's size. (2) token layout: C++ vs bev's OWN `encode.py` (copied unchanged), token ids, positions, read indices and full attention mask identical on 6 cases. (3) head: C++ vs a Python forward written from `model.py`, max abs diff < 1e-12; via the real manifest path 3.3e-16. (4) decider off vs the pre-decider code (exported commit 1aaeaec): 15 mock dev runs, 2,580 ticks, assessments, run telemetry and summaries identical |
| mutation check | 29 mutations, all caught: convert 4 (o_proj shape, copy offset, rename, eps), core 7 (answer position, read index, GELU tanh, unbiased variance, sqrt(H) scale, option cells not copied to the answer seq, option text), manifest 1 (eps), backend 4 (dropped connection, ttft source, missing usage as 0, mock pick), decider 8 (uncapped sum, unoffered case accepted, rejected answer counted, no on-change rule, lane kind ignored, offered order reversed, decider without nudge, decider offsets leaking into the diagnosticians' — the last needed a new test), board 4 (binary sha, missing sha, port, ADSP path), conformance 1 (tokens never compared) |

## Direction checks
| claim | expected | measured | |
|---|---|---|---|
| the decider's pick moves the published ranking toward it | a decider backing belief's 3rd case changes what is published | `contrarian` mock run publishes differently from arm A (`test_the_contrarian_decider_moves...`) | OK |
| offsets never exceed the cap | max summed offset <= 1.2 | 1.2 on every rule record, mock dev runs | OK |
| belief is never written by the decider | belief ranking per tick identical with and without | identical (mock, contrarian) | OK |
| the decider runs only on evidence change | calls < non-quiet ticks | dev_A01: 39 calls, dev_B01: 74, dev_N01: 0 | OK |
| llama.cpp honours the sequence plan | bev's mask | **PROVISIONAL**: checked on the plan replayed with llama.cpp's documented rule, not on llama.cpp | — |

## Constants introduced
| symbol | value | provenance | range | affects |
|---|---|---|---|---|
| `multi.decider.top_k` | 3 | HUMAN DECISION 2026-10-07 (belief's top 3) | — | the cases offered |
| `multi.decider.question` | "Which root cause best explains the plant facts?" | HUMAN DECISION 2026-10-07, fixed, never tuned | — | bev's input |
| `EXPECTED_SHA256` | e28f9f5a…4282 | CITED: lfs pointer, huggingface.co/avbiswas/bev-decider-0.4B | — | refuses another file |
| task prompts, "The answer is:", `<option>`, 2048 / 64 tokens | — | CITED: bev_decider 0.2.1 `encode.py`, model `config.json` | — | the token layout |
| LayerNorm eps | 1e-5 | CITED: torch.nn.LayerNorm default (bev's `model.py` uses defaults) | — | the head |
| GELU | exact (erf) | CITED: torch.nn.GELU default | — | the head |
| GGUF type | Q8_0 everywhere | DECISION (Q4_0 or Q8_0 allowed on HTP; the more precise one for a 0.4B decision model) | Q4_0 / Q8_0 | drift vs the reference (measured at Part C step 5) |
| bev lane `prefill_tok_s` / `decode_tok_s` | 909 / 13.9 | ASSUMED = the NPU lane's cited planning rates (plan p.14-15) | prefill >= 909 (0.31B of matrices vs 3B on the same NPU), upper bound unknown; decode unused | the simulated clock only (one eligible lane: never a placement) |
| bev lane timeout | 120 s | reused: `llm.llamaserver.timeout_s` | — | when a decider call counts as failed |
| `BEV_PORT` | 8082 | DESIGN (next to 8080 / 8081) | — | port forward |
| `--max-options` / `n_seq_max` | 16 / 18 | DESIGN (>= top_k) / DERIVED (options + prompt seq + answer seq) | max-options >= 3 | refuses larger requests |

## Numbers that changed
None with the decider off (shown above). Mock, dev quick set (10 episodes), arm A = `accuracy.yaml` + nudge, arm B =
`bev.yaml` (mock decider). **Plumbing only: the mock decider backs belief's leader.**

| | A | B | belief alone |
|---|---|---|---|
| library group top-1 | 0.736 | 0.659 | 0.655 |
| family A group top-1 | 0.504 | 0.250 | 0.243 |
| family B / C / D group top-1 | 0.746 / 0.909 / 0.871 | 0.742 / 0.909 / 0.861 | 0.734 / 0.909 / 0.861 |
| held-out (C) group top-1 | 0.725 | 0.725 | 0.725 |
| model invocation rate (S4) | 0.283 | 0.330 | — |

## Disagreements recorded, not resolved
1. **A decider that agrees with belief cancels the diagnosticians' corrections (shared cap).** Verified on the mock
   runs above: of 79 scored fault ticks where A and B publish a different rank 1, B's is belief's leader on 76, the
   decider had raised it on 79; A right / B wrong on 36, the reverse on 0. Under the conservative default (one cap for
   all model evidence), bev-decider can help only where it disagrees with belief and belief is wrong; where it agrees
   with a wrong belief it undoes Llama's corrections. Not changed.
2. **Filler cases are offered.** The first conformance request (dev_A01, drum level falling) offers RCA-09 and RCA-10,
   the all-FLAT cases that drew Llama on 7 October, because belief ranks them in its top 3. That is the agreed rule
   ("offer what belief ranks"). Whether bev-decider avoids them is a Part C result.
3. **The decider's evidence changes often.** 135 calls on mock dev_D01 (310 ticks, 250 not quiet), so offsets reach the 1.2 cap
   within a few calls on many cases. Not tuned.
4. **Fact lines carry L1's derived numbers** (e.g. "-0.70 %/min sustained 3 min"), as every compact prompt does; no raw
   readings. Recorded so it is not mistaken for a breach of invariant 1.

## Decisions taken (conservative defaults, under the sign-off)
Belief's top 3 as candidates (needs no Llama answer); its answer enters only through `nudge`, never as the ranking;
one shared cap (the bound `nudge` already had); decider off by default, its absence byte-identical to before; Q8_0;
NPU first, board CPU as fallback; `LlamaServerBackend`'s missing `RemoteDisconnected` catch not touched here (shared
runtime; Gagan fixed it in 348bd0e, merged 2026-10-08); existing board commands unchanged, `stop bev` separate.

## Blocked / needs a decision
1. **Shared or separate cap** for the decider's offsets (disagreement 1). Options: keep one cap (today); give the
   decider its own cap; let the decider replace the diagnosticians' nudge. Changes what arm B measures, so it is a
   human decision, best taken before Part C step 6.
2. **Offer the filler cases or not** (disagreement 2) — same reason.
3. **Arm A's run-to-run noise** needs arm A run twice on the board (about 1 h of board time per run, estimate from the
   accuracy-fix report); confirm the budget.
4. **Conformance drift**: no automatic threshold (one relative to the board's own drift let a broken port pass — caught
   by a test; a fixed one would be invented). A person reads the 16-bit-CPU and Q8_0-HTP0 numbers side by side.

## What I could not verify
- That llama.cpp at b11371 honours the sequence plan (cells shared across sequences by `llama_memory_seq_cp`, several
  cells of one sequence at the same position, the batch checks on consecutive positions), on the CPU or on HTP0.
- That `convert_hf_to_gguf.py` accepts the 20-layer truncated Qwen3 folder, and that llama.cpp's Qwen2 tokenizer gives
  bev's token ids (the conformance token check settles it).
- That `bev-decide` prints the loader lines without `-lv` (expected from libllama's default logger, not seen).
- That two processes can use HTP0 at once (decider + Llama NPU lane), memory (estimate ~0.5 GB GGUF + 30 MB head
  against 15 GB), latency per call.
- That `venv-convert` has torch >= 2.4 and transformers >= 4.56 for `bev_decider` (reference step).
- The weights themselves: only the header was read; the file was never downloaded here.
- Whether bev-decider helps on boiler faults at all: it was trained on support routing, policy and similar text.

## Merge of multi-agent-fix (2026-10-08)
Gagan's five commits (b7f6e45 .. 95fb39b) merged into `bev-decider` without a text conflict: the benchmark runner
(`scripts/benchmark.sh`, `bench/benchmark.py`), the connection-drop fix in `LlamaServerBackend`, merge rule `guarded`
(tiebreak; the model never promotes a flat case), `configs/accuracy.yaml` now `verifier: never` and
`merge_rule: guarded`, and candidate B (`configs/accuracy_v2.yaml`, lean answer). Follow-ups made here:
- `configs/bev.yaml` takes `verifier: never` from the new `accuracy.yaml` and keeps `merge_rule: nudge` (the decider
  enters only through nudge). Arm A stays `accuracy.yaml` + `--merge-rule nudge`, so the arms differ by the decider
  alone (test-enforced).
- `bench/replay_multi.py` replays the decider's accepted rankings in `nudge` (summed, capped, as the gate does); without
  it the runner's keep-check rejected every decider run. A run with no decider records replays as before.
- `bench/benchmark.py`'s board check expects the decider's calls from bev-decide's model on the decider's lane, only
  when the decider is enabled. The runner never starts or stops bev-decide.
- New open decision: the accuracy work's primary rule is now `guarded`; the decider has a path only through `nudge`.
  Whether to give it one under `guarded` / `tiebreak` (or to compare candidate B with the decider) is not decided here.

## Pass rule for Part C step 6 (fixed 2026-10-07, before any board run)
Dev quick set (the 8 fault episodes and 2 normal ones of `reports/multi_accuracy_fix.md`), lockstep, Llama 3.2 3B on
both lanes. Arm A = `configs/accuracy.yaml` + `merge_rule: nudge`, run twice (A1, A2). Arm B = `configs/bev.yaml`.
Order A1, B, A2. Metric: library group top-1, pooled by `bench.evaluator.aggregate` over the arm's episodes.
- **Pass:** B > A1, B > A2 and B > belief alone, each by more than |A1 - A2|.
- Arm B is valid only if no decider call failed in any episode (`multi.decider.failed == 0`).
- Held-out (family C, RCA-06) and every other metric are reported, never used to decide.
- A pass is a result on the dev quick set only; the 30 reporting episodes are run once afterwards, to report.

## Process findings
- A same-size edit restored within the same second left stale bytecode (`bench/__pycache__`); the existing test caught
  it. Caches are now cleared after every mutation restore.
- A mutation script written for bash ran under zsh (no word splitting): seven faults were applied with no backup. Each
  was reversed by exact replacement (each found once), the diff reviewed, and the restored code reproduced the
  pre-mutation decider-off output byte for byte; the check was then redone as a bash script.

## Part C: commands for the QIDK laptop
Run in order; stop at the first failure and report it.
```
# 0. code and weights
git fetch && git checkout bev-decider
cd bev-decider-0.4B && git lfs pull && cd ..           # 970 MB; also tokenizer.json
# 1-2. split, 16-bit GGUF, Q8_0 GGUF, type check  (prints sizes and sha256)
device/bev_decide/build_gguf.sh bev-decider-0.4B
# 3. reference (bev_decider, fp32, CPU) on the 24 dev requests
$BUILD/venv-convert/bin/pip install --no-deps bev-decider==0.2.1
$BUILD/venv-convert/bin/python -m bench.bev_conformance reference bev-decider-0.4B \
    --requests reports/data/bev_requests.json --out reports/data/bev_reference.json
# 4. build bev-decide in the board's container, against the package on the board
adb pull /data/local/tmp/llm/llama.cpp /tmp/board-pkg
device/bev_decide/build_android.sh $BUILD/llama.cpp /tmp/board-pkg
adb push build-bev-android/bev-decide /data/local/tmp/llm/llama.cpp/bin/
adb push $BUILD/gguf/bev/{bev-decider-0.4B-backbone-Q8_0.gguf,backbone-16bit.gguf,bev_head.bin,bev_head.json} /data/local/tmp/llm/
#    record every sha256 (laptop == board) in bench/board.py BEV_FILES / BEV_BINARY_SHA256, commit
#    (optional, on the laptop: BEV_LLAMA_SRC=$BUILD/llama.cpp .venv/bin/python -m pytest tests/test_bev_manifest.py)
# 5. conformance: port first (16-bit, board CPU), then the deployed form (Q8_0, HTP0)
.venv/bin/python -m bench.board start bev backbone-16bit.gguf cpu && .venv/bin/python -m bench.board log bev
.venv/bin/python -m bench.bev_conformance compare http://localhost:8082 --reference reports/data/bev_reference.json \
    --label cpu-16bit --out reports/data/bev_conformance_cpu-16bit.json
.venv/bin/python -m bench.board stop bev
.venv/bin/python -m bench.board start bev bev-decider-0.4B-backbone-Q8_0.gguf && .venv/bin/python -m bench.board log bev
.venv/bin/python -m bench.bev_conformance compare http://localhost:8082 --reference reports/data/bev_reference.json \
    --label htp0-q8 --out reports/data/bev_conformance_htp0-q8.json
#    with the NPU Llama lane also up (/board-up): repeat the compare, then one Llama call (bench.board speed :8080)
# 6. measurement (dev quick set only), after the decisions above
#    arm A twice:  run_demo.py --arch multi --backend llamaserver --overlay configs/accuracy.yaml --merge-rule nudge ...
#    arm B:        run_demo.py --arch multi --backend llamaserver --overlay configs/bev.yaml ...
#    chip temperature before/after each run, cooling gaps; the 30 reporting episodes only after a pass
```
