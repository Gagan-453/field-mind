# Multi-agent Phase 2: prompt shrink: report

## Status
PARTIAL. Commits 0 to 3 are done. The answer format (amendment 1) and the restated gate G1a / G1b with its
predicted counts (amendment 2) are decided and were committed before any G1a run and before any accuracy
measurement. Commits 4 to 7 follow.

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

## AMENDMENT: HUMAN DECISIONS on the answer format (after commit 3, before any accuracy measurement)
Made by the human after seeing the commit 3 token counts (the plan's format needs 89 to 111 tokens against a cap
of 60). No accuracy has been measured with any backend for the shrunk prompts at the time of this amendment.

1. **Format B' for the diagnostician:** line numbers for cases, facts and notes, no model confidences.
   Reasons: it fits 60 with margin (49 tokens worst case on all four tokenizers); option A (raising the cap)
   would break the committed projection formula, which assumes 60 and 30 answer tokens; decode is the
   bottleneck. The line-to-ID map is built when the prompt is built and stored with the job, never recomputed
   when the answer arrives. Test required: an answer for a tick-83 job that arrives at tick 84 maps to t83 IDs.
2. **At most 9 fact lines per diagnosis prompt, most severe first.** Every tick where facts are dropped is
   logged; the count is reported on dev and, once, on the reporting run.
3. **Verifier: line numbers with an explicit pass or fail for every shown case, plus the fact line of the
   strongest contradiction.** Not the failures-only list. Reason: an empty or truncated answer must not read as
   agreement. A case with no verdict counts as "not judged", not as pass.
4. **Faithfulness amendment.** With line numbers, Q3 (cited ID exists) is near 1.0 by construction and no
   longer measures anything. New metric **Q3_rel**: the share of the model's citations for a case that are in
   the deterministic supports set for that case. Computed for every backend and both arches. The Phase 2 gate
   becomes: **Q3_rel drop <= 0.02 against the real-model baseline**; Q3 is still reported. Out-of-range line
   numbers count as invented citations. This replaces "faithfulness drop <= 0.02" in the allowed-drop decision
   above; the group top-1 clauses are unchanged.
5. **Commit 1 deviation, accepted after the fact.** The commit 1 stop rule (a re-run differing by more than 2x)
   tripped on the maximum (0.778 ms against 1.808 and 1.609) and the build continued without stopping. That was
   a deviation from the plan. The human accepts it after the fact, as the human's decision: the maximum of a
   laptop timing is one tick, and mean and p50 reproduced.

Added to the plan by the same amendment:
- **Switch `multi.compact.case_order: score | shuffled`** (shuffled is seeded per tick), default `score`. With
  line numbers, "1,2,3" equals the listed order, so the real-model run must be able to measure position echo.
  Open item: measure it with the real model.
- **Erratum to `docs/multi_agent_plan.pdf`, p.13:** the example diagnosis answer is described as "about 50
  tokens". It measures 72 / 78 / 84 / 78 tokens (Llama 3.2 / Qwen3 / Gemma 3 / Qwen2.5). The PDF itself is not
  edited in this repo; this line is the correction of record until its source is updated.
- **Gemma tokenizer (reported by the human from the other machine, not verified here):** the Hugging Face
  tokenizer and the board's Gemma GGUF give identical IDs on 2,084 dev prompts. To be cited after the merge
  with `main`, and the `tokenizer.model` sha256 compared then.

### Answers to the human's two questions (no code changed to answer them)
**(a) Under B', what confidence does a case outside belief's top 3 get, and does G1 still hold at 0
differences with the mock? It does not hold.**
- Today (`fieldmind/agent/orchestrator.py`, `merge`): a case the model ranks that is not among belief's top 3
  becomes a `model_only` hypothesis with confidence `min(model's confidence, 0.5)`; if the model gives no
  confidence the code's existing default is 0.3. For a case inside the top 3 the model's number is discarded.
- In the Phase 1 dev run the mock supplied that number (`max(0.15, score - 0.1 x rank)`): 3,170 `model_only`
  hypotheses, values 0.15 to 0.50 (2,696 of them 0.15). On 595 of 1,982 non-QUIET ticks the rank-1 hypothesis is
  `model_only`.
- Under B' the model writes no confidence, so the code must supply one, and no choice reproduces the mock's
  numbers without copying the mock's invented formula into the gate. Measured on the Phase 1 dev run:

| choice for a case outside belief's top 3 | `model_only` confidences unchanged | ticks whose rank-1 confidence changes | verifier calls (192 today) |
|---|---|---|---|
| (i) the existing default, 0.3 | 11 of 3,170 | 585 | 140 (52 ticks flip) |
| (ii) belief's own confidence for that case, capped at 0.5 by `merge`; 0.3 when belief has no entry (1,154 of 3,170) | 19 of 3,170 | 580 | 327 (163 ticks flip) |

- Consequence with a real model: under (i) a model-ranked case outside belief's top 3 always sits at 0.3, below
  the verifier band [0.35, 0.75], so in conditional mode the verifier never runs when such a case is rank 1.
- Fields that would move: `confidence` and `confidence_shown` of `model_only` hypotheses, the assessment's
  `confidence` when rank 1 is `model_only`, the verifier trigger and therefore `ver_calls`, the verifier
  envelopes and `envelope_status_counts`. Order, case_ref, cause, supports, discriminator, actions, escalate,
  state, triage, facts, belief_ranking and unexplained are still expected identical. Not checked: why 1,154
  `model_only` cases have no live belief entry.

**(b) What sets the retrieval token budget, and does it differ between the mock config and a llamaserver run
at -c 4096? It does not differ.**
- The budget is `agent.retrieval.context_cap_tokens` per triage level (WATCH 2,048, INVESTIGATE 3,072, URGENT
  1,024), applied in `Retriever._enforce_budget` to a chars//4 estimate of the retrieved items only (case
  title, root cause and discriminating evidence; experience causes; note text; candidates; records; operator
  question). It drops whole items: experience, then notes, then cases. It does not count the rules, the facts,
  the world-model summary or the schema, so it is not a cap on the whole prompt.
- It lives in the `agent` block. `run_demo.load_config` changes only `llm.backend`, and the prompt is built
  before the backend is called, so the same episode gives a byte-identical prompt on mock and on llamaserver.
  `llm.llamaserver.ctx_size` (4,096) is not read by any code; it is the `-c` value for `/board-up`.
- One input that can differ between machines: `data/experience/store.json` is gitignored and absent here. If
  it is non-empty elsewhere, "own past episode" lines are added to the cases block. Here 0 of 2,164 reporting
  prompts and 0 dev prompts contain one.
- **The 2,484 figure is not reproduced and is recorded as unexplained** (measured maximum 2,160 on the
  reporting set; the board campaign's per-call server token counts will settle it after the merge). The plan (p.2) says "~2484-token
  prompt". Here the largest single-agent diagnostician prompt is 2,103 to 2,150 real tokens on dev and 2,120 to
  2,160 on the reporting set (chars//4: 2,284 and 2,274); the same maximum, 2,274, is in the v1 baseline run.
  Ratio 1.15. No run file in this repo contains 2,484 as a prompt size. Untested possible causes: a non-empty
  experience store, a different tokenizer or template, or an earlier prompt version on the board.

## AMENDMENT 2: HUMAN DECISIONS on confidence and on G1 (committed before the G1a run)
1. **Confidence for a case outside belief's top 3: option (ii).** Belief's own confidence for that case, capped
   at 0.5 by `merge`, and the existing 0.3 default when belief has no live entry. Reasons: confidence then always
   comes from the deterministic layer, as it already does inside the top 3; and option (i) would stop the
   verifier from ever running on the ticks where the model and belief disagree. Cost, recorded: verifier calls
   on dev go from 192 to 327.
2. **G1 is restated.**
   - **G1a:** answer-schema switch only, against the Phase 1 multi dev run. Differences are allowed only in the
     confidence-derived fields listed below (and the by-construction moving fields already pre-registered).
   - **G1b:** all switches on, against the G1a run: 0 differences outside the pre-registered moving fields.
   - If a measured count differs from its prediction, or any field outside the list moves: stop and report.
     The prediction is not adjusted.
3. **The 2,484-token figure stays "unexplained, not reproduced".** The measured maximum is 2,160 tokens on the
   reporting set (Gemma 3; 2,120 to 2,157 on the other three). The board campaign's per-call server token counts
   will settle it after the merge with `main`.

### G1a: confidence-derived fields, by name (the only decision fields allowed to move)
| field | where | why it moves |
|---|---|---|
| `hypotheses[].confidence` | only on hypotheses flagged `model_only` | the model no longer supplies it; code supplies belief's value capped at 0.5, or 0.3 |
| `hypotheses[].confidence_shown` | only on `model_only` hypotheses | display value, `min(confidence, margin)`; follows `confidence` |
| `confidence` (assessment) | only on ticks whose rank-1 hypothesis is `model_only` | it is rank 1's shown value |
| verifier envelope present or absent in `envelopes` | ticks where rank 1 is `model_only` and the level is INVESTIGATE or URGENT | the verifier trigger reads rank 1's `confidence` against the band [0.35, 0.75] |
| `ver_calls`, `envelope_status_counts.ok` | per run | follow the verifier trigger |

Nothing else may move: hypothesis order, `rank`, `cause`, `case_ref`, `supports`, `discriminator`, the
`carried` / `model_only` / `verifier` flags, `actions`, `escalate`, `unexplained`, `state`, `triage`, `facts`,
`headline`, `belief_ranking`, `degraded_mode`, `llm_invoked`, `diag_calls`, `parse_failure_rate`,
`verifier_disagreement_rate`, `llm_retries`, and the diagnostician envelope's `status`, `cited_cases`,
`retrieved_cases`, `retries`, `error`, and `cited_facts` after stripping the tick stamp.

### G1a: predicted counts (dev, computed from the Phase 1 run before any Phase 2 code)
| quantity | prediction |
|---|---|
| `model_only` hypotheses | 3,170 |
| of those, `confidence` unchanged | 19 (so 3,151 change) |
| ticks whose rank-1 decision `confidence` changes | 580 |
| verifier calls | 327 (192 in Phase 1) |
| ticks where a cited fact is not among the shown fact lines (would move `supports`) | 0 |

### Summary metrics that move because confidence moved (cause stated in advance)
- `Q2_library.low_conf_rate`, `Q2_heldout.low_conf_rate`, and per episode `T2_root_cause.low_conf_rate` and
  `low_conf_rate_decision`: they read rank 1's shown or decision confidence.
- The `bench/belief_saturation.py` outputs: ECE and the confident-and-wrong counts, for the same reason.
- Verifier call counts (`ver_calls`; 192 -> 327), and `mean_prompt_tokens` through the extra verifier prompts.
- Every other summary key is expected unchanged: Q1, Q2 top-1 / top-3 / group / sep / belief metrics, Q3, Q4,
  Q5, Q6, S4, S7. They depend on order, case, state and actions, none of which may move.

### New harness key for Q3_rel (pre-registered here, before it exists)
Q3_rel needs the deterministic supports of each case at each tick, which no run file holds today. The harness
(`bench/harness.py`, both arches; `fieldmind/agent/` is not edited) will write `belief_supports`
(case -> fact IDs, read from the world model after the tick) into each assessment, and the evaluator will add
`Q3_rel` to the summary and `T3_faithfulness.rel` per episode. So:
- against **Phase 1 run files**, `belief_supports` is excluded by name (those files do not have it); between
  Phase 2 runs it is compared;
- against `results/baselines/single_v3_summary.json`, "0 differences" means every key that file holds; the new
  `Q3_rel` keys are extra and reported.
- Q3_rel on the mock is not an agent result: the mock cites the first two facts whatever the case.

### Item 3: why 1,154 of the 3,170 `model_only` cases have no live belief entry (read-only finding)
They do have a belief entry; it is **retired in the same tick**. `update_hypotheses`
(`fieldmind/agent/world_model.py`) un-retires every retrieved case, updates its log-odds, and then rule 4
retires any hypothesis whose confidence is under `RETIRE_BELOW` = 0.08. All 1,154 are in that state: retrieved
this tick, retired this tick, belief confidence 0.018 to 0.079 (mean 0.030). The mock still ranks them, because
it ranks whatever was retrieved.

Consequence under option (ii), recorded, not fixed: a case belief has just retired as nearly dead is shown at
the 0.3 default, above 745 of the 2,016 live `model_only` cases whose belief confidence is under 0.3 (lowest
0.08). So "no live entry" is not "unknown"; it means "belief holds it below 0.08". It does not change the gate:
the predictions above were computed with exactly this rule. **Open item for `main`** (it is in
`fieldmind/agent/`, so not changed here): decide whether a retired-this-tick case should take its retired belief
confidence instead of the 0.3 default, and whether retrieval should return cases belief has retired.

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
**Resolved: the answer format.** The ID-only format of the plan did not fit the caps (89 to 111 tokens against
60; verifier 33 to 41 against 30). The human chose format B' and the explicit pass/fail verifier; see the
amendment. Measured worst cases: diagnostician B' 49 tokens on all four tokenizers; verifier with a verdict for
each of 3 cases plus a fact line, 21 to 23.

**Resolved: gate G1 under B'.** The human chose option (ii) and the G1a / G1b split; see amendment 2.

## Disagreements recorded, not resolved
- **Plan p.13: "about 50 tokens" for the example answer.** Measured 72 / 78 / 84 / 78. Ratio 1.4 to 1.7.
  Not resolved by changing the format; brought to the human as the blocked item above.
- **Phase 1 hard-stage maximum** did not reproduce (0.778 ms against 1.808 and 1.609); mean and p50 did.
  Unexplained; recorded in the Phase 1 report.
