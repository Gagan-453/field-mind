# Multi-agent Phase 1: plumbing: report

## Status
PARTIAL: gate pre-registered (this section), nothing built yet.

## Phase 1 gate (pre-registered, committed before any Phase 1 code)

Backend: mock only. Model-agnostic: no model is chosen and there is no real-model baseline (Session 2 board runs not done).
Mode: lockstep only (every job finishes inside its tick).

Pass requires all of:

1. **Decision identity, dev.** On all 36 dev episodes (`data/episodes_dev`) with `--backend mock`, every decision field is
   identical between `--arch single` and `--arch multi`.
2. **Prompt identity.** Every prompt sent to the backend is byte-identical and sent in the same order (recorded per call
   with role, max_tokens and a hash of the mock hint; repair calls included; diffed).
3. **Baseline unchanged.** `--arch single` on this branch reproduces current `main` (`ca93ed5`) exactly: 0 differences on the
   same field list, prompts included.
4. **Timing.** S7 deadline misses = 0 on both arches. Report the per-tick overhead of the multi plumbing in ms and the
   deterministic-assessment (P0 hard path) time against the 200 ms target. **Laptop timing**, not board timing.
5. **Tests**, each mutation-checked with `PYTHONDONTWRITEBYTECODE=1` and `__pycache__` cleared: one-writer enforcement,
   scheduler priority order, lane choice, evidence-tick stamping.

If any decision field differs: stop and report the first (episode, tick, field) where it differs. The single agent is not
changed to make them match.

After the build: phase-reviewer subagent, then one reporting-set run (30 episodes) with both `--arch` values, expecting 0
differences, then commit and tag `multi-phase1`.

### Compared fields (fixed now)
Per assessment: `tick`, `timestamp`, `state`, `triage`, `headline`, `facts`, `hypotheses` (order, and every key: cause, rank,
case_ref, confidence, confidence_shown, supports = cited fact IDs, discriminator, and the verifier / carried / model_only
flags), `belief_ranking`, `actions`, `escalate`, `unexplained`, `confidence` (shown), `degraded_mode`, `llm_invoked`, and per
envelope: `agent`, `tick`, `status`, `payload`, `cited_facts`, `cited_cases`, `tokens`, `prompt_tokens`, `retrieved_cases`,
`retries`, `error`, `prompt`, `raw_reply`, and per call `status`, `prefill`, `decode`, `decode_ms`.

Per run: `n_ticks`, `diag_calls`, `ver_calls` (LLM call count), `llm_invocation_rate`, `parse_failure_rate`,
`verifier_disagreement_rate`, `llm_retries`, `mean_prompt_tokens`, `envelope_status_counts`. Summary: every key of
`summary_*.json` except latency keys.

### Excluded fields (fixed now)
`latency_ms` (envelope and per call), `prefill_ms` per call (mock ttft is derived from latency), `tick_latency_ms`,
`wall_clock_s`, `S1_*` latency keys, and the multi-only `multi` telemetry key (jobs, lanes, queue wait). `deadline_miss` /
`deadline_miss_rate` are timing-derived and are reported separately as S7 rather than compared.
