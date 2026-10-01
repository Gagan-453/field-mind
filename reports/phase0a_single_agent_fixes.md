# Phase 0a: single-agent correctness fixes: report

All numbers below are from the **mock backend**. They measure the deterministic and retrieval layers only. They are
**not agent results**; the mock re-ranks retrieved cases and does no reasoning. Energy fields are `null` (no device).
`/bench` was run as `run_demo.py --all --backend mock` because `--arch` and `--mode` do not exist yet. Reference
baseline: `results/baselines/single_v1_summary.json` (reproduced exactly at HEAD before any change: 30 episodes, summary
identical, per-episode Q1/Q2 identical, 2164 retrieval rows saved as the identity reference).

## Status
**PARTIAL**: items 1–5 built and committed (2 steps for item 1, plus a tie-fair diagnostic). Two of the changes
(Step B, retirement) move the mock numbers in **mixed** directions and need your decision (see *Blocked / needs a
decision*). Nothing was run on the NPU or a cloud model, so Phase 0's "mock and NPU" check is half done.

Commits (all on `main`, none pushed): `934bf0b` config · `7588d11` groups/metrics/telemetry ·
`73a4208` tie-fair · `add57e3` A1 · `b6fb8b1` A2 · `d822130` B · `9ce3cba` retirement · docs and this report (next commit).

## Verification
| step | result |
|---|---|
| ran the module | `run_demo.py --all --backend mock` after every commit; deterministic (final run identical to the retirement run, retrieval dump identical) |
| self-tests | `tests/` 32 passed, 0 failed; `bench/test_checks.py` 20/0, `test_envelope_logging.py` 16/0, `test_orchestrator.py` 22/0 (those three are standalone scripts, run as `python bench/<name>.py`) |
| independent re-derivation | `Q2_library.group_top1`: evaluator **0.566**, independent script **0.5660** (rel. diff 0.01%, rounding). The script imports nothing from `bench`, uses hand-written Stage 5 clusters instead of `case_groups.json`, and counts ticks from the raw runs file. Per family A/B/C/D also agree (0.510/0.647/0.287/0.822 vs 0.51/0.647/0.287/0.822) |
| mutation check | see table below; every corruption was caught |

| corrupted | caught by |
|---|---|
| grouping threshold 0.5 → 0.25 | 4 tests in `test_case_groups.py` (file-reproduces, Stage 5 clusters, library-sensitivity, held-out membership) |
| A1: contradiction back to tag-only | 5 tests in `test_belief_triples.py` (flat-bed, up-med, shared-function, both A01 replays) |
| A2: absence step unscaled | `test_flat_evidence_moves_belief_less_than_movement` |
| B: ignore direction in band rule | 4 tests (up-med, shared-function, replay, same-direction) |
| B: `>=` → `==` | `test_bed_down_fast_contradicts_a_down_med_contradiction` |
| retirement: `>=N` → `>N` | `test_stale_tied_hypothesis_is_retired_exactly_at_n_and_logged_once`, `test_retrieval_again_revives_and_resets_the_counter` |
| retirement: counter not reset | the same two tests |

One harness hazard found along the way: the `>=` → `==` mutation is the same length as the original and the restore
landed in the same second, so Python kept the **mutated bytecode** and a test failed after the restore. Clearing
`__pycache__` fixed it. Any later mutation check should clear it between runs.

## Group check (shown before use)
Computed from `data/kb/case_library.json` (`bench/case_groups.py` → `data/kb/case_groups.json`): connected components
of moving (tag, direction) Jaccard ≥ 0.5, FLAT and bands ignored. Stable for any threshold in (0.286, 0.5].

| group | members | how |
|---|---|---|
| T total heat loss | RCA-14, RCA-18 | computed (identical moving signature) |
| W water deficit | RCA-01, RCA-16 | computed (Jaccard 0.5: `drum_level DOWN`, `water_balance DEFICIT` shared) |
| ∅ invisible | RCA-09, RCA-10, RCA-15 | computed (all empty) |
| singletons | RCA-03, 04, 05, 07, 11, 13 | computed |
| held-out membership | 06, 08 → T; 12 → RCA-11's group; 17 → ∅; 02 unassigned | **cited** from `reports/stage5_case_library.md` item 2, labelled "CITED, not computed" |

This does **not** literally reproduce the four Stage 5 clusters, because RCA-06, 08, 12, 17 are deliberately absent from
the library and `holdout.json` has no signatures for them, and CBD-open is an episode, not a case. You chose
"computed library groups plus a cited held-out block". Only RCA-06 is ever a scoring truth.

## Direction checks
| claim | expected | measured | |
|---|---|---|---|
| flat bed vs RCA-01's `bed DOWN MED` contradiction | no charge | `contradicts == []`; ep_A01 ticks 56 and 83 replayed: no charge | OK |
| bed DOWN MED | charged, log-odds lower than flat | charged; lower | OK |
| bed DOWN FAST (Step B) | charged (falling faster is stronger evidence against) | charged | OK |
| bed DOWN SLOW | not charged | not charged | OK |
| bed UP FAST | not charged (wrong direction) | not charged | OK |
| FLAT support smaller than movement support | 0.35 × | ratio 0.350 (pytest approx) | OK |
| missing FLAT expectation costs less than a missing movement one | yes | yes | OK |
| hypothesis not retrieved for N ticks | retired exactly at tick N, one event | live at N-1, retired at N, one HYP_RETIRED event | OK |
| retired hypothesis retrieved again | revived, counter reset | yes | OK |

These are all unit-level and on one episode replay. Nothing here depends on not-yet-rewritten code.

## Constants introduced
| symbol | value | provenance | range | affects |
|---|---|---|---|---|
| `agent.max_tokens` | 256 | **user decision**, Phase 0a (was 384 default, 256 verifier fallback) | plan targets 60/30/50/120 later | decode budget on gemini/litert; mock ignores it |
| `agent.belief.retire_after_ticks` | 20 | **DERIVED**: 10-min signature slope window (`orchestrator._slopes`) ÷ 30 s tick | ASSUMED [10, 120]: 5-min balance window ×2 … 2× the 60-min sensor window | how long a stale look-alike stays ranked. **Not tuned on the 30 episodes** |
| group threshold | 0.5 | "at least half the moving pairs shared"; result stable on (0.286, 0.5] | stable interval recorded in `case_groups.json` | which cases count as look-alikes |
| `LOW_CONF` | 0.5 | **user-set** ("at or below 0.5") | n/a | held-out `low_conf_rate` only |
| `BAND_RANK` | SLOW 1 < MED 2 < FAST 3 | order of `l1_symbolize.BANDS` | n/a | Step B contradiction rule |

## Numbers that changed
Baseline column = the state after the metrics commit (so the new belief metrics have a "before"). Legacy columns are
identical to `single_v1_summary.json`.

| metric | base | A1 | A2 | B | +retire |
|---|---|---|---|---|---|
| Q1 macro-F1 | 0.743 | 0.743 | 0.743 | 0.743 | 0.743 |
| Q2 top-1 (legacy, all 17) | 0.334 | 0.334 | 0.334 | 0.348 | 0.348 |
| Q2 top-3 (legacy, all 17) | 0.507 | 0.520 | 0.523 | 0.494 | 0.491 |
| Q3 faithfulness | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| Q4 precision | 0.380 | 0.380 | 0.380 | 0.377 | 0.377 |
| Q4 recall | 0.926 | 0.926 | 0.926 | 0.926 | 0.926 |
| Q5 FP/h | 0.91 | 0.91 | 0.91 | 0.91 | 0.91 |
| Q6 lead time (min, mean of 6) | 31.5 | 31.5 | 31.5 | 30.6 | 30.6 |
| S4 LLM invocation | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 |
| S7 deadline miss | 0 | 0 | 0 | 0 | 0 |
| **library episodes (13)** | | | | | |
| top-1 | 0.436 | 0.436 | 0.436 | 0.455 | 0.455 |
| top-3 | 0.663 | 0.680 | 0.684 | 0.646 | 0.642 |
| group top-1 | 0.547 | 0.547 | 0.547 | 0.566 | 0.566 |
| sep_named | 0.500 | 0.503 | 0.503 | 0.511 | 0.511 |
| belief top-1 | 0.012 | 0.429 | 0.515 | 0.480 | 0.443 |
| belief top-1, tie-fair | 0.013 | 0.264 | 0.438 | 0.420 | 0.385 |
| belief top-3 | 0.031 | 0.630 | 0.654 | 0.604 | 0.572 |
| belief group | 0.028 | 0.444 | 0.574 | 0.516 | 0.467 |
| belief top-of-list tie rate | 0.296 | 0.494 | 0.283 | 0.227 | 0.178 |
| **held-out episodes (4, all RCA-06)** | | | | | |
| group top-1 | 0.487 | 0.487 | 0.487 | 0.470 | 0.470 |
| belief group | 0.000 | 0.620 | 0.545 | 0.652 | 0.617 |
| low-confidence rate (rank-1 conf ≤ 0.5) | 0.912 | 0.189 | 0.225 | 0.240 | 0.222 |

Held-out top-1, top-3, sep_named and belief top-1/top-3 are **not applicable** and are `null`, never averaged as zeros.
The legacy `Q2_top1/top3` still include the four held-out episodes as structural zeros (Session 0 definition) so the
baseline stays comparable. Held-out cases **with** an episode: RCA-06. **Without**: RCA-02, 08, 12, 17.
Family E has no scored episodes (all three map to no case), so it shows n=0.

### Per family, before (base) → after (final)
| family | metric | before | after |
|---|---|---|---|
| A lib (n=5) | top-1 / top-3 | 0.223 / 0.451 | 0.220 / 0.438 |
| | group / sep | 0.510 / 0.389 | 0.510 / 0.367 |
| | belief top-1 / tie-fair / group | 0.030 / 0.033 / 0.073 | 0.181 / 0.142 / 0.244 |
| B lib (n=4) | top-1 / top-3 | 0.569 / 0.889 | 0.647 / 0.889 |
| | group / sep | 0.569 / 0.569 | 0.647 / 0.647 |
| | belief top-1 / tie-fair / group | 0.000 / 0.000 / 0.000 | 0.586 / 0.531 / 0.586 |
| C lib (n=2: C02, C04 → RCA-14) | top-1 / top-3 | 0.317 / 0.535 | 0.287 / 0.380 |
| | group / sep | 0.317 / 0.317 | 0.287 / 0.287 |
| | belief top-1 / tie-fair / group | 0.000 / 0.000 / 0.000 | 0.339 / 0.169 / 0.339 |
| C held-out (n=4) | group | 0.487 | 0.470 |
| | belief group / low-conf rate | 0.000 / 0.912 | 0.617 / 0.222 |
| D lib (n=2) | top-1 / top-3 | 0.825 / 0.871 | 0.822 / 0.921 |
| | group / sep | 0.825 / 0.825 | 0.822 / 0.822 |
| | belief top-1 / tie-fair / group | 0.000 / 0.000 / 0.000 | 0.914 / 0.914 / 0.914 |
| E | n=0 | no scored episodes | |

### Per episode (scored episodes only; "→" marks a change; model-order metrics, then belief)
| episode | truth | top-1 | top-3 | group | sep | belief top-1 (tie-fair) | belief group | low-conf |
|---|---|---|---|---|---|---|---|---|
| A01 fcv_seize | RCA-01 | 0.208 → 0.170 | 0.358 → 0.292 | 0.491 | 0.349 → 0.283 | 0.009 → 0.226 | 0.000 → 0.226 | n/a |
| A02 fcv_seize_fast | RCA-01 | 0.125 → 0.094 | 0.359 → 0.297 | 0.516 | 0.344 → 0.281 | 0.000 | 0.094 → 0.250 | n/a |
| A03 bfp_suction | RCA-16 | 0.396 → 0.451 | 0.648 | 0.758 | 0.626 | 0.000 | 0.033 → 0.000 | n/a |
| A05 fcv_caught | RCA-01 | 0.161 | 0.264 → 0.299 | 0.172 | 0.172 → 0.161 | 0.000 → 0.351 | 0.034 → 0.345 | n/a |
| A06 fcv_seize_repeat | RCA-01 | 0.226 | 0.624 → 0.656 | 0.613 | 0.452 → 0.484 | 0.156 → 0.134 | 0.204 → 0.398 | n/a |
| B01 tube_leak | RCA-11 | 0.680 → 0.742 | 0.953 | 0.680 → 0.742 | 0.680 → 0.742 | 0.000 → 0.353 | 0.000 → 0.570 | n/a |
| B02 tube_leak_fast | RCA-11 | 0.608 → 0.725 | 1.000 | 0.608 → 0.725 | 0.608 → 0.725 | 0.000 → 0.863 | 0.000 → 0.863 | n/a |
| B03 tube_leak_slow | RCA-11 | 0.402 | 0.603 | 0.402 | 0.402 | 0.000 → 0.285 | 0.000 → 0.285 | n/a |
| B05 tube_leak_repeat | RCA-11 | 0.586 → 0.719 | 1.000 | 0.586 → 0.719 | 0.586 → 0.719 | 0.000 → 0.625 | 0.000 → 0.625 | n/a |
| C01 wet_coal | RCA-06 | n/a | n/a | 0.674 → 0.605 | n/a | n/a | 0.000 → 0.860 | 0.884 → 0.279 |
| C02 feeder_trip | RCA-14 | 0.316 → 0.289 | 0.500 → 0.395 | 0.316 → 0.289 | 0.316 → 0.289 | 0.000 → 0.164 | 0.000 → 0.329 | n/a |
| C03 wet_coal_mild | RCA-06 | n/a | n/a | 0.382 | n/a | n/a | 0.000 → 0.800 | 0.764 → 0.418 |
| C04 feeder_trip_caught | RCA-14 | 0.317 → 0.286 | 0.571 → 0.365 | 0.317 → 0.286 | 0.317 → 0.286 | 0.000 → 0.175 | 0.000 → 0.349 | n/a |
| C05 low_cv_coal | RCA-06 | n/a | n/a | 0.179 | n/a | n/a | 0.000 → 0.179 | 1.000 → 0.162 |
| C06 wet_coal_repeat | RCA-06 | n/a | n/a | 0.714 | n/a | n/a | 0.000 → 0.629 | 1.000 → 0.029 |
| D01 high_cv_coal | RCA-07 | 0.774 → 0.769 | 0.860 → 0.851 | 0.774 → 0.769 | 0.774 → 0.769 | 0.000 → 0.828 | 0.000 → 0.828 | n/a |
| D03 high_cv_severe | RCA-07 | 0.875 | 0.883 → 0.992 | 0.875 | 0.875 | 0.000 → 1.000 | 0.000 → 1.000 | n/a |

Every scored episode changed in at least one column. The 13 unscored episodes (7 not-applicable faults + 6 normal) are
unchanged in Q1 and Q5. Outside T2, only two per-episode values moved anywhere: **A02 lead time −0.4 → −5.9 min**
(first correct call tick 1410 s → 1740 s) and **C01 action precision 0.429 → 0.375** (an extra ACT-041 proposed).

### Why each metric moved
| move | cause | how verified |
|---|---|---|
| Retrieval dump identical through config, metrics, A1, A2, retirement (2164 rows each) | none of them touch retrieval | byte-equal dump |
| **A1/A2: belief metrics 0.01 → 0.44–0.51** | belief now sees full triples (bug 6), so evidence for a case is no longer scored as contradiction. A2 stops unscaled FLAT triples saturating the log-odds clamp: top-of-belief tie rate 0.494 → 0.283 and tie-fair belief top-1 0.264 → 0.438 | per-step reruns; tie analysis |
| **A1: legacy Q2_top3 0.507 → 0.520 although I predicted no model-order change** | my prediction was wrong. `_merge` keeps the model's ≤3 retrieved cases first and fills any remaining top-3 slots with belief-"carried" hypotheses. On 160 ticks retrieval returned only 1–2 cases, so belief reached the top-3. Top-1 never depends on belief | all 160 changed-top-3 ticks had 1–2 retrieved cases and a carried entry in the top 3 |
| **B: B-family top-1 0.569 → 0.647; C-family top-3 0.535 → 0.380; A02 lead time worse** | the rule fires 3,077 new case-tick contradictions, 78% on `bed_temp_avg` and 16% on `drum_pressure`, each a slope reaching a higher band than the listed one. They hit **true cases too**: RCA-01 on 68 (62 bed, 6 water balance; A episodes) and RCA-14 on 86 (56 bed, 30 pressure; C02/C04: bed UP FAST against RCA-14's `bed UP MED` contradiction), RCA-07 on 14. RCA-11 gains (rank-1 gained 35 ticks) when RCA-01/16 are knocked out | newly-contradicted ticks enumerated per (case, listed triple, observed band, truth) |
| **retirement: family A belief top-1 0.272 → 0.181, A01 0.519 → 0.226** | 154 retirements over 30 episodes, 98 revived later, **5 of the true case** (A01 ×2, A02, A05, C04). Step B already drops RCA-01 from retrieval at bed-FAST ticks, then retirement removes its accumulated belief during the gap | HYP_RETIRED events enumerated per episode and compared with the truth |
| legacy Q2_top3 0.494 → 0.491 at retirement | same carried-slot path as A1 | not separately traced; same mechanism, small move |
| Q6 31.5 → 30.6, Q4 precision 0.380 → 0.377 | step B (A02 first-correct call later; C01 gains one action) | per-episode diff |

## Disagreements recorded, not resolved
- **Groups vs Stage 5.** The computed groups do not literally reproduce the four Stage 5 clusters (see group check).
  Both are recorded; the held-out membership is cited, and RCA-02 is left unassigned because Stage 5 itself calls its
  cluster only partial.
- **CLAUDE.md "tick 76".** On the current episodes RCA-01 is not retrieved at tick 76, is already at −4.0, and the bed
  is DOWN MED (its real contradicting triple). The flat-bed tag-only charges are at ticks 56 and 83. CLAUDE.md and
  GUIDE.md are updated; the GUIDE table was **recomputed** with the old rule (RCA-01 −1.00 net, −0.90 contradiction
  term) instead of renaming the tick. The rest of GUIDE.md's bug-6 section still reads as though the bug is open.
- **My prediction** that A1/A2/retirement would leave model-order Q2 untouched was wrong (see above). Explained and
  verified; Q2 top-1 is indeed never moved by A1, A2 or retirement.
- **Expected-evidence exact matching has the same problem in the other direction** (asked for, not changed). Of 26,936
  expected triples charged "absent", **3,688 (13.7%)** were same tag and direction at a different band: 2,399 "observed
  slower" and 655 "observed faster" on non-truth cases, and **634 on the true case** (343 slower, 291 faster).
  Largest truth-case runs: D03/RCA-07 `drum_pressure UP` expect SLOW saw MED (86 ticks, 39–137); B05/RCA-11
  `feed_water_flow UP` expect MED saw SLOW (57 ticks, 51–173); B03/RCA-11 same (52 ticks, 87–284); D03/RCA-07
  `ms_temperature UP` expect MED saw FAST (47, 48–120); B05/RCA-11 `bed_temp_avg DOWN` expect MED saw FAST (43, 52–142).
  Each costs the true case −0.2 (×weight) per tick. Not changed in this session.

## Blocked / needs a decision
No stop rule was hit. These are open questions, with options, not actions already taken:
1. **Keep Step B?** It is its own commit (`d822130`, `git revert` undoes it). It improves B-family top-1 and group
   (+0.078) and Q2 top-1 slightly, but lowers C-family top-3 (0.551 → 0.380 at this step), costs A02 5.5 minutes of lead time, and the new
   contradictions hit the true case 168 times (case-tick-trigger counts, not distinct ticks). The likely driver is the known synthetic-noise gap (bed slope reaching
   FAST by wander), but I have **not verified** that: it would need the real-noise calibration, which is out of scope.
   Options: keep; revert; or keep only for non-bed tags.
2. **Keep retirement at N=20?** Mixed on belief metrics, and it interacts with Step B. N was derived, not tuned, and I did
   not sweep it on the 30 episodes (tuning prohibition). Options: keep; choose a different derivation (e.g. N from the
   case's own signature window); or revert.
3. **`sep_named` definition.** Implemented as you chose (group right AND true case in top-3 with a non-empty
   discriminator). The mock copies `discriminating_evidence` from each retrieved case, so on mock it adds little over top-1
   (0.511 vs 0.455). It will mean more with a model that writes `sep`.
4. **Family E has no scored episode.** Its three episodes map to no case, so the per-family E row is empty by
   construction.

## What I could not verify
- **Anything beyond mock.** No cloud or board backend was run, so the real effect of the 256 answer cap (Gemini
  enforces `maxOutputTokens`, so a 3-hypothesis JSON may truncate; LiteRT cannot enforce it, `llm_backend.py:403`) is
  unverified. Phase 0's "mock and NPU, lockstep" check is not complete; the NPU half is Session 2.
- **Whether the belief improvements survive a reasoning backend.** Mock re-ranks retrieval, so belief changes only
  reach the model-order list via carried slots. `belief_*` is the right lens on mock, but a real model's reply merges
  differently (this is the same caveat as in the earlier `_merge` fix).
- **Tie-order credit.** Plain `belief_top1` partly rewards insertion (retrieval) order under ties; the tie-fair column
  is the safer number (e.g. 0.264 vs 0.429 at A1). It is an additive diagnostic I introduced, not one of the metrics
  you specified.
- **Held-out membership** of RCA-06/08/12/17 rests on the Stage 5 narrative, not on computed signatures.
- **Retirement's `retire_after_ticks`** sensitivity is unexplored on purpose.
- **GUIDE.md** tail of the bug-6 section (still says the bug is open) was left as is.
- **Held-out group credit for C03/C05** (0.382 / 0.179) is low; I did not investigate why.
- `pytest` was not installed in the venv; I installed it (dev-only, added as a comment-delimited line in
  `requirements.txt`). The three `bench/test_*.py` files are scripts and were run as such, not collected by pytest.
