# Stage 6 / BAND_EDGES retune — report

## Status

**PARTIAL — plumbing landed, band VALUES reverted to Stage 5.**

`BAND_EDGES` moved out of `fieldmind/agent/l1_symbolize.py` into
`configs/base.yaml` `checks.bands` (it had been missed by the Stage-4 threshold
retune and was a duplicated constant that could rot). The wiring is now strict:
`CheckLayer` requires `cfg["bands"]`, `build_signature` refuses an empty bands
dict, `direction_and_band` raises on a partial one instead of silently falling
back to the module mirror, and `test_checks.py` asserts the mirror equals the
config.

A criterion-based **re-derivation** of the edge values was attempted and
**reverted**: it is better on every intrinsic measure but dropped the
acceptance metric (`mock Q2_top1 0.334 → 0.173`). The band values in the config
are the Stage-5 set; `orchestrator._slopes` is back to the raw slope. Baseline
metrics are restored exactly (`Q2_top1 0.334`, `Q2_top3 0.505`, `Q1 0.743`,
`Q4 0.38 / 0.926`, `Q5 0.91`, `S7 0`).

The analysis below is kept because it is a real finding about the descriptor
vocabulary and the advisor needs it; it is **not** acted on here.

## The four deciding numbers (for the attempted re-derivation)

Measured with the criterion-based bands
(`drum_level [0.03,0.15,0.50]`, `feed/steam [0.20,1.2,4.0]`,
`drum_pressure [0.03,0.15,0.60]`, `bed_temp_avg [0.50,2.5,8.3]` on the
**load-normalised** slope, `ms_temperature [0.15,0.75,3.0]`).

### 1. No-fault FLAT fraction per tag — target ≥ 0.85, none pinned at ~0.99

| tag | deadband | no-fault FLAT frac |
|---|---|---|
| `drum_level` | 0.03 | 0.998 |
| `feed_water_flow` | 0.20 | 0.848 |
| `steam_flow` | 0.20 | 0.856 |
| `drum_pressure` | 0.03 | 0.955 |
| `bed_temp_avg` (load-norm) | 0.50 | 0.908 |
| `ms_temperature` | 0.15 | 0.857 |

All ≥ 0.85. `drum_level` is 0.998 but that is legitimate — its healthy 10-min
slope is genuinely tiny and family A still clears it (below). For comparison the
**Stage-5 values** give no-fault FLAT `bed 0.065 / feed 0.275 / steam 0.281 /
pressure 0.258 / ms 0.324` — a healthy plant coded as moving on 4 of 6 tags
every tick (~7.7 spurious movement triples per no-fault episode vs ~0.6 here).

### 2. Per-family headline-tag clearance — fraction of post-onset ticks the family's headline tag reads "moving"

| family | headline | clearance | per-episode |
|---|---|---|---|
| N (no-fault) | — | — | FLAT ≥ 0.85 every tag (table 1) |
| A | `drum_level` | **0.68** | A01 .88 / A02 .65 / A03 .59 / A04 .66 / A05 .60 / A06 .69 |
| B | `water_balance` (pseudo) | **0.81** | B01 .83 / B02 .80 / B03 .78 / B04 .84 / B05 .83 |
| C | `drum_pressure` | **0.68** | C01 .77 / C02 .91 / C03 .71 / C04 .74 / C05 .37 / C06 .81 |
| D | `bed_temp_avg` (load-norm) | **0.65** | D01 .69 / D02 .65 / D03 .83 / D04 .42 |
| E | `bed_temp_avg` (load-norm) | **0.16** | E01 .14 / E02 .20 / E03 .14 |

A/B/C/D headlines clear for the bulk of their post-onset window. **D01 goes
from 0 % (the p99.7 attempt) to 69 %** — the point of the exercise. **Family E
stays below (0.16)** — consistent with the accepted Stage-4 finding that family
E is not slope-detectable and needs a cumulative-offset detector; this is
**not** a new escalation. `ep_C05_low_cv_coal` (0.37) is the one weak fault
headline; it is carried by `energy_balance HEAT_SHORT` and maps to held-out
RCA-06 anyway.

### 3. Family C sign check — raw vs load-normalised bed slope

RCA-06 / RCA-14 describe `bed_temp_avg DOWN` (heat-input deficit cools the
bed). In family C the fuel cap sags pressure, the turbine throttles, and
`slope(steam) < 0`, so the normalisation term `−coef·slope(steam)` is
**positive** and lifts the bed slope:

| episode | mean `slope(steam)` | RAW bed slope (mean / frac DOWN / frac UP) | NORM bed slope (mean / DOWN / UP) |
|---|---|---|---|
| `ep_C01_wet_coal` | −0.048 | −0.135 / 0.14 / 0.14 | −0.019 / 0.19 / 0.18 |
| `ep_C02_feeder_trip` | −0.122 | **−0.253** / 0.22 / 0.20 | **+0.044** / 0.19 / 0.24 |
| `ep_C05_low_cv_coal` | −0.065 | −0.211 / 0.15 / 0.00 | −0.053 / 0.07 / 0.05 |

**The normalisation inverts the family C bed sign** (C02: raw −0.25 → norm
+0.04, `frac UP` now exceeds `frac DOWN`). This is the same inversion
`_load_normalised_bed_slope` structurally avoids by only ever comparing to a
positive rise threshold. It did not change retrieval in the coverage run
because family C is carried by the `energy_balance HEAT_SHORT` pseudo-triple
(unaffected by normalisation) and `drum_pressure` (clearance 0.68). Recorded in
`data/physics/DERIVATIONS.md §9.1`. **The case signatures were not adjusted** —
the PDF describes raw bed temperature and is the reference.

### 4. Q2_top1 vs 0.334 — the acceptance bar

| | Stage-5 bands (raw bed) | criterion bands (load-norm bed) |
|---|---|---|
| **`mock Q2_top1`** | **0.334** | **0.173** |
| `mock Q2_top3` | 0.505 | 0.313 |
| RCA-01 rank, 4 FCV episodes (aggregated match) | 3 / 8 / 1 / 7 | **1 / 1 / 1 / 1** |
| live mock T2 top-1, B01–B05 (RCA-11) | 0.40–0.68 | 0.02–0.24 |

**0.173 < 0.334 → the band values are reverted to Stage 5.** The intrinsic
signal is better (RCA-01 fixed, noise triples gone, D01 visible) but the mock
backend's per-tick top-1 depends on the denser noisy signature: with a truthful
sparse signature a lone real triple, or a single balance pseudo-triple, loses
the k = 4 retrieval + mock re-rank to an all-FLAT case like RCA-15. The mock
re-ranks retrieved cases and does no reasoning (CLAUDE.md), so this is a
mock-harness artifact — but `Q2_top1` on mock is the stated acceptance bar and
a device demo is imminent, so the values revert.

## What landed (kept)

| change | file | why it stays |
|---|---|---|
| `checks.bands` block (Stage-5 values) | `configs/base.yaml` | the edges are now in the one config file a sweep/retune touches; Stage 4 missed them because they were only in code |
| `CheckLayer.bands = cfg["bands"]` (strict, no default) | `l1_checks.py` | a missing block is a config error, not a silent fallback |
| `build_signature(…, bands)` required; raises on empty | `l1_symbolize.py` | the runtime never uses the mirror |
| `direction_and_band(…, bands)` raises on a partial dict | `l1_symbolize.py` | a duplicated constant that can diverge is how `BAND_EDGES` went stale |
| `BAND_EDGES` mirror = device fallback only; test asserts it equals config | `l1_symbolize.py`, `bench/test_checks.py` | keeps the two copies from drifting |
| `orchestrator._slopes` docstring records the reverted normalisation attempt | `orchestrator.py` | so the next person does not re-try it blind |
| DERIVATIONS §9.1 — raw vs load-normalised bed in the symbolizer, family C sign inversion | `data/physics/DERIVATIONS.md` | the finding outlives the revert |

## Verification

| step | result |
|---|---|
| L1 unit tests | `python bench/test_checks.py` → **20 / 20** (banding: small-move-is-SLOW, true-stillness-FLAT, fast-level-FAST, mirror==config, `direction_and_band` raises on a partial bands dict). |
| full harness | `python run_demo.py --all --backend mock` → **30/30**, `Q1 0.743`, `Q2_top1 0.334`, `Q2_top3 0.505`, `Q3 1.0`, `Q4 0.38 / 0.926`, `Q5 0.91`, `S7 0.0` — **identical to the pre-Stage-6 baseline** (`stage5_case_library.md`). |
| mutation check (tests) | changed `l1_symbolize.BAND_EDGES["drum_pressure"]` `0.60 → 0.61` → `test_checks.py` "mirror equals config" **FAILS**; restored → 20/20. |
| sim self-tests | `python -m data.generator.sim` → exit 0, 11 mutations caught (Stage 6 touched no simulator code). |
| validation gate | `python -m bench.validate_data --episodes data/episodes` → 30/30 PASS (bands do not enter the gate). |
| independent re-derivation (of the criterion table) | no-fault deadband candidates measured over two disjoint seed sets (700–711, 950–969) as well as 900–911; the criterion-based bed deadband (0.5, load-norm) holds 0.88–0.91 no-fault FLAT across all three and family D clearance 0.61–0.69. Not used (reverted). |

## Constants

No constant changed value. `checks.bands` now holds the **Stage-5** band edges
verbatim; provenance is unchanged from the original `l1_symbolize.BAND_EDGES`
(a coarse hand-set vocabulary — see *Unresolved* 1).

## Numbers that changed

| quantity | before | after |
|---|---|---|
| location of the signature band edges | hard-coded dict in `l1_symbolize.py` | `configs/base.yaml checks.bands` (+ asserted mirror) |
| `direction_and_band` on a partial/empty bands dict | silent fallback to the module dict | raises |
| every Q/S metric | — | **unchanged** (baseline restored) |

## Unresolved — written into the report per the working agreement

1. **The band edges are still a coarse hand-set vocabulary with no
   derivation.** Moving them to config did not give them provenance. The
   criterion-based derivation (no-fault ≥ 85 % FLAT + every fault family's
   headline tag moving) is defensible and the four numbers above show it works
   on the physics — it fails only the **mock** `Q2_top1`, which is a per-tick
   count over a backend that does not reason. **Decision needed:** adopt the
   criterion bands together with a retrieval metric that is not a mock per-tick
   top-1 (e.g. the aggregated-signature rank, or the Stage-5 recommended
   cluster-top-1 / discriminator-accuracy), or keep the Stage-5 bands and
   accept that a healthy plant reads as moving on 4 of 6 tags.

2. **If the criterion bands are ever adopted, bed must be load-normalised only
   in the rising direction** (DERIVATIONS §9.1). As measured, normalising the
   family C bed slope flips it from DOWN (matches RCA-06/14) to ~flat/UP. A
   one-sided normalisation (`min(0, raw)` style, or require `steam_flow` flat)
   avoids it; a symmetric one does not.

3. **`ms_temperature` is not load-driven** (no-fault `slope(ms) ~ slope(steam)`
   R² = 0.02) — normalising it does nothing, so it would stay raw. Recorded so
   the asymmetry with bed is not read as an oversight.

## Next

Moving to the two orchestrator bugs that block every LLM benchmark
(`CLAUDE.md` known bugs 1 and 2): the DEGRADED latch in `derive_state` /
`trusted_tags`, and `_merge` discarding the cross-tick belief accumulator.
