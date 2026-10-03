# Multi-agent Phase 2: prompt shrink: report

## Status
BLOCKED at commit 3 on a stop rule: the ID-only answer format does not fit the 60-token cap on any of the four
tokenizers (see "Commit 3" and "Blocked / needs a decision" at the end). Commits 0 to 3 are done; commits 4 to
7 have not started. The pre-registration below (human decisions, dev gate, expected-change statement) was committed before
any Phase 2 measurement or code (`595180b`). Results are added under "Results by commit" as commits land.

**This session is mock only.** The mock backend re-ranks retrieved cases and does no reasoning, so its numbers
measure the deterministic and retrieval layers only. They are not an agent result. The real-model baseline
(Session 2) does not exist yet, so this session makes **no accuracy claim** about the shrunk prompts. All timings
are laptop timings, not board timings.

## HUMAN DECISION: allowed accuracy drop (written before any measurement)
The allowed accuracy drop for the shrunk prompts, measured with the real model on dev against the real-model
baseline, is:
- library group top-1 drop <= 0.05, and
- faithfulness drop <= 0.02, and
- group top-1 must stay above the deterministic floor (0.501).

Reason: these are the tie bands already committed in the model-choice rule
(`reports/phase0b_lanes_model_choice.md`; the floor is `bench/model_choice.py: FLOOR_DEFAULT`).

The real-model baseline does not exist yet (Session 2 is running on another machine), so this session builds and
checks with the mock only and makes no accuracy claim.

## HUMAN DECISIONS taken at plan review
- **(a) Records do not go through the text reader.** Record-facts are written by code from the structured JSON,
  with no model call and their own IDs (`R1`...). Reason: they are already code-written, so a model can only
  lose information and adds calls. This overrules the session prompt. The text reader handles notes only.
- **(b) Verifier design changes, accepted as design changes, not as a shrink:** check 3 (discriminator
  observable) removed, the rank-1 confidence rewrite path removed, claims beyond rank 3 not shown. Reason: they
  follow the multi-agent plan's pass/fail verifier. Their effect is unmeasured until a real model runs; the
  Phase 3 known-wrong-answer test covers it.
- **(c) Token gate G3:** prompt tokens + that agent's answer cap must be < 1,280 on all four tokenizers.
  Reason: a fixed 1,280 context holds both.
- **(d) Accepted from the plan:**
  - the unsplit Phase 2 diagnostician runs on the NPU lane in fixed placement (the plan's table names only the
    water and heat halves);
  - the default placement becomes `fixed`; earliest finish stays available by switch;
  - the short discriminating check is the first sentence of `discriminating_evidence`, a mechanical rule, so
    no case data is edited;
  - tokenizer files for the two gated models come from ungated mirrors unless `HF_TOKEN` is set;
  - `tokenizers`, `jinja2` and `brew install llama.cpp` are approved for `bench/` only.

## Stops
- After every commit, `reports/multi_phase2_progress.md` is updated and committed.
- Stop and report after commit 3 (real token counts and the 60-token answer check), even if the stop rule does
  not trip.
- Stop and report again after commit 7.
- The reporting set is not run until the dev gate passes.

## Are mock decisions expected to change when the prompt changes? No. Gate on 0 differences on dev.
Why they should be identical:
- The mock never reads the prompt. Its answer is a function of `mock_hint` only
  (`fieldmind/runtime/llm_backend.py`, `MockBackend.generate`), and the hint comes from L1 and the shared
  `Retriever`, which this phase does not touch.
- The ID-only answer expands to the same payload: cause and discriminator strings come from the same retrieved
  case record the mock copies today; order and confidences are the same numbers; cited fact IDs are the same
  facts once the gate strips the tick stamp for a same-tick answer (the Phase 1 convention).
- Note-facts and record-facts feed prompts only. Nothing in this phase lets them move belief or retrieval.
- The verifier trigger reads the deterministic confidence, so the verifier runs on the same ticks.

### Fields that must move, by construction (excluded by name in the comparison, and printed)
- per envelope: `prompt`, `raw_reply`, `payload`, `tokens`, `prompt_tokens`
- per call: `prefill`, `decode`
- per run: `mean_prompt_tokens`; new `text_calls` counter
- the prompt log's hint hash
- the multi-only `multi` key, which gains the text-reader envelopes, the group, `sep`, the note-facts and
  record-facts used, and the rendered text

### Fields compared (0 differences required)
- per assessment: `tick`, `timestamp`, `state`, `triage`, `headline`, `facts`, `belief_ranking`, `actions`,
  `escalate`, `unexplained`, `confidence`, `degraded_mode`, `llm_invoked`
- `hypotheses`: order, and cause, rank, case_ref, confidence, confidence_shown, supports, discriminator, and
  the verifier / carried / model_only flags
- per envelope: `agent`, `tick`, `status`, `cited_cases`, `retrieved_cases`, `retries`, `error`
- per envelope: **`cited_facts`, compared after stripping the tick stamp (`t84.F1` -> `F1`). Not excluded.**
- per run: `n_ticks`, `diag_calls`, `ver_calls`, `llm_invocation_rate`, `parse_failure_rate`,
  `verifier_disagreement_rate`, `llm_retries`, `envelope_status_counts`
- summary: every key except the latency keys and `mean_prompt_tokens`

Timing-derived fields stay excluded as in Phase 1 (`latency_ms`, `prefill_ms`, `tick_latency_ms`,
`wall_clock_s`, `S1_*`, `deadline_miss`, `deadline_miss_rate`).

### Three places identity could break (watched and reported, not patched around)
1. The mock's "no case retrieved" fallback emits a case-less hypothesis that an ID-only answer cannot express.
   It occurred 0 times in 1,982 dev diagnoses in the Phase 1 dev run. If it occurs on the reporting set, those
   ticks' hypothesis lists will differ; the count is reported.
2. The mock ignores `max_tokens`. A real server truncates at the cap and the JSON breaks. So the mock's answers
   are token-counted on the real tokenizers rather than trusted.
3. `x` (unexplained) and verifier contradictions are empty on the mock, so their expansion is exercised only by
   the scripted-backend tests.

## Phase 2 dev gate (dev, 36 episodes, mock, lockstep)
| gate | pass condition |
|---|---|
| G1 decisions | multi compact vs the Phase 1 multi dev run: 0 differences outside the moving fields above, with `cited_facts` compared after stripping the tick stamp. The comparator is shown to still catch an injected `supports` change and an injected `cited_facts` change |
| G2 placement | fixed vs earliest finish: 0 differences, prompt logs byte-identical |
| G3 tokens | on all four tokenizers (Llama 3.2 3B, Qwen3 1.7B, Gemma 3 1B, Qwen2.5 0.5B), every prompt's tokens + that agent's answer cap < 1,280 (caps: diagnostician 60, verifier 30, text reader 50); every answer within its cap; max and p95 per agent per tokenizer, beside the Phase 1 column; guard firings counted |
| G4 single unchanged | `--arch single` vs the Phase 1 single dev run: 0 differences, prompt log byte-identical; `git diff multi-phase1 -- fieldmind/agent` empty |
| G5 timing | S7 = 0 on both arches; P0 over 200 ms = 0 (laptop timing) |
| G6 tests | full suite green; every mutation caught, run with `PYTHONDONTWRITEBYTECODE=1` and `__pycache__` cleared |

Only after G1 to G6 pass: one reporting-set run (mock). `--arch single` must equal
`results/baselines/single_v3_summary.json` (summary and per-episode, 0 differences); multi compact is compared
with `results/baselines/multi_p1_summary.json` under the same field rule; token max and p95 on the reporting
prompts and the guard's firing count are reported, not tuned against.

### Stop rules specific to this phase
- **Answer cap.** If the worst-case legal ID answer (3 cases, 2 stamped citations each) exceeds 60 tokens on
  any of the four tokenizers, the format and the cap conflict. Stop and report the numbers and the options.
- **Note-fact coverage.** Before the diagnostician commit, on dev only: for every note, raw note -> the
  note-fact the schema can express; list every note whose discriminating content cannot be expressed. If any
  tier-2 dev episode loses its discriminating note content, stop and report.
- If any decision field differs, stop and report the first (episode, tick, field). The single agent is not
  changed to make them match.

## What the gate publishes on an empty ranking (`r: []`)
The answer is valid and goes through the single agent's `merge` unchanged, which is what it already does with
an empty model list: the gate publishes belief's ranked hypotheses with their belief confidences, each flagged
`carried` with no citations for this tick. The headline is the deterministic one. Actions and escalation come
from the gate on that ranking as usual. Because nothing is cited, every ALARM or CRITICAL fact appears under
`unexplained`. Code adds one rendered line, "model: no listed case fits", and the event is counted.

## Design points fixed before the build
- The guard's chars-per-token ratio is fitted on dev prompts only, using the worst tokenizer (lowest chars per
  token). The report gives how many times the guard fires on dev and on the reporting run.
- The diagnostician prompt builder takes per-section compact switches (`rules`, `cases`, `notes`, `world`,
  `schema`), so a failed real-model gate can be ablated one section at a time. All on is the Phase 2 prompt.
- `fieldmind/agent/` is not edited. `bench/model_choice.py` is not edited on this branch.

## Open items recorded, not fixed in this phase
- **Operator question has no consumer** until the query agent exists; wrong-premise handling is unserved.
- **The retrieval budget still sizes cases by their full text**, so URGENT ticks keep dropping to 2 or 3 cases
  (317 dev calls in the Phase 1 run) although compact lines would fit 4. Fixing it changes which cases the gate
  takes actions from, so it changes decisions and is out of scope here.
- The repair call's "only if it can finish before the deadline" rule needs real time (Session 6).
- **Stamped IDs and `bench/model_choice.py`.** Its raw-faithfulness reads envelope `cited_facts`, which are
  stamped in the compact path. Not edited on this branch; to be resolved after the merge with `main`.
- **Causes outside the retrieved cases.** With candidate causes removed, the model can no longer name a cause
  outside the retrieved cases. Count in the Session 2 logs how often the real model does that on the full
  prompt.
- **Lockstep overstates note handling.** The rule that text-reader jobs drain before the diagnosis is built
  does not hold in real time; lockstep accuracy on note-dependent episodes may overstate real-time accuracy.
- **Verifier lane vs the projection formula.** The fixed table puts the verifier on the CPU, but the
  model-choice projection formula assumes both calls on the NPU lane; reconcile when lane rates are measured.
- **Text-reader quality is unmeasured.** The mock text reader's note-facts come from code-built hints.

## What this session cannot verify
- Any accuracy effect of the shrink (needs the Session 2 baseline and the board).
- That the Hugging Face tokenizers match the GGUF tokenizers on the board; to be checked against each lane's
  `/tokenize` or `timings.prompt_n` when the board is attached.
- Board timings; everything timed here is laptop time.

---

# Results by commit

## Commit 2: fixed placement in the scheduler
`multi.placement: fixed | earliest_finish` is now a real switch (`fieldmind/multi/scheduler.py`,
`Scheduler.choose_lane`); `run_demo.py --placement` overrides it; the run file records it under `multi.placement`.
In fixed mode a job takes the lane `multi.fixed_placement` gives its agent and waits for it even when the other
lane is idle. An agent with no entry raises. The default in `configs/base.yaml` is now `fixed`.

**Gate (dev, 36 episodes, 5,850 ticks, mock, lockstep). Mock numbers; not an agent result.**

| check | result |
|---|---|
| fixed vs earliest finish, decisions | `bench/compare_runs.py`: 0 differences over 5,850 assessments and 2,174 envelopes; summaries 0 differences |
| fixed vs earliest finish, prompts | 2,174 calls each; `cmp`: byte-identical; sha256 `6e9b748a...`, the Phase 1 value |
| fixed vs the Phase 1 multi run and the Phase 1 single run | 0 differences each (runs and summaries) |
| every job on its assigned lane (fixed) | diagnostician: npu 1,982, cpu 0; verifier: cpu 192, npu 0 |
| same jobs under earliest finish | diagnostician: npu 1,733, cpu 249; verifier: npu 48, cpu 144 (the Phase 1 split) |
| S7 / P0 over 200 ms (laptop) | 0 / 0 in both runs |

Independent count: jobs on lanes (2,174) = `diag_calls` + `ver_calls` summed over episodes (2,174) = prompt-log
lines (2,174). Relative difference 0.

Simulated queue wait is 0 for every job under fixed placement and nonzero for 7 jobs (max 1.3 s) under earliest
finish. These come from the placeholder lane rates, so they are expectations, not results.

Tests: `tests/test_fixed_placement.py`, 15 tests; full suite 169 passed (154 before).

| mutation (`PYTHONDONTWRITEBYTECODE=1`, `__pycache__` cleared before and after) | caught by |
|---|---|
| fixed mode falls through to earliest finish | 9 tests: `test_every_agent_lands_on_its_assigned_lane[*]` (6), `test_fixed_job_waits_for_its_busy_lane_while_the_other_is_idle`, `test_agent_without_a_lane_raises_and_is_not_placed`, `test_episode_every_job_runs_on_its_table_lane` |
| a fixed job takes the idle lane | `test_fixed_job_waits_for_its_busy_lane_while_the_other_is_idle`, `test_episode_every_job_runs_on_its_table_lane` |
| lookup returns the other lane | 9 tests, incl. `test_repair_call_stays_on_the_assigned_lane` |
| config table swapped (verifier npu, diagnostician cpu) | `test_episode_every_job_runs_on_its_table_lane` |
| missing agent falls back to the first lane | `test_agent_without_a_lane_raises_and_is_not_placed` |

Constants introduced:

| symbol | value | provenance | range | affects |
|---|---|---|---|---|
| `multi.fixed_placement` diag_water / diag_heat / verifier | npu / cpu / cpu | CITED: plan, "Policies to compare", fixed placement (p.11) | none | lane of each job in fixed mode |
| `multi.fixed_placement` text_reader / query | cpu / cpu | CITED: plan, "Model agents", default lane (p.5) | none | same |
| `multi.fixed_placement` diagnostician (unsplit) | npu | HUMAN DECISION (plan review); the plan names only the two halves | npu or cpu | lane of the Phase 2 diagnostician; with a real model, which numerics produce the diagnosis |

## Commit 3: real tokenizer counts (`bench/token_count.py`)

### How each tokenizer got onto this machine
`tokenizers` 0.23.2 and `jinja2` 3.1.6 were installed into `.venv` (used by `bench/` only). `HF_TOKEN` is not
set, so the two gated models come from ungated mirrors. `bench/token_count.py --fetch` downloads
`tokenizer.json`, `tokenizer_config.json` and, where the repo has one, `chat_template.jinja` at a pinned revision
into `bench/tokenizers/<name>/` (gitignored). `bench/tokenizers/manifest.json` (committed) holds repo, revision
and sha256, and every count refuses to run if a file's sha256 differs.

| candidate | repo used | revision | mirror | template adds |
|---|---|---|---|---|
| Llama 3.2 3B | `unsloth/Llama-3.2-3B-Instruct` (official `meta-llama/...` returns HTTP 401) | `006f5dcd13` | yes | 35 tokens: BOS, a system header with two date lines, user and assistant headers |
| Qwen3 1.7B | `Qwen/Qwen3-1.7B` | `70d244cc86` | no | 12 tokens with thinking off (an empty `<think></think>` block); 8 with thinking on |
| Gemma 3 1B | `unsloth/gemma-3-1b-it` (official `google/...` returns HTTP 401) | `5b11413a10` | yes | 9 tokens |
| Qwen2.5 0.5B | `Qwen/Qwen2.5-0.5B-Instruct` | `7ae557604a` | no | 29 tokens: a default system prompt the template inserts |

A count is the prompt as one user message inside the model's chat template, generation prompt included, BOS
counted once. That is what `LlamaServerBackend` sends. Qwen3 is counted with thinking off, which is the larger
prompt; with thinking on the model would also spend answer tokens on thinking, so any answer cap assumes it is off.

### Phase 1 prompts in real tokens (dev, 2,174 prompts, the "before" column)
Mock run; the prompts are the single agent's. Budget column uses the Phase 2 caps (60 / 30) for comparison.

| tokenizer | agent | n | mean | p95 | max | >= 1,280 | prompt + cap >= 1,280 |
|---|---|---|---|---|---|---|---|
| Llama 3.2 3B | diagnostician | 1,982 | 1,865.5 | 2,021 | 2,103 | 1,980 | 1,980 |
| Llama 3.2 3B | verifier | 192 | 1,449.4 | 1,672 | 1,836 | 164 | 169 |
| Qwen3 1.7B | diagnostician | 1,982 | 1,877.0 | 2,032 | 2,126 | 1,980 | 1,980 |
| Qwen3 1.7B | verifier | 192 | 1,442.9 | 1,666 | 1,830 | 163 | 168 |
| Gemma 3 1B | diagnostician | 1,982 | 1,891.5 | 2,042 | 2,150 | 1,980 | 1,980 |
| Gemma 3 1B | verifier | 192 | 1,461.2 | 1,688 | 1,841 | 164 | 169 |
| Qwen2.5 0.5B | diagnostician | 1,982 | 1,894.0 | 2,049 | 2,143 | 1,980 | 1,980 |
| Qwen2.5 0.5B | verifier | 192 | 1,459.9 | 1,683 | 1,847 | 164 | 169 |

Numbers that changed: the Phase 1 report's chars/4 estimate was diagnostician mean 2,036 / max 2,285 and verifier
max 2,095 with 170 of 192 over. Real counts are 7 to 8% lower for the diagnostician (mean 1,866 to 1,894, max
2,103 to 2,150) and 12% lower for the verifier maximum (1,830 to 1,847; 163 or 164 of 192 over). The conclusion
does not change: 1,980 of 1,982 diagnostician prompts are over on every tokenizer. Lowest chars per token on
these prompts: 3.961 (Gemma 3), 4.057 (both Qwen), 4.150 (Llama 3.2).

### The 60-token answer check: FAILS on all four tokenizers
Bare answer text, compact JSON (no spaces), tick 143 (three digits; dev runs to about tick 170).

| answer | chars | Llama 3.2 | Qwen3 | Gemma 3 | Qwen2.5 |
|---|---|---|---|---|---|
| **worst case in the plan's format: 3 cases, 2 stamped citations each, 1 note** | 159 | **89** | **105** | **111** | **105** |
| same, with 4 notes and 2 unexplained facts | 193 | 107 | 127 | 135 | 127 |
| same as the first row, default `json.dumps` spacing | 179 | 102 | 118 | 125 | 118 |
| the plan's own example exactly as printed on p.13 (2 cases, 3 citations) | 126 | 72 | 78 | 84 | 78 |

The plan describes its example as "about 50 tokens". It is 72 to 84. Where the tokens go: `"RCA-11"` is 6 or 7
tokens, `"t143.F1"` is 6 to 9, `0.6` is 3, and `"sep":"RCA-11","n":["N3"],"x":[]}` is 16 or 17.

The verifier has the same problem at its cap of 30: three case IDs with pass/fail plus a stamped fact ID is 33
to 41 tokens. The text reader fits its cap of 50: 30 to 32 tokens for two tags, 36 to 40 for three.

### Verification
| step | result |
|---|---|
| ran the module | `bench/token_count.py --prompts results/multi_phase2/prompts_dev_fixed.jsonl --answers`: 2,174 prompts on 4 tokenizers, exit 0 |
| self-tests | `tests/test_token_count.py`: 28 passed; full suite 197 passed |
| independent re-derivation | llama.cpp's own tokenizer (`llama-tokenize`, Homebrew llama.cpp 0.5.0, build 11146) on the vocab-only GGUFs from the llama.cpp repo, over 73 dev prompts (every 30th) and the 8 answer cases. Llama 3.2, templated: 132,127 tokens by both, 0 of 81 texts differ. Qwen2.5, templated: 134,112 by both, 0 differ. Qwen3, bare text: 131,995 by both, 0 differ. Relative difference 0 in all three |
| mutation check | 8 mutations, 8 caught (table below) |

| mutation (`PYTHONDONTWRITEBYTECODE=1`, `__pycache__` cleared) | caught by |
|---|---|
| prompt cap 1,280 -> 1,300 | `test_budget_is_prompt_plus_answer_cap_under_1280[*]` (4), `test_count_prompts_flags_only_the_prompt_over_budget` |
| diagnostician answer cap 60 -> 50 | `test_answer_caps_per_agent[*]` (2), the budget test, the count test |
| budget ignores the answer cap | budget test (3 cases), count test |
| no generation prompt in the template | `test_generation_prompt_is_part_of_the_count`, `test_prompt_is_counted_inside_the_chat_template[*]` (4), `test_qwen3_is_counted_with_thinking_off` |
| prompt counted without its template | template test (4), `test_bos_is_counted_once`, Qwen3 test |
| special tokens added a second time | `test_bos_is_counted_once`, template test (Gemma, Llama) |
| Qwen3 counted with thinking on | template test (Qwen3), Qwen3 test |
| sha256 check skipped | `test_file_that_does_not_match_the_manifest_is_refused` |

### What I could not verify
- **Gemma 3 has no independent count.** llama.cpp ships no Gemma 3 vocab file, so its numbers rest on the
  Hugging Face tokenizer alone.
- **Qwen3's template was not cross-checked**, only its bare-text tokenization (the Qwen2 vocab file has no
  `<think>` token).
- The mirrors' files were not compared with the gated official repos.
- Whether the board's GGUF files tokenize the same way, and whether `llama-server` renders the same template
  (it has its own template engine). To check against each lane's `/tokenize` or `timings.prompt_n`.
- The Llama 3.2 template writes today's date; a different date could move the count by a token.

## Blocked / needs a decision
**The ID-only answer format and the answer caps conflict (stop rules 2 and 6).** The plan's format needs up to
111 tokens for a legal 3-case answer and 72 to 84 for its own example, against a cap of 60; the plan's estimate
of "about 50" is off by more than the cap allows. Commits 4 to 7 are not started, because the answer format
fixes the parser, the gate's expansion, the mock roles and the prompts' ID scheme.

Options, each measured on all four tokenizers (Llama 3.2 / Qwen3 / Gemma 3 / Qwen2.5):

| option | worst-case answer | tokens | fits 60 | what it gives up |
|---|---|---|---|---|
| A. keep the plan's format, raise the cap | 3 cases x 2 stamped citations, 4 notes, 2 unexplained | 107 / 127 / 135 / 127 | no; needs a cap near 136 | the 60 rule; G3 becomes prompt + ~136 < 1,280; writing time roughly doubles (9.8 s against 4.3 s at the plan's 13.9 tok/s planning rate, an expectation, not a measurement) |
| B. line numbers for everything: cases 1..4, facts and notes by their line in the prompt, confidence in tenths | `{"g":"A","r":[[1,6,[1,2]],[2,3,[1,2]],[3,2,[1,2]]],"sep":1,"n":[1,2,3,4],"x":[3,4]}` | 55 / 55 / 55 / 55 | yes, by 5 (62 on three tokenizers if a cited fact line is two digits, so it also needs at most 9 fact lines) | the model no longer writes `t84.F1` or `RCA-11`; code maps line numbers to the stamped IDs of the job's evidence tick |
| B'. as B, without confidences | `{"g":"A","r":[[1,[1,2]],[2,[1,2]],[3,[1,2]]],"sep":1,"n":[1,2,3,4],"x":[3,4]}` | 49 / 49 / 49 / 49 | yes, by 11 | as B, plus the model's confidence |
| C. real case IDs, fact and note line numbers, no confidences | `{"g":"A","r":[["RCA-11",[1,2]],...],"sep":"RCA-11","n":[1,2,3,4],"x":[3,4]}` | 61 / 65 / 65 / 65 | no (52 to 56 with one note and nothing unexplained) | would need limits on notes and unexplained facts as well |
| D. keep stamped IDs, shrink the content to 2 cases x 1 citation | `{"g":"A","r":[["RCA-11",0.6,["t143.F1"]],["RCA-07",0.3,["t143.F2"]]],...}` | 57 / 64 / 66 / 64 | no | and loses the third case |

Facts that bear on the choice:
- **The model's confidence is already mostly unused.** In the single agent's `merge`, a case that is in belief's
  top 3 keeps belief's confidence and the model's number is discarded; the model's number is used only for a
  case outside belief's top 3, capped at 0.5. On the dev mock run that was 3,170 of the published hypotheses.
- With B or B', the gate still checks every citation against the facts of the answer's evidence tick, and
  published citations are still `t84.F1`; only what the model types changes. This does change the letter of the
  CLAUDE.md rule "Fact IDs carry their tick", so it is a human decision.
- Verifier at cap 30: real case IDs plus a stamped fact ID is 33 to 41 tokens (over). Line numbers
  (`{"v":[[1,"p"],[2,"f"],[3,"p"]],"c":2}`) is 21 to 23. Listing only the failed line numbers is 13.

Questions:
1. Which answer format: A, B, B', or something else?
2. If B or B': is at most 9 fact lines in a diagnosis prompt acceptable? Dev's maximum is 7 facts on a tick.
3. Does the verifier follow the same choice?

## Disagreements recorded, not resolved
- **Plan p.13: "about 50 tokens" for the example answer.** Measured 72 / 78 / 84 / 78. Ratio 1.4 to 1.7.
  Not resolved by changing the format; brought to the human as the blocked item above.
- **Phase 1 hard-stage maximum** did not reproduce (0.778 ms against 1.808 and 1.609); mean and p50 did.
  Unexplained; recorded in the Phase 1 report.
