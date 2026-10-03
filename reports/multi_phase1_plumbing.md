# Multi-agent Phase 1: plumbing: report

## Status
PARTIAL: built and the dev gate passes on every clause. Still to do: the phase-reviewer review and the one-shot reporting run.

**Every number below comes from the mock backend.** The mock backend re-ranks retrieved cases and does no reasoning, so these
figures measure the deterministic and retrieval layers only. They are not an agent result. All timings are **laptop timings**
(Apple M5, agent code on the laptop, no board), not board timings.

## Phase 1 gate (pre-registered, committed before any Phase 1 code: `0404b04`)

Backend: mock only. The phase is model-agnostic: no model is chosen and there is no real-model baseline, because the Session 2
board runs have not been done. Mode: lockstep only, so every job finishes inside its tick.

Pass requires all of:

1. **Decision identity, dev.** On all 36 dev episodes (`data/episodes_dev`) with `--backend mock`, every decision field is
   identical between `--arch single` and `--arch multi`.
2. **Prompt identity.** Every prompt sent to the backend is byte-identical and sent in the same order. Each call is recorded
   with its role, max_tokens and a hash of the mock hint; repair calls are included; the two logs are diffed.
3. **Baseline unchanged.** `--arch single` on this branch reproduces current `main` (`ca93ed5`) exactly: 0 differences on the
   same field list, prompts included.
4. **Timing.** S7 deadline misses are 0 on both arches. Report the per-tick overhead of the multi plumbing in ms and the
   deterministic-assessment (P0 hard path) time against the 200 ms target, as **laptop timing**, not board timing.
5. **Tests.** One-writer enforcement, scheduler priority order, lane choice, and evidence-tick stamping each have a test,
   and each test is mutation-checked with `PYTHONDONTWRITEBYTECODE=1` and `__pycache__` cleared.

If any decision field differs, stop and report the first (episode, tick, field) where it differs. The single agent is not
changed to make them match.

After the build: run the phase-reviewer subagent, then one reporting-set run (30 episodes) with both `--arch` values,
expecting 0 differences, then commit and tag `multi-phase1`.

### Compared fields (fixed before the build)
Per assessment:
- `tick`, `timestamp`, `state`, `triage`, `headline`, `facts`
- `hypotheses`: their order, and every key: cause, rank, case_ref, confidence, confidence_shown, supports (= cited fact IDs),
  discriminator, and the verifier / carried / model_only flags
- `belief_ranking`, `actions`, `escalate`, `unexplained`, `confidence` (shown), `degraded_mode`, `llm_invoked`
- per envelope: `agent`, `tick`, `status`, `payload`, `cited_facts`, `cited_cases`, `tokens`, `prompt_tokens`,
  `retrieved_cases`, `retries`, `error`, `prompt`, `raw_reply`
- per call: `status`, `prefill`, `decode`, `decode_ms`

Per run: `n_ticks`, `diag_calls`, `ver_calls` (the LLM call count), `llm_invocation_rate`, `parse_failure_rate`,
`verifier_disagreement_rate`, `llm_retries`, `mean_prompt_tokens`, `envelope_status_counts`.

Summary: every key of `summary_*.json` except the latency keys.

### Excluded fields (fixed before the build)
- `latency_ms` (envelope and per call)
- `prefill_ms` per call (the mock's ttft is derived from latency)
- `tick_latency_ms`, `wall_clock_s`, and the `S1_*` latency keys
- the multi-only `multi` telemetry key (jobs, lanes, queue wait)
- `deadline_miss` / `deadline_miss_rate`: these are timing-derived, so they are reported separately as S7 rather than compared

## Gate result (dev, 36 episodes, mock, HEAD `abdf2e9`, clean tree)

| clause | result | verdict |
|---|---|---|
| 1. decision identity, multi vs single | `bench/compare_runs.py`: **0 differences** over 36 episodes, 5,850 assessments and 2,174 envelopes; the summaries also have 0 differences | PASS |
| 2. prompt identity | 2,174 recorded calls on each side; **`cmp` reports the logs byte-identical**, same sha256 (`6e9b748a…`) | PASS |
| 3. single on branch vs main `ca93ed5` | runs: 0 differences; summary: 0 differences. The single prompt log is also byte-identical to the one recorded before the refactor | PASS |
| 4. S7 / timing | S7 misses = 0 for single and multi, in both repetitions. P0 never exceeded 200 ms (0 of 5,850 ticks). Timing table below | PASS |
| 5. tests | 47 new tests; all 9 mutations were caught (table below); full suite 145 passed | PASS |

No decision field differed, so there was no first differing tick to report.

### Timing (laptop, mock; dev, 5,850 ticks; two repetitions, interleaved)
| | rep 1 | rep 2 |
|---|---|---|
| single tick ms: mean / p95 / max | 0.408 / 0.764 / 1.66 | 0.425 / 0.786 / 2.55 |
| **plumbing overhead, audit off** (paired multi−single per tick): mean / p50 / p95 / max | **0.020 / 0.012 / 0.060 / 1.90** | **0.005 / 0.008 / 0.059 / 1.64** |
| plumbing overhead, audit on: mean / p50 / p95 / max | 6.36 / 2.65 / 22.0 / 121.2 | 6.33 / 2.68 / 22.1 / 50.6 |
| **P0 deterministic-assessment ms, audit off** (all ticks): p50 / p95 / max | **0.377 / 0.644 / 2.20** | 0.376 / 0.646 / 2.01 |
| P0, audit off, non-QUIET ticks (1,982): p50 / p95 / max | 0.540 / 0.657 / 2.20 | 0.528 / 0.664 / 2.01 |
| P0, audit on (all ticks): p50 / p95 / max | 3.25 / 15.4 / 100.5 | 3.29 / 15.4 / 27.6 |
| P0 > 200 ms | 0 | 0 |
| S7 deadline misses, single / multi (audit on and off) | 0 / 0 | 0 / 0 |

The P0 time runs from tick start to the deterministic assessment: sensor, triage, signature, retrieval and belief, then the
gate's approve on belief's claims. On QUIET ticks it covers the whole tick. In lockstep the published assessment is still the
final one; the P0 assessment is telemetry.

**The write audit is the expensive part.** It costs about 300× the plumbing itself, and up to 122 ms on a laptop tick, because
it fingerprints every section (including the growing event log and the assessment) around each agent step. On a slower board
CPU this could approach the 200 ms budget. See Decisions taken, item 3.

### Lane and job telemetry (dev, multi, simulated clock; rates are ASSUMED placeholders, see Constants)
| | value |
|---|---|
| jobs | 2,174 = 1,982 diagnostician + 192 verifier. This equals `diag_calls + ver_calls`; stale drops 0; replaced 0 |
| diagnostician P1 (URGENT): lane | NPU 118, CPU 199 |
| diagnostician P2: lane | NPU 1,615, CPU 50 |
| verifier P3: lane | NPU 48, CPU 144 |
| queue wait (simulated) | 0 for 99.7% of jobs; max 1.3 s |
| simulated deadline misses | P1 317 of 317, P2 0 of 1,665, P3 0 of 192 |
| finish more than 30 s after the evidence tick | 142 of 2,174 (diagnostician then verifier: mean 31.0 s, max 35.6 s) |
| lane busy (simulated) | NPU 36,093 s, CPU 6,508 s |
| prompt tokens (estimate) | diagnostician mean 2,036, max 2,285, **1,980 of 1,982 over 1,280**; verifier max 2,095, 170 of 192 over 1,280 |

All P1 jobs miss the 10 s P1 deadline, because a ~2,000-token prompt plus a 256-token answer cap does not fit 10 s at either
lane's planning rate (NPU ≈ 2.2 + 18.4 s). That is the expected Phase 1 outcome: the prompt shrink (Phase 2) and the
60-token cap are what make P1 feasible. These are simulated-clock numbers on placeholder rates, so they are not a measurement.

### Dev summary (mock; identical for both arches)
| metric | value |
|---|---|
| Q1 macro F1 | 0.782 |
| Q2 top-1 / top-3 | 0.332 / 0.453 |
| library: belief top-1 tie-fair / belief group | 0.375 / 0.502 |
| Q3 faithfulness | 1.0 |
| Q4 precision / recall | 0.357 / 0.882 |
| Q5 FP/h | 0.98 |
| Q6 lead time (min) | 32.4 |
| S4 LLM invocation rate | 0.337 |
| S7 | 0.0 |

## Design note

**The tick (lockstep):**
1. `gate.begin_tick`
2. P0 path: `sensor` → `triage` → (if QUIET, gate publishes and the tick ends) → `sensor.signature` → `retriever+belief` →
   gate publishes the deterministic assessment
3. scheduler: diagnostician job (P1 if URGENT, else P2) → gate checks the result against the evidence tick's facts and merges
   it into the diagnosis slot
4. scheduler: verifier job (P3), only when `should_run` says so → gate writes the verdict
5. gate+memory: approve, shown confidence, assessment, event log, status

This is the single agent's order exactly. Every step runs inside `bb.step(agent)`.

**Blackboard sections** (`fieldmind/multi/blackboard.py`, `OWNERS`):

| section | single writer | readers | WorldModel field |
|---|---|---|---|
| facts (per tick; index of stamped ids `t84.F1`) | sensor | all | none (new) |
| trust | sensor | sensor (next tick), triage, diagnostician (summary) | `trusted_tags` |
| residuals | sensor | triage (trip extrapolation) | `residuals` |
| findings | sensor | triage, diagnostician (summary) | `open_findings` |
| baselines | sensor | none in Phase 1 | `baselines` |
| signature (+ slopes) | sensor | retriever | none |
| outbox.sensor (this tick's events) | sensor | gate | none |
| triage (level, reason, plant state) | triage | orchestrator / scheduler, gate | none |
| retrieval (packet) | retriever | diagnostician, gate | none |
| belief (hypotheses, log-odds) | retriever | diagnostician (summary), gate (shown confidence) | `hypotheses` |
| outbox.retriever | retriever | gate | none |
| jobs (job table) | scheduler | telemetry | none |
| diagnosis (checked, merged claims) | gate | verifier, gate | none |
| verdict | gate | gate | none |
| status (`degraded_mode`, tick, state) | gate | triage (`derive_state`) | `degraded_mode`, `tick`, `state` |
| events (timeline) | gate | evaluator / checkpoint | `timeline` |
| assessment | gate | harness, evaluator | none |

The diagnostician and verifier own no section. Their answers return as Results, and only the gate puts them on the board.

**Enforcement** has three layers:
- `write`/`mutable` raise `WriterError` for a non-owner, and for an owner writing during another agent's step.
- `read` returns read-only containers.
- The audit (`multi.audit_writes`) fingerprints all sections around every step and raises if a non-owner's step changed one.
  This catches in-place mutation by the reused world-model functions.

Those functions are given a namespace that holds only the calling agent's live sections plus a fresh event outbox. Events
reach the log only through the gate, in pipeline order.

**Messages** (`fieldmind/multi/jobs.py`):
- `Job{job_id, agent, side, evidence_tick, priority 1..4, deadline_s, max_answer_tokens, submit_s, lane, prompt_tokens,
  predicted_finish_s, start_s, finish_s}`.
- `Result{job, envelope, evidence_tick, lane, queue_wait_ms, start_s, finish_s, stale}`.
  - The envelope is the existing `AgentEnvelope`, unchanged, so it goes into `Assessment.envelopes` exactly as in the single
    agent.
  - The scheduling fields go to `assessment["multi"]["results"]`, in the same order as `envelopes`.

**Lanes and scheduler** (`fieldmind/multi/lanes.py`, `fieldmind/multi/scheduler.py`):
- Each `SimLane` runs one job at a time (a second `begin` raises `LaneBusy`) on a simulated clock. A job starts at
  max(submit, lane free) and takes prompt/prefill + answer/decode seconds; the answer length is capped at `max_tokens`.
- `LaneBackend` is the backend the Diagnostician and Verifier are built on, which is why they are unmodified. The job's first
  call picks the lane by earliest predicted finish (ties go to the NPU), and repair calls stay on that lane.
- The queue is ordered by (priority, submit order), with at most one waiting job per (agent, side).
- On mock, both lanes share one backend. On llamaserver, each lane gets its own URL (8080 / 8081). That path is wired but was
  not run this session.

**Fact IDs.** Fact objects keep their local id (`F1`) because the prompt text must be byte-identical in Phase 1. The stamp
lives in the board's index (`FactsBook.stamped_ids`, `resolve("t84.F1")`). The gate resolves citations against
`facts_of(result.evidence_tick)`, which is tested to differ from using the current tick.

## Verification
| step | result |
|---|---|
| ran the module | dev, single and multi, mock: 36 episodes, 5,850 ticks each, exit 0 |
| self-tests | `pytest`: **145 passed** (98 before + 47 new); `bench` scripts 20/22/16 passed after the refactor |
| independent re-derivation | LLM call count by three routes: prompt-log lines by role (1,982 diag + 192 ver = 2,174) = run counters `diag_calls`+`ver_calls` (2,174) = lane `n_jobs` sum (2,174); relative difference 0. Decision identity by a second method: a whitelist sha256 over the decision fields (not `compare_runs`' blacklist walk) gives `e43b0ceb4d073cee` for main, single and multi |
| mutation check | 9 mutations, 9 caught (next table) |
| comparator can fail | 3 injected differences (a confidence_shown +0.001, a prompt +1 space, diag_calls +1) were all reported; a +50 ms `tick_latency_ms` was correctly ignored |

### Mutation checks (`PYTHONDONTWRITEBYTECODE=1`, `__pycache__` cleared before and after each)
| mutation | caught by |
|---|---|
| blackboard `_check` owner test disabled | `test_every_section_rejects_every_non_owner[*]` (17), `test_wrong_writer_leaves_section_unchanged`, `test_events_reach_the_log_only_through_the_gate` |
| audit owner comparison disabled | `test_audit_catches_in_place_mutation_by_non_owner`, `test_audit_catches_deep_mutation_inside_a_section` |
| scheduler priority sort inverted | `test_dispatch_is_by_priority_then_submit_order` |
| no replacement of a waiting job | `test_newer_job_replaces_waiting_one_for_same_agent_and_side` |
| predictor prefill/decode rates swapped | `test_prompt_heavy_job_goes_to_fast_prefill_lane`, `test_queue_wait_on_one_lane_is_exact`, `test_answer_longer_than_cap_is_clocked_at_the_cap`, `test_repair_call_stays_on_the_lane_of_the_first_call` |
| lane choice by latest finish | `test_prompt_heavy_…`, `test_decode_heavy_…`, `test_busy_lane_loses_to_idle_lane`, `test_repair_call_…` |
| gate checks citations against the current tick | `test_citation_checked_against_evidence_tick_not_current_tick` |
| stale threshold 1 → 2 ticks | `test_answer_older_than_one_tick_is_dropped_and_logged` |
| Result evidence tick not taken from the job | `test_result_carries_the_jobs_evidence_tick`, `test_episode_every_result_stamped_with_its_tick_and_decisions_match` |

## Direction checks
None: no physical response is modelled in this phase.

## Constants introduced
| symbol | value | provenance | range | affects |
|---|---|---|---|---|
| `multi.deadlines_s` P1/P2/P3/P4 | 10 / 30 / 60 / none s | CITED: plan, "Priorities and deadlines" (p.10) | none | simulated deadline-miss telemetry only |
| `multi.lanes.npu` prefill / decode | 909 / 13.9 tok/s | CITED: plan, "Rates used for planning" (p.14): Llama 3.2 3B Q4_0, llama.cpp NPU. ASSUMED as this project's NPU lane rate | unknown until the chosen GGUF is measured (Session 2); the plan's own NPU figures span 839–909 prefill and 11.7–13.9 decode | lane choice and the simulated clock only; never a mock decision (both lanes call one backend) |
| `multi.lanes.cpu` prefill / decode | 126 / 42 tok/s | CITED: plan p.15: Gemma 3 1B, LiteRT-LM CPU. ASSUMED as the CPU lane rate; a different model and runtime from the NPU row | unknown until measured | same |
| `FactsBook.keep` | 2 ticks | DERIVED: the stale rule accepts answers at most one tick old, so the current and previous tick suffice | none | which evidence ticks the gate can resolve |
| simulated decode length | min(reply decode tokens, max_tokens) | DERIVED: a server stops at `max_tokens`; the mock ignores the cap and reports len(text)//4 ≈ 960 | none | simulated clock only |

## Numbers that changed
None. Decisions, prompts and summaries are identical to `main` `ca93ed5`.

## Decisions taken
1. **Glue extraction in `fieldmind/agent/` (user's choice).** Commit `10ce4df` moved about 40 lines of tick glue out of
   `Orchestrator.tick` into module functions that `fieldmind/multi` imports. It was proven with 0 decision differences against
   main, a byte-identical prompt log, and passing pytest and bench scripts.
2. **Triage is its own agent.** The plan folds L2 into the scheduler; the session prompt lists triage separately. Keeping it
   separate keeps the scheduler a pure job/lane component. This changes no behaviour.
3. **`audit_writes: true` by default.** This is the conservative choice: it is the strongest single-writer check. It costs
   6.3 ms mean, 22 ms p95 and up to 122 ms per laptop tick. It must be off, or made incremental, before board P0 timings
   (Session 6) are trusted. Recorded under Open items.
4. **P1 rules not applied.** The plan's P1 rules ("verifier skipped", "shortest prompt") and rate adaptation from measured
   timings would change decisions or need real time, so they are not built. P1/P2/P3 only set priority and deadline.
5. **Simulated decode is capped at `max_tokens`** (see Constants). This is telemetry only.
6. **`build_multi_agent` lives in `bench/harness.py`, not in `fieldmind/multi/`.** That keeps `fieldmind/` free of `bench`
   imports for the device copy. It builds the components through `build_agent`, so nothing is duplicated.

## Disagreements recorded, not resolved
- **Prompt cap.** CLAUDE.md requires every prompt to stay under 1,280 tokens. In Phase 1, 1,980 of 1,982 diagnostician prompts
  and 170 of 192 verifier prompts exceed it (estimated: mean 2,036, max 2,285). This is forced by gate clause 2: prompts must be
  byte-identical to the single agent's. Shrinking them is Phase 2's job. Prompt and answer tokens are logged per call.
- **Answer caps.** The plan's caps (diagnostician 60, verifier 30) are not applied; the single agent's `agent.max_tokens` of 256
  is kept, for the same reason.
- **P1 is infeasible at these sizes.** On the simulated clock every P1 job misses its 10 s deadline. That is consistent with
  the plan's own arithmetic for a ~2k-token prompt and a 256-token cap.

## Blocked / needs a decision
- None blocking Phase 1.
- Carried forward: no model is chosen and the lane rates are placeholders until the Session 2 board runs.

## Open items
- An audit mode cheap enough for the board: incremental fingerprints, or audit only in tests and lockstep runs.
- Real-time mode, the "hard path never waits on a lane" test (with a fake lane that sleeps 60 s), the degradation ladder, and
  rate adaptation: Session 6. The stale rule's "unless that side's evidence is unchanged" clause needs sides: Phase 3.
- The capped model→belief update (the plan's "the belief agent moves log-odds by a capped amount"). In Phase 1 a model answer
  only reorders the shown claims through the single agent's `merge`, exactly as before. The capped update is new behaviour,
  so it belongs to a later phase.

## What I could not verify
- **Board timings.** Every millisecond here is laptop time with the agent code on the laptop. The P0 margin on the SM8650
  is unknown.
- **The llamaserver lane wiring.** Per-lane URLs (`make_lanes`) were not exercised. This session is mock-only, and no lane was
  started.
- **Lane-choice realism.** The lane rates come from two different models in the plan, and the simulated clock omits the
  plan's overhead term. The lane split and simulated deadlines above therefore illustrate the mechanism; they are not
  predictions.
