# Phase 0a, Session 1b: measurement hygiene: report

All numbers are **mock backend**. They measure the deterministic and retrieval layers only. They are **not agent
results**; the mock re-ranks retrieved cases and does no reasoning. Energy is `null` (no device).

## Status
PARTIAL. Step 1 (dev set) done. Step 2 (bed slope) is a finding only. Step 3 (band calibration) was run and **not adopted**
(human decision, below). Step 4 (belief saturation on the old edges) is measured. Step 5 (fix (c), display-only) is specified here and being built. Not yet done: the reporting-set run,
`results/baselines/single_v3_summary.json`, the C04 advisor entry, phase-reviewer.

Commits (main, none pushed): `f2f9f5d` dev set. `232e08c` calibration + sanity scripts. Branch `exp/band-edges-p85`
(`dd5d41a`): the p85 edges, preserved, not for main.

## Verification
| step | result |
|---|---|
| ran the module | `episode_build --set dev`: 36/36 pass the gate on the first seed, no retries. `band_calibration`, `band_sanity` and three mock dev runs executed (outputs in the session log) |
| self-tests | pytest 46 passed / 0 failed; `bench/test_checks.py` 20/0 (21/0 on the experiment branch), `test_envelope_logging.py` 16/0, `test_orchestrator.py` 22/0 |
| independent re-derivation | dev FLAT fraction per tag at the p85 edges: script (`Orchestrator._slopes`) vs numpy `polyfit` on the raw CSVs: drum_level 1.000/1.000, feed 0.856/0.856, steam 0.862/0.862, pressure 0.861/0.861, bed 0.850/0.850, ms 0.858/0.858; relative difference 0%. Also dev Q5: evaluator 0.98 vs mean of per-episode rates recomputed from the runs file 0.98 (0%); the pooled rate is 0.87 |
| mutation check | dev seed offset 1000 → 0: caught by `test_dev_seeds_disjoint_from_reporting_and_calibration` and `test_every_fault_has_a_twin_with_identical_scenario`. `max` → `min` in `calibrate()`: caught by `test_raises_deadband_to_p85_and_keeps_multiples` and `test_never_lowers_a_deadband_that_already_meets_the_criterion`. `__pycache__` cleared between runs |

## Decisions taken
1. **[human] Item 2 skipped:** calibrate the raw bed slope; no load normalisation.
2. **[human] Deadband rule:** `max(current, p85)`, not p85 for every tag.
3. **[human] Family E** is reported, not a stop.
4. **[human] Band edges not adopted (option 1).** The keep rule, fixed before results, fails by a wide margin: dev
   tie-fair belief top-1 0.375 → 0.098, belief group 0.502 → 0.067, retrieval top-1 0.434 → 0.193, the same pattern as
   Stage 6. The edges are preserved on `exp/band-edges-p85`; `main` keeps the Stage-5 edges.
5. Gate-retry policy for dev (seed +10000, +20000, never touch severities) was prepared and **not needed**.
6. The bed "SLOW" test in `bench/test_checks.py` used 0.08 °C/min, which is FLAT under the new bed deadband (0.74). Its
   input moved to 1.0 °C/min **on the experiment branch only**; main is unchanged. This was an expected consequence of
   the edges, not a transcription error.

## Direction checks
None: no physical response was added or changed. Band edges are a descriptor vocabulary, not a plant model.

## Constants introduced
| symbol | value | provenance | range | affects |
|---|---|---|---|---|
| `DEV_SEED_OFFSET` | 1000 | design choice: keeps dev seeds off every seed already used (0–3, 100–604, 700–711, 900–911, 950–969) | any offset that keeps the disjointness test passing | dev fault seeds |
| `DEV_NOFAULT_SEEDS` | 1100–1111 | same | same | the 12 extra no-fault episodes |
| `TARGET_FLAT` | 0.85 | **user-set** criterion, fixed before any result | n/a | `band_calibration.py` only |
| p85 band edges | see branch | **FITTED** to dev no-fault, method in the script | **not adopted** | nothing on main |

## Numbers that changed
`main`'s agent behaviour is unchanged by this session (no agent code or config edit survives). The reporting set at HEAD
reproduces `single_v2_summary.json` with no differing keys.

### Dev set: before and with the p85 edges (dev, mock; the edges are NOT in `main`)
| metric | dev, main edges | dev, p85 edges | delta |
|---|---|---|---|
| Q1 macro-F1 | 0.782 | 0.782 | 0 |
| Q2 top-1 / top-3 (legacy) | 0.332 / 0.453 | 0.148 / 0.238 | −0.184 / −0.215 |
| Q3 / Q5 / S7 | 1.0 / 0.98 / 0 | 1.0 / 0.98 / 0 | 0 |
| Q4 precision / recall | 0.357 / 0.882 | 0.460 / 0.853 | +0.103 / −0.029 |
| Q6 lead time (min) | 32.4 | 33.9 | +1.5 |
| library top-1 / top-3 | 0.434 / 0.593 | 0.193 / 0.312 | −0.241 / −0.281 |
| library group top-1 | 0.489 | 0.229 | −0.260 |
| library belief top-1 tie-fair | 0.375 | 0.098 | −0.277 |
| library belief group / tie-fair | 0.502 / 0.477 | 0.067 / 0.140 | −0.435 / −0.337 |
| library belief tie rate | 0.270 | 0.730 | +0.460 |
| held-out belief group / tie-fair | 0.709 / 0.700 | 0.000 / 0.000 | −0.709 / −0.700 |
| held-out low-conf rate | 0.245 | 0.340 | +0.095 |

Reference, reporting set (v2): library tie-fair belief top-1 0.438, belief group 0.574, held-out belief group 0.545. Dev
is lower on both library belief metrics. That fits the earlier selection on the reporting set, but I have not tested that
explanation.

### Why the matcher collapsed: rank-1 case, post-onset fault ticks (1,968 ticks, from the existing run logs, no reruns)
| case | belief rank-1, main → p85 | retrieval/model-order rank-1, main → p85 |
|---|---|---|
| RCA-15 (∅ group) | 11.9% → **59.4%** | 9.7% → **57.2%** |
| RCA-09 (∅ group) | 4.7% → 10.6% | 2.4% → 4.3% |
| RCA-10 (∅ group) | 0.5% → 0.1% | not in the top list |
| RCA-13 | 9.8% → 20.6% | 6.9% → 15.5% |
| RCA-07 | 28.3% → 0.0% | 33.8% → 5.4% |
| RCA-11 | 16.3% → 0.8% | 24.9% → 3.7% |
| RCA-14 | 12.5% → 0.0% | 9.5% → 3.1% |

The ∅ trio (RCA-09/10/15, empty signatures) goes from 17.1% to 70.0% of belief rank-1 ticks: with most tags reading FLAT,
FLAT-heavy cases win. On the normal-episode ticks that have hypotheses (10), rank-1 moves from RCA-07 to RCA-13. RCA-13's
signature has **5 FLAT triples out of 6** (the only movement is `bed_temp_avg UP SLOW`), so it is FLAT-heavy like the
∅ cases; that is consistent with the takeover, but I have not tested it beyond the count.

## Findings
### Item 2: bed slope history
The signature bed slope has been the **raw** 10-min slope since the first commit `e7c756d` (2026-08-31). Load
normalisation in the signature existed only as uncommitted Stage 6 scaffolding (`018fbd8` → `aa86567`, recorded in
`888b01a`); it was reverted because mock Q2 top-1 fell 0.334 → 0.173 and because a symmetric normalisation flips family
C's bed sign (C02 raw −0.25 → +0.04 °C/min, DERIVATIONS §9.1). No design document (both plan PDFs, GUIDE §3.5) specifies a
load-normalised signature bed; only the L1 drift/PATTERN checks and the multi-agent drift watcher use a load-corrected bed.
So "restore" was a mismatch with the instruction, not a regression; no code changed.

### Band calibration (step 3): tag-level separation vs matcher collapse
Criterion: deadband = max(previous, p85 of healthy 10-min |slope|), 2 s.f. rounded up; multiples kept; 12 dev no-fault
episodes, 1,260 windows. Pooled FLAT is 0.85–0.86 per tag (per-episode 0.52–1.00). Share of post-onset ticks on which the
family's headline tag reads as moving (healthy ≈ 0.15 under the new edges; 0.76–0.95 under the old):

| family | headline tag | p85 edges | Stage-5 edges | reading |
|---|---|---|---|---|
| A | drum_level | 0.52 | 0.52 | unchanged (already 100% FLAT healthy) |
| B | feed_water_flow (banded proxy) | 0.11 | 0.80 | see below |
| C | drum_pressure | 0.68 | 0.85 | separates clearly |
| D | bed_temp_avg | 0.53 | 0.97 | separates clearly |
| E | bed_temp_avg | 0.07 | 0.93 | reported only |

- **Tag level.** The new edges separate C (0.68) and D (0.53) from healthy (≈0.15) clearly, where the old edges separated
  almost nothing (healthy read as moving 0.76–0.95 of the time). Yet the matcher collapses (table above). That points at the
  uncalibrated case-signature band labels (Stage 6 "Unresolved 1"), not at the edges themselves: the case labels were read
  from PDF prose and are reachable only by the noisy, dense signature the old edges produce.
- **Family B.** The banded proxy `feed_water_flow` does not separate the fault under either set of edges: 0.80 vs a healthy
  ~0.8 under the old edges (it moves with healthy wander), and 0.11 vs 0.15 under the new ones. B's real Stage 6 headline,
  `water_balance`, comes from BALANCE facts and does not depend on `checks.bands`; it is present on 0.67 of post-onset
  ticks (B01/B02/B05 0.86, B04 0.92, B03 slow leak 0.34). The stop condition triggered for the signature proxy only.
- **Family E.** 0.07 under the new edges. Reported only; consistent with the Stage 4 finding that E needs a cumulative
  drift detector.
- `bench/band_sanity.py` reproduces this table (`--bands-yaml` for the branch config). Its moving/FLAT verdict is only
  meaningful for edges that meet the 85%-FLAT criterion.

### Glossary
- **Q5** (`Q5_fp_per_hour`) is the **mean of per-episode rates** (0.98 on dev). The pooled rate (all FP ticks over all
  hours) is 0.87. Both are correct; the difference is weighting by episode length.

## Step 4: belief saturation on dev, main (Stage-5) edges
Tool: `bench/belief_saturation.py` (read-only). Validated first on the reporting-set runs: it reproduces the Phase 0a
Check 1 figures (library 729 ticks at the clamp, 388 ties, 247 ties at the clamp = 63.7%, mean shown conf 0.619, 45.6%
at >= 0.9; held-out 203 ties, 168 at the clamp, 40.4% confident-and-wrong; median 0.728 vs 0.729, rounding). Test:
`tests/test_belief_saturation.py`; mutation `>=` -> `>` on the clamp test was caught by both of its tests.

| dev, mock, main edges | library (1,327 ticks) | held-out (273) | no-fault (10, 5 episodes) |
|---|---|---|---|
| belief rank-1 at the +4.0 clamp | 621 (46.8%) | 160 (58.6%) | 0 |
| top-of-belief ties | 301 (22.7%) | 229 (83.9%) | 1 |
| ...ties at the clamp, share of ties | 215 (71.4%) | 155 (67.7%) | 0 |
| shown rank-1 conf: mean / median | 0.685 / 0.885 | 0.765 / 0.980 | 0.775 / 0.711 |
| shown conf >= 0.9 | 48.9% | 60.8% | 20% |
| confident (>0.5) and wrong group | 233 (17.6%) | 109 (39.9%) | n/a |
| shown conf deciles 0.0-1.0 | 0, 208, 142, 46, 43, 45, 51, 58, 85, **649** | 0, 21, 21, 12, 7, 16, 7, 8, 15, **166** | 0,0,0,0,0,1,2,3,2,2 |

Additional, from the same logs. Of the ticks that sit AT the clamp (denominator: library 621, held-out 160; **not** all
scored ticks), **29.0% (180 of 621) of library and 49.4% (79 of 160) of held-out have a rank-1 case in the wrong group**.
As a share of all scored ticks (1,327 and 273) that is 13.6% and 28.9%, which is why it is below the confident-and-wrong
rows above (17.6% and 39.9%): that row counts any shown conf > 0.5, not only the clamp. The clamp is reached a median of 7 ticks after the first post-onset hypothesis
(library, 9 of 13 episodes reach it; min 2, max 39) and 7.5 ticks on held-out (4 of 4). The largest per-tick step for a
steady rank-1 is +1.20 (library) and +0.77 (held-out).

**N03-type fast climb.** `dev_N03_normal` itself is quiet (no hypotheses at all). The same climb shows on `dev_N05_normal`:
RCA-07 rank-1 with log-odds +0.90, +2.00, +3.09, +4.00 over ticks 11-14 (shown conf 0.711, 0.881, 0.957, 0.982), i.e. the
clamp in four ticks on a healthy plant; `dev_N09_normal` (the other N03-spec copy) shows RCA-07 at +0.90, +1.81 (0.711,
0.859) before its hypotheses disappear. No-fault coverage is thin: 10 ticks in 5 of 12 episodes, so these rows are
anecdotes, not rates. The reporting `ep_N03` table will come only from the end-of-session reporting run.

### Overconfidence fixes proposed (belief is NOT changed; the human chooses)
Common to every option, **fixed now, before any measurement of the fix**: measured on dev, mock, against the current
`main` as the preceding kept state. Gate G: library tie-fair belief top-1 and belief group each drop by no more than 0.01
(standing keep rule); Q1, Q3, Q5, S7 unchanged; legacy Q2 top-1 does not drop by more than 0.01; held-out reported, not
gating (one held-out case). Calibration metric defined now: **ECE** over 5 equal-width bins of shown rank-1 confidence
against whether the shown rank-1 case lies in the true case's group, on library + held-out scored ticks. Its baseline is
measured on the unchanged tree at the start of the chosen fix, before any code change.

| | what it does | constants | predicted effect (not measured) | keep rule, in addition to G |
|---|---|---|---|---|
| **(a) Decay** | multiply log-odds by (1 - lambda) each tick before the update | lambda from a half-life; DERIVED start: the 10-min signature window = 20 ticks, lambda = 0.034; ASSUMED range of half-life [10, 120] ticks (same bounds as the retirement setting) | **Weak.** A steady +1.2/tick step against a 3.4% decay still reaches +4.0 in about the same 4-5 ticks, so saturation under continuing evidence is untouched; it only shortens how long a stale hypothesis lingers. Retirement had the same character and failed the keep rule (library tie-fair -0.025), and a decay strong enough to bite would need a tuned value | library share of ticks at the clamp falls by at least 0.10 (0.468 to <= 0.368) AND confident-and-wrong share does not rise. I expect it to fail both |
| **(b) Tie-break by this tick's retrieval score** | among exactly tied log-odds, order by the current tick's retrieval score | none | Ties stop being arbitrary insertion order: library tie share (0.227) should fall toward the cases that are genuinely identical (RCA-09/10/15, RCA-14/18). **Does not touch shown confidence**: tied hypotheses still show 0.982. The tie-fair metric assumes ties are uniform, so it will not register the gain; plain belief top-1 will | plain library belief top-1 does not drop AND exact-tie share (equal log-odds and equal score) falls to at most half of 0.227 AND shown confidence values bit-identical. Fixes ties only, not overconfidence |
| **(c) Confidence from the rank-1 vs rank-2 margin** | shown conf = sigmoid(log-odds rank-1 - log-odds rank-2); sigmoid(log-odds) if only one live hypothesis | none (no free constant: it is the two-way odds ratio) | **Strongest on the measured cause.** A tie (including a clamp-vs-clamp tie) shows exactly 0.5, so the 83.9% tied held-out ticks stop being "confident" (conf > 0.5) and its confident-and-wrong share (0.399) should collapse; library should fall by the part that sits on ties (magnitude unverified; untied clamp ticks with a wide margin stay confident, e.g. 4.0 vs 1.0 shows 0.95). Belief ranking is unchanged, so belief metrics should be bit-identical. **Side effect to flag:** the verifier fires inside conf [0.35, 0.75], so ties at 0.5 enter that band and S4 (LLM invocation rate) will rise on mock | hypothesis order and belief metrics bit-identical (display only, applied after sorting); ECE strictly lower; confident-and-wrong share lower on library AND held-out; the S4 change reported with its cause (needs your OK, it changes a cost metric) |

My recommendation, for you to overrule: (c) first (lowest risk, no constants, addresses the measured shared cause), then
(b) as a separate step for the tie arbitrariness; (a) last or not at all.

## Step 5: fix (c), shown confidence from the margin: specification (written before any code)
Human choice: **(c) only, strictly display-only; the verifier trigger and every decision path keep the existing value.**

### 1. Every consumer of confidence (grep of `fieldmind/` and `bench/`)
| consumer | reads | kind | after (c) |
|---|---|---|---|
| `world_model.update_hypotheses`: `h.confidence = sigmoid(log_odds)` | log-odds | producer | unchanged |
| `world_model` retire floor: `h.confidence < RETIRE_BELOW (0.08)` | decision value | decision (retirement) | unchanged |
| `world_model.rank_hypotheses`: sort by confidence | decision value | decision (order) | unchanged |
| `world_model.belief_ranking` (telemetry): carries `confidence` | decision value | telemetry | unchanged |
| `orchestrator` claims: `"confidence": h.confidence` into `_merge` | decision value | decision (deterministic wins confidence) | unchanged |
| `orchestrator` `top_conf` -> `Verifier.should_run` band `[0.35, 0.75]` | decision value | **decision (S4)** | **unchanged** |
| `Verifier.run` prompt `conf={h['confidence']}`; `Verifier.apply` caps (<= 0.35) or revises `h["confidence"]` | decision value | decision (model input and output) | unchanged |
| `orchestrator._wm_summary` ("current hypotheses: cause(0.98)") into the Diagnostician prompt | decision value | decision (model input) | unchanged |
| `l4_diagnose` validation of the model's own `confidence` number | the model's number | validation | n/a |
| `l6_gate.approve` (actions, escalation) | none (escalation is from STATE; verified by grep: no confidence) | decision | n/a |
| `l7_memory.promote` | none | n/a | n/a |
| `Assessment.confidence` | was `top_conf` (a pre-verifier copy of the decision value); no reader in the code base | display | **switches to the shown value of rank 1** |
| `asmt.hypotheses[i]["confidence"]` | decision value (also what the evaluator read) | output | **unchanged; new field `confidence_shown` added beside it** |
| `bench/evaluator.py` `low_conf_rate` (<= 0.5) | `hyps[0]["confidence"]` | reporting | switches to `confidence_shown` (falls back to `confidence` on old runs); the old definition is kept as `low_conf_rate_decision` |
| `bench/belief_saturation.py` | confidence | reporting | reads `confidence_shown` if present; `--decision-conf` forces the old value |

Rule: only the **display** (`confidence_shown`, `Assessment.confidence`) and **reporting** consumers switch. The
`confidence_shown` field is computed in the orchestrator **after** the verifier and the gate, from the final hypothesis list,
and nothing reads it afterwards, so no decision can depend on it.

### 2. Exact formula
For each hypothesis `i` in the final shown list, with decision confidence `c_i` (its final value, after any verifier cap) and
the live belief ranking `B = wm.hypotheses not retired` (log-odds `l_j`):

- if `i` has no belief entry (a model-only idea): `shown_i = c_i`.
- otherwise let `l_i` be its log-odds, and `r_i = max(l_j for j in B, j != i)`; **if `i` is the only live hypothesis, `r_i = 0`**.
- `shown_i = min(c_i, sigmoid(l_i - r_i))`, rounded to 3 decimals like `confidence`.

Consequences, each of which gets a unit test:
- **No rank-2 hypothesis** (single live hypothesis): `sigmoid(l_i - 0) = sigmoid(l_i) = c_i`, so `shown = c`. The single-hypothesis
  climb is unchanged by construction.
- **Rank-1 ahead by margin d > 0** (rival `l_2 >= 0`): `shown = min(c_1, sigmoid(d))`; e.g. +4.0 vs +1.0 shows 0.953 (not 0.982).
  If the rival is negative, `sigmoid(l_1 - l_2) >= sigmoid(l_1) = c_1`, so `shown = c_1` (the margin never raises confidence).
- **Non-leaders** have `l_i <= r_i`, so `shown <= 0.5`.
- **Two-way tie** (equal log-odds): each shows 0.5 if its `c_i >= 0.5`, else its own `c_i` (the `min`).
- **k-way tie, k >= 3** (e.g. the empty-signature trio RCA-09/10/15 at the +4.0 clamp): every tied hypothesis has an equal rival,
  so each shows **0.5, not 1/3**. The formula is a pairwise margin, not a probability over the tied set; reading ties as
  uniform (1/k) would need a softmax over all live hypotheses (the dropped option (d)). Recorded as a known simplification.
- **Both ranks at -4.0** (`l_1 = l_2 = -4.0`, `c = 0.018`): the margin is 0, `sigmoid(0) = 0.5`, but the `min` keeps
  `shown = 0.018`. The `min` is a safeguard I added to the approved formula: without it a disbelieved hypothesis would show
  50%. It cannot occur among live hypotheses today (anything under confidence 0.08 is retired), and is handled anyway.
  **Decision taken (rule 6, conservative):** the margin can only lower the shown value, never raise it.

### 3. ECE definition and baseline (dev, current main, measured before any code change)
- Scored ticks: post-onset ticks with a non-empty hypothesis list (same as the saturation table). **Decided on library
  ticks**; held-out and the pooled figure are reported.
- 5 equal-width bins of the shown rank-1 confidence on [0, 1], the last closed at 1.0. `ECE = sum_b (n_b / N) * |mean conf_b -
  fraction correct_b|`.
- **Correct = the shown rank-1 case lies in the TRUE case's group** (`case_groups.json`). Group, not case: look-alike cases
  (RCA-14/18, RCA-09/10/15) cannot be told apart by any confidence, and the confident-and-wrong measure is group-level too.
  The case-level ECE is reported as a secondary diagnostic only.

| dev, current main (decision confidence) | library | held-out |
|---|---|---|
| ECE (group), **decided** | **0.1305** | 0.4167 |
| ECE (case), secondary | 0.1391 | 0.7647 (trivial: the held-out case is never in the library) |
| confident (> 0.5) and wrong group | **233 of 1,327 = 0.176** | 109 of 273 = 0.399 |
| low-confidence share (shown conf <= 0.5) | 0.335 | 0.260 |
| library+held-out pooled ECE (group / case) | 0.1679 / 0.2459 (1,600 ticks) | |

Library bins (conf bin: n, mean conf, group-correct): 0-0.2: 208, 0.155, 0.212; 0.2-0.4: 188, 0.266, 0.298; 0.4-0.6: 88,
0.493, 0.420; 0.6-0.8: 109, 0.709, 0.413; 0.8-1.0: 734, 0.961, 0.802. The top bin carries most of the error (0.961 vs 0.802).
A fresh dev run at current main reproduces the earlier "before" run exactly except wall-clock latency fields
(`tick_latency_ms`, envelope latencies, S1 p50/p95).

### 4. Keep/revert rule for (c): fixed now; decided on LIBRARY only
Keep (c) only if **all** hold on dev, mock, against current main:
1. **Belief metrics bit-identical**: every `belief_*` key (library, held-out, per family) and every per-episode `belief_*`.
2. **Decision values bit-identical**: in every assessment the `hypotheses` order, each `confidence`, `actions`, `escalate`,
   `state`, `triage`, `llm_invoked` and `belief_ranking` equal the current-main run (only `confidence_shown` is new and
   `Assessment.confidence` differs by design).
3. **Q1, Q2 (legacy top-1/top-3, library top-1/top-3/group/sep), Q3, Q4, Q5, Q6, S4, S7 unchanged** (exact; S1 latency excluded).
   `low_conf_rate` is exempt by design (see 5).
4. **Library ECE (group) < 0.1305 AND library confident-and-wrong-group share < 0.176** (both must fall, strictly).
5. **Reported, not used to decide:** held-out ECE, held-out confident-and-wrong share (**flagged if either gets worse**),
   `low_conf_rate` (held-out, evaluator) and the library low-confidence share. `low_conf_rate` is **expected to rise**,
   because ties at exactly 0.5 count as <= 0.5. Held-out is not gating: only RCA-06 has episodes (standing rule).
6. Unit tests for every formula case above and mutation checks pass; the whole suite is green.

### 5. Predictions, written before measuring
- **P1 (single-hypothesis climb):** (c) does not change it. `dev_N05` RCA-07 still shows ~0.711, 0.881, 0.957, 0.982 on
  ticks 11-14. The condition is exact: shown changes only if a live rival has log-odds **> 0** at that tick.
- **P2:** belief metrics, hypothesis order, decision confidences, S4 and every other Q/S key are bit-identical (by construction:
  nothing that decides reads the new field).
- **P3:** held-out confident-and-wrong falls sharply (83.9% of held-out ticks are ties, which now show <= 0.5).
- **P4 (library):** confident-and-wrong falls, but by **at most the tie share of 0.227** (a tie is the only thing that
  lowers a rank-1 to 0.5; wide-margin untied clamp ticks stay at ~0.95-0.98). I expect a modest ECE fall, **not** a collapse.
  It can in principle rise if the ticks moved into the 0.4-0.6 bin are right far less than half the time; the rule decides.
- **P5:** `low_conf_rate` (held-out) rises from 0.245, and the library low-confidence share from 0.335.

## Disagreements recorded, not resolved
- **Instruction vs history (item 2).** "Restore load normalisation" vs a signature that never had it. Resolved by your
  decision to skip, not by me.
- **Pooled vs per-episode FLAT.** The criterion is pooled. Per-episode FLAT at the p85 edges ranges 0.52–1.00 (load swings
  differ), so a single episode can read far more movement than 15%. Not investigated.
- **Dev below reporting** on library belief metrics (0.375 vs 0.438 tie-fair top-1; belief group 0.502 vs 0.574).
  **Unexplained (hypothesis: A2 was selected on the reporting set).** Not tested.

## Blocked / needs a decision
- None. Human choice made: (c) only, display-only, S4 must not move (see Step 5).

## Open list (added)
- **Case-signature band calibration, tested together with the edges as one unit.** Tag-level separation is good under the
  p85 edges and the matcher still collapses, so edges and case band labels must be judged together. It touches
  `data/kb/case_library.json`, so it needs a **pre-registered rule and advisor sign-off**. Not done in this session.

- **Overconfidence fix (a), per-tick log-odds decay: DROPPED** (human decision). Recorded: a decay mild enough to be
  derived (half-life = the 20-tick signature window) cannot stop a +1.2/tick climb from reaching the clamp in 4-5 ticks.
- **Single-hypothesis fast climb.** One live hypothesis has no rival, so nothing in (c) touches it: `dev_N05_normal`, RCA-07
  alone, +0.90, +2.00, +3.09, +4.00 over ticks 11-14 (shown 0.711 to 0.982) on a healthy plant. Open.
- **Fix (b), tie-break by this tick's retrieval score: DEFERRED to Session 2** (human decision). It changes rank-1 order, which
  is the open "does belief decide, or only break ties" question, to be decided with real-model numbers.
- **Whether ambiguity (a tie, a small margin) should trigger the verifier.** Separate later change; (c) leaves the
  trigger on the decision confidence.

## What I could not verify
- Why dev library belief is lower than reporting (unexplained; hypothesis: A2 selected on the reporting set).
- Everything beyond mock: a reasoning model may not depend on signature density the way the mock re-rank does.
- A01, A04 and A06 never reach TRIP_IMMINENT on their dev seeds (reporting twins do: 29.2, 59.8, 30.2 min). Time-to-trip
  differs for A02/A03/D01/D03 too. Dev A-family lead times are reported separately and are not compared with reporting.
