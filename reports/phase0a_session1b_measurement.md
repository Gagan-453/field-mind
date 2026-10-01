# Phase 0a, Session 1b: measurement hygiene: report

All numbers are **mock backend**. They measure the deterministic and retrieval layers only. They are **not agent
results**; the mock re-ranks retrieved cases and does no reasoning. Energy is `null` (no device).

## Status
PARTIAL. Step 1 (dev set) done. Step 2 (bed slope) is a finding only. Step 3 (band calibration) was run and **not adopted**
(human decision, below). Step 4 (belief saturation on the old edges) is in progress. Not yet done: the reporting-set run,
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
FLAT-heavy cases win. On the normal-episode ticks that have hypotheses (10), rank-1 moves from RCA-07 to RCA-13. I did not
check whether RCA-13's signature is also FLAT-heavy.

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

## Disagreements recorded, not resolved
- **Instruction vs history (item 2).** "Restore load normalisation" vs a signature that never had it. Resolved by your
  decision to skip, not by me.
- **Pooled vs per-episode FLAT.** The criterion is pooled. Per-episode FLAT at the p85 edges ranges 0.52–1.00 (load swings
  differ), so a single episode can read far more movement than 15%. Not investigated.
- **Dev below reporting** on library belief metrics (0.375 vs 0.438 tie-fair top-1). Not explained.

## Blocked / needs a decision
- **Choose the overconfidence fix** (step 4, below). I am waiting on that.

## Open list (added)
- **Case-signature band calibration, tested together with the edges as one unit.** Tag-level separation is good under the
  p85 edges and the matcher still collapses, so edges and case band labels must be judged together. It touches
  `data/kb/case_library.json`, so it needs a **pre-registered rule and advisor sign-off**. Not done in this session.

## What I could not verify
- Why dev library belief is lower than reporting.
- Whether RCA-13's signature is FLAT-heavy (it doubles under the p85 edges).
- Everything beyond mock: a reasoning model may not depend on signature density the way the mock re-rank does.
- A01, A04 and A06 never reach TRIP_IMMINENT on their dev seeds (reporting twins do: 29.2, 59.8, 30.2 min). Time-to-trip
  differs for A02/A03/D01/D03 too. Dev A-family lead-time metrics are therefore not comparable with reporting.
