# Stage 6 / BAND_EDGES retune — report

## Status

DONE — `BAND_EDGES` moved from `fieldmind/agent/l1_symbolize.py` into
`configs/base.yaml` under `checks.bands`, and every edge re-derived by the
Stage-4 method against the regenerated no-fault slope distributions. The
signature is now truthful: a non-FLAT triple means the tag moved more than a
healthy plant does. **RCA-01 goes to rank 1/13 for all four FCV episodes**
(offline aggregated match; was A05 rank 1 only). The retune also *surfaces* a
finding the old edges were masking — the SLOW/MED/FAST labels in the
PDF-transcribed case signatures are unreachable for every slow-developing fault
(B, C, D, E), because the old edges sat *below* the plant's true 10-min-slope
noise floor and only "fired" on slow faults by also firing on healthy wander.
Case signatures and the FLAT weight were **not touched**.

## What changed

| item | old | new |
|---|---|---|
| `BAND_EDGES` location | hard-coded dict in `l1_symbolize.py` | `configs/base.yaml` → `checks.bands` (list per tag); `l1_symbolize.BAND_EDGES` kept only as the device fallback, asserted equal to config by a unit test |
| threading | `build_signature(facts, slopes)` | `build_signature(facts, slopes, self.checks.bands)`; `CheckLayer.bands = cfg.get("bands", {})`; `direction_and_band(tag, slope, bands=None)` |

### Method (identical to the Stage-4 threshold retune)

The signature slope is the per-tag **10-min least-squares slope**
(`orchestrator._slopes` → `direction_and_band`). Measured its no-fault
`|slope|` distribution over the **12 fresh-seeded no-fault runs (seeds
900–911)** — the same set Stage 4 used, disjoint from N01–N06 so Q5 stays
uncircular. **deadband := p99.7 of that distribution** (Stage 4: "thresholds
set from the p99.7 of each statistic"). `slow/med` and `med/fast` keep each
tag's *old* multiple of its deadband (the old edges were themselves nothing but
deadband multiples — 5–6× and 16.7–20×) rescaled onto the new deadband.

### No-fault `|slope|` distribution and the resulting bands

2 520 ready ticks, 12 runs. `|slope|` in tag-units/min on the 10-min window:

| tag | p50 | p95 | p99 | **p99.7** | max | old dead | **new** `[dead, slow/med, med/fast]` |
|---|---|---|---|---|---|---|---|
| `drum_level` | 0.0038 | 0.0115 | 0.0168 | **0.0219** | 0.037 | 0.03 | `[0.022, 0.11, 0.37]` |
| `feed_water_flow` | 0.0960 | 0.2822 | 0.4044 | **0.4552** | 0.496 | 0.05 | `[0.46, 2.8, 9.2]` |
| `steam_flow` | 0.0948 | 0.2725 | 0.4013 | **0.4577** | 0.506 | 0.05 | `[0.46, 2.8, 9.2]` |
| `drum_pressure` | 0.0084 | 0.0288 | 0.1074 | **0.1606** | 0.253 | 0.004 | `[0.16, 0.8, 3.2]` |
| `bed_temp_avg` | 0.2538 | 0.8173 | 1.2783 | **2.0579** | 2.856 | 0.03 | `[2.1, 10.0, 35.0]` |
| `ms_temperature` | 0.0665 | 0.2223 | 0.3570 | **0.5968** | 0.726 | 0.04 | `[0.6, 3.0, 12.0]` |

The old deadbands for `feed_water_flow`, `steam_flow`, `drum_pressure`,
`bed_temp_avg`, `ms_temperature` were **20–70× too small** — they were the
noise floor of the *pre-regeneration* physics (sub-model 4 dropped bed/ms emit
noise ~20× but added the OU load driver + per-subsystem process disturbances,
which move the *10-min slope* far more than emit noise did). `drum_level` was
already correct (0.03 vs measured p99.7 0.022) and barely moves.

### The check — fraction of no-fault ticks reading FLAT per tag

This is the point of the exercise: FLAT must mean "not moving more than a
healthy plant does", so nearly every healthy tick must read FLAT.

| tag | OLD dead | OLD FLAT frac | **NEW dead** | **NEW FLAT frac** |
|---|---|---|---|---|
| `drum_level` | 0.03 | 0.9984 | 0.022 | **0.9972** |
| `feed_water_flow` | 0.05 | 0.2754 | 0.46 | **0.9972** |
| `steam_flow` | 0.05 | 0.2810 | 0.46 | **0.9972** |
| `drum_pressure` | 0.004 | 0.2575 | 0.16 | **0.9968** |
| `bed_temp_avg` | 0.03 | **0.0651** | 2.1 | **0.9976** |
| `ms_temperature` | 0.04 | 0.3238 | 0.6 | **0.9972** |

Under the old edges a healthy plant was coded as **moving on 4 of 6 tags every
tick** (`bed_temp_avg` FLAT only 6.5 % of the time). That is the "~8 spurious
movement triples per tick cap the weighted-Jaccard near 0.1–0.25" that
`stage5_case_library.md` blamed three times on "the simulator's per-tick
noise" — it was the un-retuned deadbands. Measured directly:

| | pre-onset (healthy) movement triples / episode | post-onset |
|---|---|---|
| OLD bands | **7.71** | 9–15 |
| NEW bands | **0.62** | 0–3 (12 for the two `_caught` recovery episodes, where the plant genuinely swings both ways) |

## Verification

| step | result |
|---|---|
| ran the retune module | `band_retune.py` → distributions + bands + FLAT fractions above; 2 520 no-fault ticks, 12 fresh runs. |
| L1 unit tests | `python bench/test_checks.py` → **20 / 20** (was 18/18; the 3 banding tests replaced by 5 — healthy-plant bed drift reads FLAT, just-past-deadband is SLOW, mid-band is MED, large is FAST, and `BAND_EDGES` mirrors the config). |
| full harness | `python run_demo.py --all --backend mock` → **30/30**, no crash. `Q1_macro_f1 0.743`, `Q3_faithfulness 1.0`, `Q5_fp_per_hour 0.91`, `S7_deadline_miss 0.0` — **all unchanged** (bands touch only `build_signature` → retrieval). `Q2_top1 0.334 → 0.132`, `Q2_top3 0.505 → 0.188` over the same 17 scored episodes — see *Disagreements* 1. |
| sim self-tests | `python -m data.generator.sim` → exit 0, 11 mutations caught, 8 direction checks OK (no simulator code touched). |
| validation gate | `python -m bench.validate_data --episodes data/episodes` → **30/30 PASS**; `--selftest` → 7/7 (bands do not enter the gate). |
| independent re-derivation | deadband p99.7 recomputed over **two disjoint seed sets** (700–711; and 950–969 × 60 min, 20 runs). bed 2.06 / 1.38 / 1.71; ms 0.60 / 0.37 / 0.46; feed 0.46 / 0.39 / 0.44; pressure 0.16 / 0.14 / 0.12; level 0.022 / 0.018 / 0.025. Rel. spread 16–48 % (bed/ms widest — a p99.7 of a correlated-drift-dominated tail over ~2 500 ticks is inherently noisy). The 900–911 value sits at the **top** of the range for bed/ms, i.e. mildly conservative (larger deadband → higher FLAT fraction, the safe direction). All three sets agree the bed deadband is O(1–2 °C/min), ~50–70× the old 0.03. |
| mutation check (tests) | set `checks.bands.bed_temp_avg` back to the old `[0.03, 0.15, 0.5]` → `test_checks.py` **16 passed / 4 failed**: "healthy-plant bed drift (0.5 °C/min) reads FLAT", the SLOW and MED checks, and the `BAND_EDGES`-mirrors-config check all fail. Restored → 20/20. |

## Direction checks

The bands carry no physical sign; `direction_and_band` returns UP/DOWN from the
slope sign, unchanged. The relevant check is *does a fault that genuinely moves
a tag now produce the band its PDF case signature expects*:

| case triple | fault that should produce it | measured post-onset 10-min `|slope|` (p90 / max) | band produced | OK? |
|---|---|---|---|---|
| RCA-01 `drum_level [DOWN, FAST]` | family A FCV seizure | 2.18 / 3.87 %/min | **FAST** (hi 0.37) | **OK** — clean `drum_level|DOWN|FAST` at 0.29–0.60 persistence on A01/A02/A05/A06 |
| RCA-16 `feed_water_flow [DOWN, FAST]` | family A BFP suction | 0.39 / 1.77 TPH/min | SLOW at best (med needs 2.8) | **FAIL** — see *Disagreements* 1 |
| RCA-07 `bed_temp_avg [UP, FAST]` | family D high-CV coal | 2.22 / 4.27 °C/min | SLOW (D03) / **FLAT** (D01, long ramp) | **FAIL** |
| RCA-11 `feed [UP, MED]`, `bed [DOWN, MED]`, `p [DOWN, SLOW]` | family B tube leak | feed 0.27 / 0.56; bed 0.79 / 1.81; p 0.02 / 0.037 | feed SLOW; bed **FLAT**; p **FLAT** | **FAIL** — RCA-11 retained only via `water_balance\|SURPLUS\|MED` (not slope-banded) |
| RCA-14 `bed [DOWN, FAST]`, `p [DOWN, FAST]`, `steam [DOWN, MED]` | family C feeder trip | bed 2.42 / 7.88; p 0.92 / 2.27; steam 0.53 / 1.63 | bed SLOW; p **MED**; steam SLOW | partial (p only) |

## Coverage analysis (re-run)

### RCA-01 rank — the headline

Aggregated post-onset signature (persistence ≥ 0.15 of ticks), real
`CaseLibrary.match` against the deployed 13-case library:

| episode | Stage 5 (old bands) | **Stage 6 (new bands)** | live mock T2 top-1 (Stage 5 → Stage 6) |
|---|---|---|---|
| `ep_A01_fcv_seize` | rank 3, raw n/a | **rank 1/13, raw 0.22** (RCA-16 0.17) | 0.13–0.23 → **0.509** |
| `ep_A02_fcv_seize_fast` | rank 8 | **rank 1/13, raw 0.33** | → **0.609** |
| `ep_A05_fcv_caught` | rank 1 | **rank 1/13, raw 0.23** | → 0.333 |
| `ep_A06_fcv_seize_repeat` | rank 7 | **rank 1/13, raw 0.61** | → **0.774** |

All four FCV episodes now retrieve RCA-01 at rank 1. The mechanism: the FCV
level collapse produces `drum_level|DOWN|FAST` (0.29–0.60 persistence), which
matches RCA-01's headline triple exactly, and the ~8 noise triples per tick
that previously diluted every score are gone. **No case signature and no FLAT
weight was changed** — this is entirely the deadband fix. (`stage5` disagreement
2, "retrieval still limited by the noise floor / FLAT weight is not the cause",
is now resolved: the noise floor *was* the deadbands.)

### Cluster table (18 case signatures, moving triples, FLAT ignored)

Unchanged from `stage5_case_library.md` item 2 — the clusters are a property of
the case signatures, which were not touched. Pairwise re-run confirms:

| cluster | members | (tag,dir)-Jaccard | shared moving triples | six-tag separator |
|---|---|---|---|---|
| **T** total heat loss | RCA-06 ≈ RCA-08 ≈ RCA-14 ≈ RCA-18 | **1.00** all pairs; RCA-14/18 moving-sig **byte-identical** | `bed DOWN`, `drum_pressure DOWN`, `steam_flow DOWN`, `ms_temperature DOWN`, `energy_balance HEAT_SHORT` | magnitude band only (non-tags: VFD phase-loss codes / O2 / PA-to-coal / compartment bed spread) |
| **W** water-side deficit, level falling | RCA-01 ≈ RCA-16 | 0.50 (moving-J 0.50) | `drum_level DOWN`, `water_balance DEFICIT` | `feed_water_flow` FLAT (RCA-01) vs DOWN (RCA-16) — **not reliably produced**, see below |
| **L** water ingress, level held | RCA-11 ≈ RCA-12 ≈ CBD-left-open | ~0.7 (RCA-11 vs RCA-12) | `feed_water_flow UP`, `drum_level FLAT`, `water_balance SURPLUS` | `bed_temp_avg` DOWN (RCA-11) vs FLAT — now **never produced** (bed FLAT for all B episodes) |
| **S** swell | RCA-02 ≈ RCA-05 | 0.60 | `drum_level UP`, `drum_pressure UP`, `steam_flow DOWN` | `ms_temperature DOWN FAST` (RCA-02); no episode |
| **∅** invisible on six tags | RCA-09 ≈ RCA-10 ≈ RCA-15 ≈ RCA-17 | 1.00 (all empty moving sig) | — | none — go-observe only |

**Cluster W is now sharper and that is a problem the retune reveals, not
causes.** With the noise gone, `ep_A03_bfp_suction` (true case RCA-16) retrieves
**RCA-01 at raw 0.70 vs RCA-16 at 0.42** — both cluster-W cases match its
`drum_level|DOWN|FAST` + `water_balance|DEFICIT`, and RCA-01 (fewer total
triples) wins the Jaccard. A03 produces no persistent `feed_water_flow` triple
at all (feed slope maxes in SLOW), so the FLAT-vs-DOWN separator that
distinguishes RCA-01 from RCA-16 is unavailable. This is exactly the
"retrieve the cluster, not the case" limit `stage5` recommended a metric change
for.

### Aggregate mock Q2

`Q2_top1 0.334 → 0.132`, `Q2_top3 0.505 → 0.188` (17 scored episodes). Net of:

- **up:** RCA-01 / cluster-W episodes (A01/A02/A05/A06) — live T2 0.13–0.23 → 0.33–0.77.
- **down:** every slow-fault episode. `ep_B0*` (RCA-11) live T2 0.40–0.68 → **0.0**;
  `ep_C02` (RCA-14) 0.30 → 0.01; `ep_D01` (RCA-07) → 0.0 (D03 still 0.0 top-1 /
  0.625 top-3); `ep_C0*` → 0.0.

The slow-fault matches under the old bands were **noise-driven coincidences**:
the old `bed_temp_avg` FAST edge was 0.5 °C/min against a healthy 10-min-slope
p99.7 of 2.06, so healthy bed wander *alone* produced `bed_temp_avg|UP|FAST`,
which happened to match RCA-07. Removing that also removes the coincidental hit.
The retune trades an inflated, noise-propped Q2 for a truthful signature.

## Constants introduced

| symbol | value | provenance | range | affects |
|---|---|---|---|---|
| `checks.bands.<tag>[0]` (deadband) | level 0.022, feed 0.46, steam 0.46, pressure 0.16, bed 2.1, ms 0.6 | **FITTED** — p99.7 of the no-fault 10-min `|slope|` over seeds 900–911 (Stage-4 method) | ±16–48 % across disjoint seed sets (see re-derivation); the tail p99.7 is seed-noisy for bed/ms | which tick slopes enter the signature as movement vs FLAT → every retrieval score |
| `checks.bands.<tag>[1:3]` (slow/med, med/fast) | each tag's old `lo/dead` (5–6×) and `hi/dead` (16.7–20×) × the new deadband | **DERIVED** from the deadband (the old edges were themselves deadband multiples — "scaled to the old deadbands") | ratio fixed by the old table; the *scale* moves with the deadband | which of SLOW/MED/FAST a movement triple gets → exact-triple case match |

No simulator constant, L1 check threshold, `load_coef`, episode severity,
ground-truth format, case signature or FLAT weight was changed.

## Numbers that changed

| quantity | old | new | downstream |
|---|---|---|---|
| `l1_symbolize.BAND_EDGES` | invented `(0.03,0.15,0.5)`-family literals | config `checks.bands`, deadbands = no-fault p99.7 | `build_signature` → `Retriever` → T2/T4/T6 |
| no-fault FLAT fraction (bed / feed / pressure / ms) | 0.065 / 0.275 / 0.258 / 0.324 | **0.998 / 0.997 / 0.997 / 0.997** | signature truthfulness |
| healthy-plant movement triples / episode | 7.71 | **0.62** | weighted-Jaccard ceiling |
| RCA-01 rank, 4 FCV episodes (aggregated match) | 3 / 8 / 1 / 7 | **1 / 1 / 1 / 1** | T2 for family A |
| mock `Q2_top1` / `Q2_top3` (17 eps) | 0.334 / 0.505 | **0.132 / 0.188** | headline retrieval metric — see disagreement 1 |
| `Q1` / `Q3` / `Q4` / `Q5` / `S7` | 0.743 / 1.0 / 0.537 / 0.91 / 0.0 | **unchanged** (Q4 0.537/0.779 same) | — |

## Disagreements recorded, not resolved

1. **The SLOW/MED/FAST labels in the PDF-transcribed case signatures are
   unreachable for every slow-developing fault (families B, C, D, E).**
   (Stop-rule-2 hit — a derived consequence disagrees with the case
   study–sourced signatures by more than a band.) Measured post-onset 10-min
   `|slope|` maxima vs the new edges:

   | tag | fault (family) | max `|slope|` | new deadband | new slow/med | band reached |
   |---|---|---|---|---|---|
   | `bed_temp_avg` | B tube-leak quench | 1.81 | 2.1 | 10.0 | **FLAT** |
   | `bed_temp_avg` | C / D bed excursion | 7.88 / 4.27 | 2.1 | 10.0 | SLOW |
   | `feed_water_flow` | A BFP / B leak | 1.77 / 0.56 | 0.46 | 2.8 | SLOW |
   | `drum_pressure` | B leak sag | 0.037 | 0.16 | 0.8 | **FLAT** |
   | `drum_pressure` | C heat-short sag | 2.27 | 0.16 | 0.8 | MED |

   Only `drum_level` (fast level excursions → RCA-01/16 cluster) and family-C
   `drum_pressure` produce a band above SLOW. `RCA-07` needs `bed UP FAST`;
   `RCA-11` needs `feed UP MED` + `bed DOWN MED`; `RCA-14` needs `bed DOWN FAST`
   + `p DOWN FAST` — **none producible**. The affected cases now retrieve on the
   **balance pseudo-triples** (`water_balance|SURPLUS|MED` 0.33–0.86 for family
   B; `energy_balance|HEAT_SHORT` for family C) which are *not* slope-banded and
   are unaffected — offline aggregated rank for RCA-11 stays 1–3/13, but live
   per-tick T2 collapses to 0.0 because a lone pseudo-triple loses to the
   all-FLAT RCA-15 in the k=4 retrieval.

   This is **not** created by the retune. The old edges "detected" these faults
   only by sitting below the plant's true noise floor — the same edge value
   fired on healthy wander (7.71 noise triples/episode). The retune makes the
   symbolizer honest and the honesty exposes that the six-tag *slope-band*
   vocabulary aligns with the PDF signatures only for fast level excursions.
   Same species as the Stage-4 family-E finding (family E is not
   slope-detectable) — now generalised to B/C/D.

   **Not resolved by tuning.** Re-scaling the edges downward to make the fault
   triples land in MED/FAST would be choosing the symbolizer against the case
   signatures — the mirror of what the task forbids on the signature side. See
   *Blocked*.

2. **The deadband p99.7 is seed-noisy for `bed_temp_avg` and `ms_temperature`
   (±39–48 % across disjoint seed sets).** The distribution is
   correlated-drift-dominated (Stage-4 finding: the no-fault bed spread is ~real
   OU load + process wander, ~1 700× the emit-noise SE), so its extreme tail
   over ~2 500 ticks is not tightly estimated. The config uses the 900–911
   value (2.06 / 0.60), which is the **largest** of the three sets — mildly
   conservative. A ±40 % move in the bed deadband (1.4–2.1) does not change any
   conclusion: family C/D bed faults still cap at SLOW, family E/D01 still FLAT.
   Recorded, not resolved — a tighter estimate needs many more no-fault runs
   than the Stage-4 protocol generates.

## Blocked / needs a decision

1. **What to do about the dead SLOW/MED/FAST bands in the case signatures
   (disagreement 1).** The magnitude bands in the PDF-transcribed signatures for
   RCA-07/11/14/16/18 are now unproducible. Options for the advisor:
   - **(a)** re-band the case signatures against the measured fault-slope
     percentiles (e.g. RCA-07 `bed [UP, SLOW]`, RCA-11 `feed [UP, SLOW]`). This
     **touches case signatures** and is explicitly out of scope for this task —
     needs sign-off, and a decision on whether the PDF's qualitative "rapid" /
     "gradual" wording maps to our SLOW at all.
   - **(b)** drop magnitude bands from `CaseLibrary.match` — compare on
     `(tag, direction)` + the balance pseudo-triples only. A small, clean
     L3-matcher change; makes the six-tag vocabulary match its actual
     resolving power. Recommended for consideration.
   - **(c)** accept it: rely on the aggregated post-onset signature (offline
     rank is still good for RCA-01/11) + the pseudo-triples + the Stage-5
     recommended **cluster-top-1 / discriminator-accuracy** metric, and treat
     live per-tick top-1 as a known-capped diagnostic. No further change.

   Chosen here: **(c)** — no code change beyond the retune, consistent with the
   Stage-5 metric recommendation. But **(b)** is cheap and principled and the
   advisor should weigh it.

2. **`Q2_top1` fell 0.334 → 0.132 on mock.** If the headline metric stays
   `Q2_top1`, the retune looks like a regression; if it moves to
   (cluster-top-1, discriminator-accuracy) as `stage5` recommended, the picture
   is RCA-01 fixed + slow faults correctly reading "cluster only". This is the
   same advisor decision as `stage5` *Blocked* item 2, now with more evidence.

## What I could not verify

- **Whether the SLOW band should exist at all for our vocabulary.** The old
  comment claimed "RCA-04 tube leak, RCA-09 fouling drift" need it; RCA-09 is
  all-FLAT and RCA-04 has no episode. With the new edges, the only fault triples
  landing in SLOW are family C/D bed and family A/B feed — and for those the
  case signatures ask for MED/FAST. SLOW may now be a band nothing uses on
  either side. Not removed (that is a signature-vocabulary decision).
- **The live-backend effect.** All Q2 numbers here are mock (re-ranks retrieved
  cases, no reasoning). Whether a reasoning backend, handed the corrected
  retrieval set, recovers the slow-fault diagnoses from the pseudo-triples +
  notes + records is not measurable on mock.
- **The `drum_pressure` deadband under a pressure-setpoint OU.** `stage4`
  disagreements 6–7 note our drum pressure has a fixed setpoint (sd 0.12 vs
  fingerprint 0.77). If a later stage adds the slow setpoint OU, the
  `drum_pressure` deadband (0.16) will rise and family-C's `p DOWN MED` (its one
  surviving above-SLOW triple) may fall back to SLOW. Flagged so it is not
  closed silently.
