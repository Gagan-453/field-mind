# Multi-agent Phase 2: prompt shrink: report

## Status
PRE-REGISTRATION ONLY. This file was committed before any Phase 2 measurement or code. It holds the human
decisions, the dev gate, and the statement of what is expected to change. Results are added below as commits land.

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
