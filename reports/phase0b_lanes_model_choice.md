# Phase 0b, Session 2: persistent model servers and model choice — report

Baseline: **single-agent-v3** (`results/baselines/single_v3_summary.json`, mock). Mock numbers in this report measure only
the deterministic and retrieval layers. They are **not agent results**. Energy is `null` everywhere because no power
was measured. Agent code runs on the **laptop**, and only model calls run on the board. Hard-path timings are laptop
timings, not board timings.

## Status
PARTIAL. Steps 1, 2 and 4 are built and tested: `LlamaServerBackend`, board tooling, the ranking rule and the
model-choice tool. The mock reference row is run. **Blocked on the board:** `adb devices` lists no device, so
`/board-up`, the candidate runs, the lane rates and the reporting run have not happened.

## Decisions taken
1. **C episode = `dev_C02_feeder_trip`** (truth RCA-14, library). The C twins C01/C03/C05/C06 are held-out (RCA-06):
   they cannot score top-1 or library ECE. The model-choice set is `dev_A01_fcv_seize` (RCA-01),
   `dev_B01_tube_leak` (RCA-11) and `dev_C02_feeder_trip` (RCA-14).
2. **No JSON grammar** (`json_mode: false`), so the broken-JSON rate measures the model. The plan's open decision ranks
   models on that rate, and a grammar would push it to about 0.
3. **`cache_prompt: false`**, so `prefill_tokens` and prefill tok/s count every prompt token.
4. **temperature 0, seed 0**, so runs can be reproduced. Design choice.
5. **Ranking verdict: measured and recorded; `_merge` is not changed in this session.** A "belief decides" verdict
   becomes a separate keep/revert step on dev.
6. `llm.backend` default stays `mock`. The URL lives in `llm.llamaserver.url` (the per-backend sub-block that
   `make_backend` reads), not in a top-level `llm.url`.
7. Model-choice runs use dev episodes only. The 30 reporting episodes run once, at the end, with the chosen model
   (user rule).

## Pre-registered: the ranking question (written and committed before any real-model run)
The question: should belief decide rank-1, with the model only breaking ties, or does the model's order stay?

- **Population.** Post-onset ticks of library-truth episodes that meet all of these:
  - the belief ranking is non-empty;
  - the diagnostician envelope is `ok`, and the gate kept the model's order (raw citation faithfulness ≥
    `min_faithfulness` = 0.5);
  - the **model's own rank-1** is in a group that is **none** of the groups of belief's tied top set. The model's
    rank-1 is `payload.hypotheses[0]`, resolved by cause against the deterministic hypotheses and then by
    `case_ref`, the same way `_merge` resolves it.
- **Scoring.**
  - Model correct means its rank-1 case lies in the true group (`case_groups.json`). A model-only idea with no case
    counts as incorrect and is counted separately.
  - Belief correct is tie-fair: the share of the tied top set that lies in the true group.
- **Rule.**
  - n < 30 → INCONCLUSIVE.
  - p_belief − p_model ≥ 0.10, and belief ≥ model in every episode with ≥ 10 such ticks → **BELIEF_DECIDES**.
  - The mirror image → **MODEL_DECIDES** (status quo).
  - Anything else → INCONCLUSIVE (status quo kept).
  - The 0.10 margin and the n and episode floors are pre-registered decision constants (design choice, not derived).
    Ticks are autocorrelated, so the per-episode clause stands in for a significance test.
- **Decided on the chosen model's dev runs.** Reported for every candidate. Also reported:
  - the same statistic using the **shown** rank-1 (the population definition the mock prior used);
  - the same statistic on the **mock** run of the same three dev episodes.
- **The mock prior is a different population.** Session 1b's figures (belief 41%, model order 28%, 276 ticks) cover
  only the reporting-set ticks that are in the lowest confidence bin and have a negative margin.
- Code: `bench/model_choice.py` (`ranking_question`, `verdict`). Tests: `tests/test_model_choice.py`.

### Mock reference on the same population (not an agent result)
| mock, dev A01+B01+C02 | n | p_belief | p_model | verdict |
|---|---|---|---|---|
| pooled | 157 | 0.239 | 0.389 | INCONCLUSIVE |
| dev_A01_fcv_seize | 53 | 0.000 | 0.528 | |
| dev_B01_tube_leak | 69 | 0.145 | 0.478 | |
| dev_C02_feeder_trip | 35 | 0.786 | 0.000 | |

On the mock, the model's rank-1 and the shown rank-1 give identical figures, because the mock answers on every
invoked tick and the gate never drops it. Pooled, these three dev episodes go the **opposite** way to the
reporting-set prior. C02 disagrees with A01 and B01, so the rule returns INCONCLUSIVE.

## Follow-up (Session 2, part 2): missing timings are None
- `LlamaServerBackend` now returns `None`, not 0, for any timing field the server does not send:
  `prefill_tokens` ← `prompt_n`, `decode_tokens` ← `predicted_n`, `ttft_ms` ← `prompt_ms`. A failed call also
  carries `None`. The other backends are unchanged. **LiteRT still writes 0 for anything it cannot parse.** That is
  not changed here; it is noted only.
- **One agent change, telemetry only:** the diagnostician's repair path (`l4_diagnose.py`) used to add the two calls'
  token counts, and adding `None` would crash. A count that either call did not report now stays `None`. No decision
  reads these counts. The mock run of the 3 dev episodes is identical before and after: 400 assessments, 0
  decision-field differences, 0 token differences.
- `env.prompt_tokens` still falls back to `est_tokens(prompt)` when the server sends no count. That is existing,
  documented behaviour. `bench/model_choice.py` therefore uses the server count `tokens.prefill` for prompt tokens,
  not `prompt_tokens`.
- Aggregations skip `None` and report the count of missing values per field:
  - `bench/board.py`: `lane_speed()["missing"]`, `mean_rates()` with `<field>_missing`, and `decode_rate_wallclock()`
    gives `None` if a count is missing;
  - `bench/model_choice.py`: `prompt_tokens_missing` and `answer_tokens_missing` rows.
  - TTFT is not stored in the envelope, so it is not aggregated in the table.
- Tests: `tests/test_llamaserver_backend.py` (no timings, partial timings, failed call) and
  `tests/test_missing_timings.py` (repair path, both aggregations). `pytest`: 89 passed / 0 failed.
- Mutation checks, run on scratch copies; all caught:
  - backend fills 0 for missing → 2 tests;
  - repair sum treats `None` as 0 → `test_repair_path_keeps_unknown_counts_unknown`;
  - `model_choice` counts `None` as 0 → `test_model_choice_excludes_none_and_counts_it`;
  - `board.mean_rates` counts `None` as 0 → `test_board_mean_rates_excludes_none_and_counts_it`;
  - a failed call drops the explicit `None`s → `test_failed_call_reports_no_counts`.

## Verification
| step | result |
|---|---|
| ran the module | mock run on the 3 dev episodes via the edited `run_demo.py`: 400 assessments, **0** decision-field differences against Session 1b's `runs_mock_dev_c.json` (hypotheses, belief_ranking, state, triage, actions, escalate, llm_invoked). `bench.model_choice` runs on it (table above). Live board call: **not run (no device)** |
| self-tests | `pytest tests`: 83 passed / 0 failed (72 before, plus 7 backend and 4 model-choice tests). `bench/test_checks.py` 20/0, `test_envelope_logging.py` 16/0, `test_orchestrator.py` 22/0. A bare `pytest` (no path) errors at collection, because `bench/test_checks.py` calls `sys.exit` at import. This predates this session (checked on the stashed tree) |
| independent re-derivation | planned: decode tok/s from client wall clock, by differencing two calls that differ only in `max_tokens` (`bench.board.decode_rate_wallclock`), against the server's `predicted_per_second`. **Not run (no device)** |
| mutation check | Run on scratch copies; the repo was untouched. Backend: (M1) swap `prompt_n` and `predicted_n`: caught by `test_every_field_comes_from_server_timings`. (M2) `prompt_ms` × 1000: caught by the same test. (M3) lane label hard-coded: caught by it and by `test_registered_and_built_from_config`. Ranking statistic: (M1) group comparison replaced by case comparison: 3 tests fail. (M2) tie-fair dropped: `test_population_and_scoring_worked_by_hand`. (M3) gate filter removed: 3 tests fail. (M4) `n < 30` changed to `<=`: `test_verdict_rule_boundaries` |

Found while testing: in `verdict`, 0.50 − 0.40 evaluates to 0.0999… in floating point, so an exact 0.10 margin would
have failed the rule. The difference is now rounded to 3 d.p., the same rounding the rates already get. The boundary
test caught this.

## Direction checks
None: no physical response was added or changed.

## Constants introduced
| symbol | value | provenance | range | affects |
|---|---|---|---|---|
| `llamaserver.ctx_size` | 4096 | DERIVED: max `context_cap_tokens` 3072 + `max_tokens` 256 = 3328, rounded up to 2^12 | n/a | `-c` on both lanes; a prompt over it would be truncated or rejected |
| `llamaserver.timeout_s` | 120 | ASSUMED: 256 tokens at the plan's ~12 tok/s decode is ~21 s, plus about 3 s prefill, with a wide margin | [30, 300] s | when a slow call counts as a timeout |
| `llamaserver.cpu_threads` | 6 | /board-up skill starting value | to be measured | CPU lane decode rate |
| `temperature` / `seed` | 0.0 / 0 | design choice (reproducibility) | n/a | answers; greedy decoding |
| ranking rule margin / n floor / episode floor | 0.10 / 30 / 10 | pre-registered decision constants | n/a | the ranking verdict only |

## Numbers that changed
None so far. No decision path changed: the mock dev run is identical to Session 1b.

## Disagreements recorded, not resolved
- Mock ranking statistic on these three dev episodes (model 0.389 > belief 0.239) against the reporting-set prior
  (belief 41% > model 28%). They are different populations, and dev is not reporting. Recorded, not explained.

## Blocked / needs a decision
- **No device attached** (`adb devices` is empty). Steps 3, 5 and 6 need the QIDK on USB.

## What I could not verify
- Everything on the board: the server's timing fields on this llama.cpp build, the HTP0 offload, both lanes' rates and
  the thermal zone names.
- The backend is tested only against a fake server that returns the documented llama-server `timings` keys. If this
  board's build names them differently, every field stays 0 instead of being guessed. The first live call checks this.
