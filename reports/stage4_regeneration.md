# Stage 4 / regeneration + inherited retunes — report

## Status
DONE — all 30 episodes regenerated and passing the validation gate. Driver
severities re-anchored to the RCA case timelines; one shared load OU
supplemented with independent per-subsystem process noise (steam↔bed 0.98 →
0.88); `notes_gen.base_cv`, the L1 thresholds, the DEVIATION band and the load
coefficient all brought onto the new physics.

## Verification

| step | result |
|---|---|
| ran the generator | `python -m data.generator.episode_build --out data/episodes` → **30/30 written**, 0 rejected. `by family: A6 B5 C6 D4 E3 N6`. |
| gate on the output | `python -m bench.validate_data --episodes data/episodes` → **30/30 PASS** (1 benign WARN, `ep_E03`). |
| sim self-tests | `python3 -m data.generator.sim` → exit 0. 10 self-test groups pass; 8 direction checks OK; `_ou_recheck` OK; **11 mutations** caught (M11 new: zero the process-OU innovation → steam↔bed → +0.97 > 0.95, caught). |
| L1 unit tests | `python bench/test_checks.py` → **18 / 18**. |
| independent re-derivation (xcorr) | `sim._pearson` steam↔bed **+0.871**; OLS `sqrt(R²)` of `bed ~ steam` **+0.872** (0.1 %). R² = 0.760. |
| independent re-derivation (time-to-trip) | closed form `t_trip = 40 %span / (K_level(66)·deficit)` from the **measured** effective deficit: `ep_A01` 35.7 min vs 29.2 measured (22 %); `ep_A02` 15.6 vs 13.1 (19 %); `ep_A06` 35.5 vs 30.2 (17 %). Closed form over-predicts because it assumes a constant deficit while the level controller claws feed back early — direction correct, all < 2×. |
| mutation check | `G_SW` sign flipped → `ep_C01` → validate_data **C1 FAIL**. Restored. |

## Effect 1 — driver severities re-anchored to the RCA timelines

**Framing (per the review):** this is *re-anchoring severity to real timescales*,
not undoing a speed-up. The physics from stage 3 is unchanged. Where a case
gives a timeline the severity is solved against it; where it does not (family E,
the 8 h → ≤3 h compression of family B) the severity is recorded as a benchmark
design choice.

RCA anchors (`docs/Boiler_Failure_Case_Studies_RCA.pdf`, read with pypdf):

| family | case | RCA onset→ALARM | RCA onset→trip |
|---|---|---|---|
| A | 1 | 20 % Lo @ ~25 min | manual low-low trip @ ~35 min ("declined monotonically for 30 min") |
| B | 11 | — (controlled trip @ ~8 h) | feed 2–3 t/h over steam @ 4.5 h; conductivity falling |
| C | 6 | 66→63 kg/cm² @ 35 min; 66→58 @ 65 min | burner support @ 58, **no hard trip** |
| D | 7 | 880 °C bed @ ~90 min | 940 °C DCF trip @ ~125 min |
| E | — | never | never (no RCA timeline — design choice) |

### Before / after (min from onset; "—" = state not reached in the episode)

| episode | old→trip | new→DEVIATION | new→ALARM | new→trip | driver change |
|---|---|---|---|---|---|
| A01 fcv_seize | 15.2 | 7.2 | 19.2 | **29.2** | eff 0.77 → 0.81 |
| A02 fcv_seize_fast | 6.3 | 2.4 | 9.8 | **13.1** | eff 0.62 → 0.75 |
| A03 bfp_suction | 5.9 | 3.8 | 15.9 | **20.0** | eff 0.55 → 0.75 |
| A04 strainer_choke | 25.5 | 22.0 | 35.8 | **59.8** | eff 0.79 → 0.83 (120-min ep) |
| A05 fcv_caught | trip (mis-caught) | 8.3 | — | **— (recovers)** | eff 0.74 → 0.82, recovery onset+1100 s |
| A06 fcv_seize_repeat | 14.7 | 10.6 | 24.0 | **30.2** | eff 0.75 → 0.82 |
| B01 tube_leak | none | 9.6 | — | none | leak 3.5 → 2.2 t/h (gap ≈ +3.1) |
| B02 tube_leak_fast | none | 2.2 | — | none | leak 6.0 → 3.5 |
| B03 tube_leak_slow | none | 27.1 | — | none | leak 2.2 → 1.8 (150-min ep) |
| B04 cbd_left_open | none | 1.8 | — | none | leak 4.0 → 2.5 |
| B05 tube_leak_repeat | none | 9.9 | — | none | leak 3.5 → 2.2 |
| C01 wet_coal | none (p→48) | 10.6 | — | none (p→57.5) | fuel_avail 0.80 → 0.955 |
| C02 feeder_trip | none (p→37) | 1.6 | 4.9 | none (p→52) | 0.62 → 0.89 |
| C03 wet_coal_mild | none (p→52) | 22.1 | — | none (p→56) | 0.88 → 0.96 |
| C04 feeder_trip_caught | none | 1.0 | 2.4 | — (recovers) | 0.65 → 0.89 |
| C05 low_cv_coal | none (p→50) | 15.6 | — | none (p→56) | 0.84 → 0.95 |
| C06 wet_coal_repeat | none (p→47) | 10.8 | — | none (p→58) | 0.80 → 0.96 |
| D01 high_cv_coal | 12.1 | 26.6 | 48.8 | **120.3** | cv 1.16/ramp 12 min → 1.14/ramp 120 min (160-min ep) |
| D02 low_primary_air | none (bed 931) | 33.4 | 41.1 | none (bed ~915) | PA 0.80/ramp 8 → 0.86/ramp 70 (130-min ep) |
| D03 high_cv_severe | 5.2 | 11.3 | 15.6 | **39.8** | cv 1.24/ramp 6 → 1.16/ramp 55 (80-min ep) |
| D04 low_pa_caught | none | 16.8 | — | — (recovers) | PA 0.84/ramp 8 → 0.86/ramp 40 |
| E01–E03 | none | — | — | none | absorb 0.985–0.989 → 0.984–0.986; seeds 600/603/604 |

Episode durations were extended where the RCA trajectory did not fit
(A01 55→70, A03 50→60, B/C several, D01 70→160, D02 60→130, D03 50→80, D04 65→85,
E01 240→200, E02 200→180, E03 180→160). All 30 tier labels unchanged.

**Family A is a knife-edge.** Near `eff·81.6 ≈ steam demand` a 0.02 change in
effectiveness moves time-to-trip from ~15 min to "never", and the sub-model-4
slow load OU (σ 2.1 t/h) sets a different baseline load per seed. Effectiveness
was therefore solved **per scenario seed**, not from one global number. The
load sensitivity is physical (a marginal feed restriction is more or less
survivable with the load at the time) and is kept.

**Family D is carried by a long ramp.** The corrected bed lag (τ 139 s) reaches
its target in minutes, so RCA Case 7's 90-min / 125-min approach is produced by
a 55–120 min driver ramp (the fuel changeover / ash-recirc depletion the case
describes), not a fast step. `D01` trips at **120.3 min** (RCA 125).

## Effect 2 — independent per-subsystem process noise

One shared `load_demand` OU coupled every tag through a single input →
steam↔bed `pearson_level` **+0.98** vs the fingerprint's **+0.87** (bed 96 %
explained by steam vs 76 % in the real trace).

Added: three **independent** single-timescale OU processes on the *effective*
driver values inside `step()` — `heat_absorption`, `coal_cv_factor`,
`primary_air` — never mutating `self.d.*`, so the fault schedule and emitted
ground truth stay exact. They enter the same energy balance as the scheduled
drivers, so **both balances still close** (verified: `sim` self-tests 5, 6a;
`_leak_run` paired mutations M3/M4; validate_data C1/C2 on all 30). The
`primary_air` disturbance is applied as a signed `− K_PA·ou_pa` term so the
`min(1, ·)` rectifier does not bias the bed upward in normal operation.

| symbol | value | provenance | range | affects |
|---|---|---|---|---|
| `TAU_PROC_S` | 25 min | ASSUMED — combustion / air-side disturbance timescale | 15–45 min | how much of the OU the τ 139 s bed lag passes |
| `SIGMA_PROC_HA` | 0.0022 | ASSUMED, calibrated to steam↔bed 0.87 | 0.001–0.004 | bed + pressure |
| `SIGMA_PROC_CV` | 0.0022 | ASSUMED, calibrated | 0.001–0.004 | released heat → bed + pressure |
| `SIGMA_PROC_PA` | 0.0035 | ASSUMED, calibrated | 0.0015–0.006 | bed target (zero-mean K_PA term) |

**Achieved** (`sim._ou_recheck` / `validate_data --suite`, 3 × 30 h no-fault):

| quantity | one shared OU | + process noise | fingerprint |
|---|---|---|---|
| steam↔bed `pearson_level` | +0.97 | **+0.88** | +0.869 |
| bed R² on steam | 0.94 | **0.76** | 0.755 |
| steam_flow sd | 2.34 | 2.06 | 2.38 |
| bed 30-min autocorrelation | 0.62 | 0.57 | 0.571 |

Stated as **achieved**, not tuned-to-hit: the σ triple was set once against the
0.87 target and the result reported. `_ou_recheck` now asserts steam↔bed ∈
[0.60, 0.95] (both bounds); mutation M11 (kill the process OU) → +0.97, caught.

## Inherited items

### notes_gen.base_cv 3400 → 4040
`data/generator/notes_gen.py`: `base_cv` literal and the two "3400" note strings
→ **4040** (`sim.GCV_KCAL_PER_KG`, Dulong on the one ASSUMED ultimate analysis,
DERIVATIONS §4.1). `records.json coal_lab_report.gcv_kcal_kg` now `int(4040·cv)`.

### DEVIATION band load-normalised + a pressure term
`episode_build.state_timeline`, DEVIATION tier:
- `|bed − 850| > 25` → `|bed − (850 + LOAD_COEF·(steam − 67))| > 25`. Same
  normalisation L1's `_load_normalised_bed_slope` applies — a raw band
  manufactures DEVIATION labels the detector is built never to raise, and a bed
  at 870 °C at high load is operating normally. `LOAD_COEF` is read from the
  config at generation time and **stamped into every `ground_truth.json` as
  `state_timeline_load_coef`** so a future re-fit cannot silently relabel data.
- **new:** `drum_pressure < 63`. RCA Case 6's combustion-deficit deviation
  point (66→63 at T+35 min); there was no pressure term before, so an
  RCA-faithful controlled sag (family C now sags to ~57 with no hard trip)
  registered as all-NORMAL and family C was unscoreable.
- `gap > 4` → `gap > 2.5`. Family B (RCA Case 11) is "feed 2–3 t/h over steam
  yet level holds"; the old > 4 band never saw it once leaks were sized to the
  RCA.
- 60 s debounce added so noise flicker across these tighter thresholds does not
  shatter the timeline.

ALARM/TRIP thresholds (bed 880/940, level 20/10, pressure 55) are **unchanged**
— real RCA setpoints.

### load coefficient re-fit (DERIVATIONS §9)
Slope-regression `slope(bed) ~ slope(steam)` over the regenerated N01–N06:
**2.21 °C/tph, R² 0.61**. But OLS slope with estimation noise on the regressor
is attenuated toward 0; the value that **minimises the no-fault load-normalised
bed-slope residual** is **2.75–2.85** (swept), which equals the simulator's
generator gain `K_BED_LOAD = 2.75`. Kept at **2.75** — the normalisation must
cancel exactly what the generator adds, and 2.21 leaves a `0.54·slope(steam)`
residual that raises the family-E detector's floor. `config` value therefore
**did not move**; no second regeneration needed for it.

### L1 thresholds re-tuned against the new noise
Measured over **12 fresh-seeded no-fault runs (seeds 900–911, disjoint from
N01–N06** so Q5 stays uncircular). Thresholds set from the p99.7 of each
statistic; the aggregate rate was **measured**, not assumed independent.

| key | old | new | no-fault p99.7 of the statistic |
|---|---|---|---|
| `checks.balance.level_gain_pct_per_min_per_tph` | 0.22 | **0.586** | — (matches `geometry.K_level(66)`; was an invented literal) |
| `checks.rates.bed_temp_avg.threshold` | 0.4 | **1.6** | 1.28 °C/min (10-min slope, **not** load-normalised → OU load swings it) |
| `checks.rates.drum_pressure.threshold` | −0.05 | **−0.15** | 0.12 kg/cm²/min |
| `checks.rates_long.bed_temp_avg` | 0.08 / 40 min | **0.22 / 55 min** | 0.24 (55-min load-normalised) — see finding below |
| `checks.rates_long.ms_temperature.threshold` | 0.05 | **0.20** | 0.20 |
| `checks.balance.residual_tph` | 2.0 | **1.5** | 0.13 t/h |
| `checks.balance.p_falling` | 0.05 | **0.15** | 0.12 |
| `checks.balance.bed_rising` | 0.3 | **1.3** | 1.19 (5-min load-normalised) |
| `l1_checks._patterns` bed-slope literals (code, not config) | 0.4 / 0.2 / 0.1 | **`bed_rising` / 0.5 / 0.3** | the 0.4 literal fired the "energy accumulating" pattern ~15×/h on a healthy plant |

**Achieved false-positive rate — analytic, from the fresh no-fault set:**

| check | FP ticks/hour |
|---|---|
| RATE:bed_temp_avg (dominated by `rates_long`, threshold 0.22) | 1.10 |
| RATE:drum_pressure | 0.24 |
| BALANCE:drum_pressure | 0.24 |
| BALANCE:bed_temp_avg | 0.14 |
| **aggregate** | **1.48 / hour** (target ≤ 2) |

Per-family L1 detection is intact — first WATCH+ fact after onset: A 2.5–18 min,
B 2–27 min (BALANCE water-residual), C 1.5–20 min, D 5.5–9.5 min. **This is NOT
a harness Q5 result** — it is the analytic trigger rate of L1 over no-fault
windows. A closed-loop Q5 on held-out episodes is a scoped follow-up
(deliberately not iterated against these same episodes).

## Disagreements recorded, not resolved

1. **Family E is now at the edge of detectability. (stop-rule-2 hit — recorded,
   not resolved by tuning.)** With the OU load driver + the per-subsystem process
   noise, the no-fault load-normalised bed slope over 55 min has p99.7 ≈ 0.24
   °C/min. Family E's own signal is ~0.15–0.24 °C/min (over its full duration).
   The two distributions **overlap** — no threshold catches family E without
   ~1 FP/hour on that one check. Confirmed against the generated episodes:
   `rates_long.bed` fires on **E01 at +95 min and E02 at +97 min** (still lead
   time in a 200 / 180 min episode); **E03 is never flagged by L1**. The 40 °C /
   15 σ margin CLAUDE.md described is gone; CLAUDE.md itself predicted "about
   4 σ against real variability" and it is now < 2 σ, partly because family E
   was also softened (0.985 → 0.984–0.986) to keep bed_max clear of the 880
   alarm under the process noise (E03 bed_max 874). **Options for the advisor:**
   (a) strengthen family E — conflicts with its "crosses nothing" definition,
   and every stronger seed/severity tested pushed bed_max ≥ 878; (b) give L1 a
   **cumulative-offset** drift detector (family E's *offset* from the
   load-normalised baseline reaches +12–20 °C, well outside no-fault ±5 °C — a
   slope detector is the wrong instrument for a ramp), an L1 redesign out of
   scope for a data stage; (c) accept low family-E detectability and report it.
   Chosen: (c) for now, `rates_long.bed` threshold 0.22 so E01/E02 clear it,
   aggregate FP still < 2/h.

2. **`load_coef` empirical fit (2.21) ≠ the value used (2.75).** §9 asks for the
   fit to the normals; the fit is errors-in-variables-attenuated and using it
   degrades the family-E normalisation. 2.75 (generator gain, residual-minimising)
   is used. Both figures and the reason are in the config comment.

3. **Family C bed cooling is now small (~8–12 °C vs the old 35 °C).** The
   pressure-integrator quasi-steady sag is ≈ `60·fuel_availability`, so an
   RCA-faithful sag to ~57 kg/cm² needs `fuel_availability ≈ 0.955`, which only
   removes ~5 % of heat and cools the *average* bed ~8–12 °C. RCA Case 6's
   bed-temperature fall is **compartment-selective**; the six-compartment
   average (our tag) would fall less. The discriminating L1 signal for family C
   is the pressure sag at flat steam (BALANCE "heat input short"), not the bed
   drop — verified to fire on all six C episodes. Recorded; the old 35 °C was
   flagged "on the strong side" in `stage3_submodel2.md` disagreement 6.

4. **`steam↔pressure` / `bed↔pressure` cross-correlation sign** is still
   negative (−0.21 / −0.12) against the fingerprint's +0.35 / +0.39. Unchanged
   from `stage3_submodel4.md` disagreement 2 — the real plant's drum-pressure
   setpoint co-drifts with load over hours; ours is fixed at 66. A slow OU on
   the pressure setpoint is the candidate fix, still deferred. The process noise
   added here does not touch this.

5. **`drum_pressure` sd 0.12 vs fingerprint 0.77** — likewise unchanged and same
   cause (fixed setpoint). Recorded in `stage3_submodel4.md`.

## Blocked / needs a decision
- **Family-E detectability (disagreement 1).** The question for the advisor:
  accept it, or authorise an L1 cumulative-offset drift detector in the agent
  stage. Not a data-generation fix.
- **A closed-loop harness Q5** on held-out normal episodes (fresh seeds again,
  or more generated normals) to confirm the analytic 1.48/h — deliberately not
  done here to keep the retune uncircular.

## What I could not verify
- **Family A per-seed severities** reproduce the RCA *rate* (20 % @ ~25 min,
  trip @ ~30–40 min) but the RCA *deficit* (4–5 t/h) is not matched — the
  measured effective deficit is ~1.9 t/h for the canonical cases. This is the
  pre-existing §3.7 K-over-determination, carried, not introduced here.
- **`TAU_PROC_S = 25 min` and the σ triple** are ASSUMED — the fingerprint has
  no per-subsystem disturbance spectrum to fit them to. They are pinned only by
  the single steam↔bed target; the (τ, σ) pair is a ridge, not a point (τ 20 or
  35 min gave the same +0.87 with a rescaled σ).
- **Family E's "crosses nothing" guarantee** holds for the three chosen seeds
  (bed_max 874/875/874) but is **seed-sensitive**: seeds 602 / 608 / 611 at the
  same severity reach bed_max 880–884. The generated episodes are safe; the
  guarantee is not robust to an arbitrary seed.
