# Stage 3 / sub-model 4 — cross-correlated OU drivers + fingerprint measurement noise — report

## Status
DONE — the last two pre-rewrite pieces in `sim.py` are replaced:

1. **Load wander.** `swing = 2·sin(t/1800)` → a **two-timescale
   Ornstein-Uhlenbeck** perturbation on `load_demand`:
   `load = d.load_demand + ou_fast + ou_slow`, `ou_fast` τ = 26.6 min
   (FITTED `steam_flow.ar1`), `ou_slow` τ = 3 h (the slow component the
   single-AR1 fit misses). One shared process drives every tag through the
   physics, so the tags come out **cross-correlated** with no per-tag noise
   injection and the balances still close.
2. **Measurement noise.** The ad-hoc dict (bed 1.2, ms 0.8 °C — ~20× too big)
   → `EMIT_NOISE` from the fingerprint white-noise estimates
   (`hf_noise_est_2nd_diff`, DERIVATIONS §7.2): bed 0.057, ms 0.026, steam
   0.109, pressure 0.019, level 0.15 (no ref), feed 0.109. Added to the emitted
   copy only.

Episodes NOT regenerated. `configs/base.yaml` NOT touched. `sim.py` core stays
stdlib-only (the OU uses `math` + `random`; the verification stats use
`statistics`, only under `__main__`).

## Verification
| step | result |
|---|---|
| ran the module | `python3 -m data.generator.sim` — **exit 0**, ~9 s. Two expected `RuntimeWarning`s (family-A clamp guard). All 30 episodes still build (`episode_build`, dry run). |
| self-tests | `_self_test()` — **10 groups pass**. Group 5 (no-fault energy balance) now runs **4 seeds** with bands widened for the OU wander (pressure ±3 kg/cm2, bed ±30 °C). Groups 8–10 (dissolved solids) unaffected. |
| direction checks | **8 / 8 OK** — swell, family A/B, fuel-cap, E10 leak, E8 primary-air, E12 ms-vs-load all still fire with the OU + new noise. |
| independent re-derivation | **achieved statistics vs the fingerprint** from 3 × 30-h no-fault runs (a 45–240 min episode is far too short to estimate a 3-h-τ process). `steam_flow` sd **2.34 (fp 2.38)**, autocorrelation 5m/30m/1h **0.91/0.59/0.35 (fp 0.88/0.65/0.50)**; `steam↔bed` cross-correlation **+0.95 (fp +0.87)**. Table below. |
| mutation check | **9 mutations, all caught.** New **M9**: kill the slow OU component → `steam_flow` 1-h autocorrelation collapses from ~0.4 to **−0.01** over 24-h runs (fast-only OU, τ 27 min → exp(−60/27) = 0.11) — caught by the sub-model-4 stat check. |

### Achieved vs fingerprint (3 × 30-h no-fault runs, `_ou_recheck`)
| tag | sd | fp sd | acf 5m / 30m / 1h | fp acf | verdict |
|---|---|---|---|---|---|
| `steam_flow` | **2.34** | 2.38 | 0.91 / 0.59 / 0.35 | 0.88 / 0.65 / 0.50 | **match** (the OU is fitted to this) |
| `bed_temp_avg` | 6.07 | 10.68 | 0.97 / 0.66 / 0.39 | 0.85 / 0.57 / 0.42 | autocorrelation **matches**; sd low (disagreement 1) |
| `ms_temperature` | 1.16 | 4.33 | 0.93 / 0.62 / 0.37 | 0.77 / 0.41 / 0.26 | sd low (disagreement 1) |
| `drum_pressure` | 0.22 | 0.77 | 0.23 / 0.00 / 0.00 | 0.44 / 0.15 / 0.05 | tightly controlled (disagreement 2 / correction 1) |
| **cross-corr** steam↔bed | **+0.95** | +0.87 | | | **match** (single shared driver) |
| cross-corr steam↔pressure | −0.24 | +0.35 (incr-1min −0.09) | | | sign gap (disagreement 3) |
| cross-corr bed↔pressure | −0.12 | +0.39 | | | sign gap (disagreement 3) |

Per-sample increment sd (emitted): bed 0.085, ms 0.039, steam 0.200, pressure
0.031 — vs the real trace's bed 0.273 / ms 0.067 / steam 0.188
(CLAUDE.md calibration-gap table). Steam matches; bed and ms still move a little
less sample-to-sample than reality (disagreement 1).

## Direction checks
Unchanged from sub-model 2 (the OU adds no tag sign). All 8 re-verified with
the OU active and the fingerprint noise. `steam_flow` in the swell checks now
carries the OU wander instead of the sinusoid — the swell trace slope is still
−0.776 / −0.787 vs −G_sw −0.780.

## Constants introduced
| symbol | value | provenance | range | affects |
|---|---|---|---|---|
| `TAU_LOAD_FAST_S` | 26.62 min | **FITTED** — `fingerprint steam_flow.ar1.timescale_minutes` | — | fast load wander; short-lag tag autocorrelation |
| `TAU_LOAD_SLOW_S` | 3.0 h | **ASSUMED** | 2 – 6 h | multi-hour load wander; 1-h+ tag autocorrelation, cross-episode mean-load spread |
| `SIGMA_LOAD_FAST_TPH` | 1.4 t/h | **FITTED split** — with `SIGMA_LOAD_SLOW` targets emitted `steam_flow` sd ~ 2.5 and 1-h autocorrelation ~ 0.50 | — | `steam_flow` variability |
| `SIGMA_LOAD_SLOW_TPH` | 2.1 t/h | **FITTED split** — as above; `√(1.4²+2.1²) = 2.52` | — | as above |
| `EMIT_NOISE` | bed 0.057, ms 0.026, steam 0.109, pressure 0.019, level 0.15, feed 0.109 | **FITTED** (`hf_noise_est_2nd_diff`) except level (**ASSUMED**, no column) and feed (**ASSUMED**, mirrors steam) | — | emitted trace only; L1 RATE / MAD / stuck checks |

## Numbers that changed
| quantity | old | new | ratio | downstream |
|---|---|---|---|---|
| load wander | `2·sin(t/1800)` — deterministic ±2 t/h, 30-min period | two-timescale OU, ±2.5 t/h sd, τ 27 min + 3 h, seeded | — | every tag's within/across-episode wander; `steam_flow` autocorrelation and cross-correlations; no-fault false-positive exposure (Q5) |
| emit noise `bed_temp_avg` | 1.2 °C | **0.057 °C** | 0.048× | L1 RATE / MAD thresholds on bed (tuned against 1.2 — **not** retuned here) |
| emit noise `ms_temperature` | 0.8 °C | **0.026 °C** | 0.033× | L1 checks on ms |
| emit noise `steam_flow` | 0.35 t/h | **0.109 t/h** | 0.31× | L1 balance residual noise floor |
| emit noise `feed_water_flow` | 0.35 t/h | **0.109 t/h** | 0.31× | L1 balance residual noise floor |
| emit noise `drum_pressure` | 0.05 kg/cm2 | **0.019 kg/cm2** | 0.38× | L1 `p_falling` check |
| emit noise `drum_level` | 0.15 % | 0.15 % (unchanged — no ref) | 1× | swell tests (unchanged) |
| no-fault bed swing | ~±13 °C (sinusoid + old noise) | up to ~±20 °C (OU load wander × K_BED_LOAD) | — | approaches `episode_build` DEVIATION threshold `|bed−850|>25` — see disagreement 4 |

The five `EMIT_NOISE` FITTED values and the OU τ are the numbers
DERIVATIONS §7.1 / §7.2 already named; this stage puts them in the simulator.

## Disagreements recorded, not resolved
1. **`bed_temp_avg` / `ms_temperature` standard deviation is low** — bed 6.1
   vs fingerprint 10.7, ms 1.2 vs 4.3. The **autocorrelation shape matches**
   well (bed 0.97/0.66/0.39 vs 0.85/0.57/0.42), so the *dynamics* are right;
   the real tags just have more absolute long-range drift. Bed's 5-day sd
   10.68 includes very-slow wander (days) that a τ = 3 h `ou_slow` does not
   reach; ms has its own slow drift (attemperator setpoint, SH-side fouling)
   that is not a driver in this model. **Not forced** — CLAUDE.md is explicit
   that the long single-tag autocorrelations are inherited and immaterial to
   the fault families, and inflating `SIGMA_LOAD_SLOW` to hit bed sd 10.7 would
   push `steam_flow` sd well past its own fingerprint target and widen the
   no-fault bed swing (disagreement 4). A third, day-scale OU component is a
   candidate for a later stage.
2. **`drum_pressure` sd 0.22 vs fingerprint 0.77; achieved autocorrelation
   ≈ 0 vs the 44.5-min ar1** (correction 1's deferred item). With `e_p`
   **physical** (679 J/Pa, sub-model 2) and the firing pressure-trim active,
   drum pressure is held tighter than the real trace. The real 44.5-min
   pressure autocorrelation is itself inherited input slowness (CLAUDE.md:
   "steam flow's own τ is 27 min"); our load wander is present (steam sd 2.34)
   but the firing controller absorbs it before pressure moves much. **e_p stays
   physical** — this is a control-loop-looseness question (the `0.06·p_err`
   firing trim), not an `e_p` question, and loosening the trim risks the
   family-C pressure-collapse mechanism. Flagged for the config-retune stage.
   Fault-family pressure behaviour is correct: family C collapses (44–50
   kg/cm2), family E holds, normal wanders ~±1.3.
3. **`steam↔pressure` and `bed↔pressure` cross-correlation sign** — ours
   −0.24 / −0.12, fingerprint `pearson_level` +0.35 / +0.39. At the level, our
   pressure dips slightly when load rises (fast transient before firing catches
   up). The fingerprint's own `pearson_increment_1min` steam↔p is **−0.09**
   (same sign as ours at short timescales); the positive `pearson_level` value
   is a slow co-drift (operator raising pressure and load setpoints together
   over hours) that this model does not have, because `ou_slow` drives only
   load and the pressure controller returns pressure to 66. Minor — pressure
   cross-correlation is not a fault discriminator. Not forced.
4. **No-fault bed can swing ~±20 °C from OU load wander**, approaching the
   `episode_build.state_timeline` DEVIATION threshold `|bed−850| > 25`. Across
   8 seeds the worst 90-min no-fault run reached +19.9 °C. This is within the
   fingerprint's own within-1h bed envelope (ptp mean 24.6 °C, p95 38 °C), so
   it is realistic, but it narrows the margin before a normal episode shows a
   spurious DEVIATION tick (a Q5 false positive). The DEVIATION band and
   `load_coef_degc_per_tph` are flagged in `base.yaml` as phase-2 tuning; this
   is a **config-retune / regeneration dependency**, recorded, not a
   sub-model-4 defect (the bed-load sensitivity is `K_BED_LOAD = 2.75`,
   anchored to the config).
5. **`ou_slow` τ = 3 h and the σ split are ASSUMED-fitted, not uniquely
   determined.** The pair (τ, σ_slow) that reproduces steam sd 2.4 and 1-h
   autocorrelation 0.50 is a ridge, not a point — τ 2.5 h with a larger σ, or
   τ 4 h with a smaller σ, fit about as well. 3 h / 2.1 t/h is one defensible
   point on it. The fingerprint has no second-timescale fit to pin it.

## Blocked / needs a decision
No new stop-rule hits. Config-retune / regeneration stage inherits:
- **(a)** L1 thresholds tuned against the **old** noise dict —
  `checks.rates.*`, `checks.rates_long.*`, `checks.balance.*`, MAD/stuck
  epsilons — must be re-tuned against `EMIT_NOISE` (bed/ms noise is now ~20×
  smaller, so the old rate thresholds are far too loose).
- **(b)** `episode_build` DEVIATION band + `load_coef_degc_per_tph` vs the
  no-fault OU bed swing (disagreement 4).
- **(c)** the firing pressure-trim gain vs the too-tight `drum_pressure`
  (disagreement 2).
- **(d)** `§9` load-coefficient re-fit to the regenerated normals (needs the
  regeneration).
- Carried from earlier sub-models: `notes_gen.base_cv` 3400 → ~4040 (sm2);
  online CBD analyser assumption (sm1/sm3); drum GA / level-transmitter span
  (sm1).

## What I could not verify
- **`ou_slow` parameters** — no second-timescale fit exists in the fingerprint
  (disagreement 5). Would need a spectral / multi-AR fit of the reference
  `steam_flow` trace.
- **Whether bed/ms need a day-scale drift component** (disagreement 1) —
  reproducing the 5-day sd would; whether that matters for the benchmark is an
  advisor question (the fault families do not depend on it).
- **`feed_water_flow` noise 0.109** — no reference column; mirrors `steam_flow`.
- **The absolute `drum_level` noise 0.15 %** — unchanged from sub-model 1, no
  fingerprint column.
- The achieved statistics are from **synthetic no-fault runs**, not compared
  tick-for-tick against the real trace (which is a different boiler at a
  different operating point — CLAUDE.md §9).
