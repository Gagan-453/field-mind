# FieldMind simulator - constant derivations

Every constant in `data/generator/sim.py` and `data/physics/` is one of:

| tag | meaning |
|---|---|
| **DERIVED** | from geometry / thermodynamics; the algebra is shown here |
| **CITED** | to `docs/FieldMind_Boiler_Agent_Plan.pdf` or a case-study PDF, with the section |
| **FITTED** | to `data/reference/fingerprint.json`, with the JSON path and method |
| **STANDARD** | to a named standard, with a specific clause / equation number |
| **ASSUMED** | plausible value, no citation checked; a range and the affected quantity are given |

`STANDARD` is used only where a clause number is actually verifiable (IAPWS-IF97).
Anything that would need a paywalled or unverified clause is **ASSUMED** instead.

Reproduce every headline number in this file with:

```
python -m data.physics.steam_tables      # IF97 self-test + operating-point dump
python -m data.physics.geometry          # geometry self-test + K, inventory, feed max
```

Both run their self-tests on import; a wrong coefficient fails loudly there.

---

## 1. Operating point

| quantity | value | provenance |
|---|---|---|
| main steam flow (MCR) | 67 t/h | **CITED**: Plan section 1; RCA Case 1 section 1 |
| drum pressure, gauge, nominal | 66 kg/cm2(g) | Plan section 1 gives 67 at MCR; the simulator `NOMINAL` runs 66 (normal 1 kg/cm2 operating margin below MCR). `geometry.NOMINAL_DRUM_KGFCM2G = 66.0` so the config K matches the simulator's nominal state. |
| main steam temperature | 495 degC | **CITED**: Plan section 1; RCA Case 1 section 1 |
| continuous blowdown, nominal | 1.0 t/h | **CITED**: Plan section 4.2 water-balance worked example uses `blowdown = 1.0` |
| tick period | 30 s | **CITED**: Plan section 3.2 |
| raw sample period | 5 s | **CITED**: Plan section 3.2; corroborated **FITTED**: `fingerprint.json.sampling.dt_seconds_median = 5.0` |

Unit conversion `kg/cm2(g)` <-> `MPa`:

- **DERIVED** from **STANDARD** `1 kgf := 9.80665 N` (standard gravity, ISO 80000-4)
  => `1 kgf/cm2 = 98066.5 Pa` exactly => `1 MPa = 10.197162129779 kgf/cm2`.
- `fingerprint.json._pressure_conversion` uses the same number but is **not its
  source**, so this is not marked CITED to the fingerprint.
- Immaterial note, recorded so it is not chased later: the fingerprint converted
  the reference boiler's pressure MPa->kg/cm2 without subtracting atmosphere, so
  its "99.6 kg/cm2(g)" is about 1 unit high if the source reading was absolute.
  Affects no calibration in this project.

---

## 2. Steam properties - IAPWS-IF97 (`steam_tables.py`)

**STANDARD**: IAPWS-IF97, *Revised Release on the IAPWS Industrial Formulation
1997 for the Thermodynamic Properties of Water and Steam* (IAPWS R7-97(2012)).

| region | used for | clause | coefficients |
|---|---|---|---|
| Region 1 | saturated / compressed liquid: feedwater, rho_f, h_f | Eq. 7 | Table 2, 34 terms (ni, Ii, Ji) |
| Region 2 | saturated / superheated vapour: main steam, rho_g, h_g | Eq. 15-17 | Table 10 ideal 9 terms, Table 11 residual 43 terms |
| Region 4 | saturation line p <-> Tsat | Eq. 30-31 | Table 34, 10 terms (ni) |

Specific gas constant `R = 0.461526 kJ/(kg K)` - **STANDARD**: IF97 Table 1.

Region 3 (near-critical) is **not implemented**; the module must not be called
above about 22 MPa. The whole operating envelope is 55-75 bar -> Regions 1, 2, 4.

### Self-test anchors (STANDARD: IF97 published verification values)

Run on import (`_self_test`), relative tolerance 1e-7 (1e-6 for Region 4):

| check | expected | IF97 source |
|---|---|---|
| Tsat(10 MPa) | 584.149488 K | Table 35 |
| Tsat(0.1 MPa) | 372.755919 K | Table 35 |
| Tsat(1 MPa) | 453.035632 K | Table 35 |
| psat(300 K) | 0.00353658941 MPa | Eq. 30 verification |
| psat(500 K) | 2.63889776 MPa | Eq. 30 verification |
| psat(600 K) | 12.3443146 MPa | Eq. 30 verification |
| Region 1 (3 MPa, 300 K) | v = 1.00215168e-3, h = 115.331273 kJ/kg, s = 0.392294792 | Table 5 |
| Region 1 (80 MPa, 300 K) | v = 9.71180894e-4, h = 184.142828 kJ/kg | Table 5 |
| Region 1 (3 MPa, 500 K) | v = 1.20241800e-3, h = 975.542239 kJ/kg | Table 5 |
| Region 2 (3.5 kPa, 300 K) | v = 39.4913866, h = 2549.91145 kJ/kg, s = 8.52238967 | Table 15 |
| Region 2 (3.5 kPa, 700 K) | v = 92.3015898, h = 3335.68375 kJ/kg | Table 15 |
| Region 2 (30 MPa, 700 K) | v = 5.42946619e-3, h = 2631.49474 kJ/kg | Table 15 |

The (30 MPa, 700 K) check is the **only** one that exercises the high-Ii
residual terms (contribution scales as pi^24). During development a transcription
error in the last residual term (Ii=24, Ji=58: `-0.94369707241210e-6` written as
`e-16`) passed every other check and failed only this one - keep it.

### Saturated-line property approximation

`sat_liquid(p)` / `sat_vapour(p)` evaluate Region 1 / Region 2 at `(p, Tsat(p))`.
The IF97 region-boundary inconsistency this introduces is **below 0.02 % in h** -
under the simulator's measurement noise. Recorded, not corrected.

### Values at the operating point (`python -m data.physics.steam_tables`)

| p (kg/cm2g) | Tsat (degC) | rho_f (kg/m3) | rho_g (kg/m3) | h_f (kJ/kg) | h_g (kJ/kg) | h_fg (kJ/kg) |
|---|---|---|---|---|---|---|
| 55 | 269.91 | 767.61 | 28.03 | 1184.63 | 2789.77 | 1605.14 |
| 66 | 281.61 | 747.40 | 34.06 | 1245.11 | 2777.94 | 1532.83 |
| 67 | 282.60 | 745.62 | 34.62 | 1250.32 | 2776.74 | 1526.42 |
| 72 | 287.38 | 736.84 | 37.47 | 1275.73 | 2770.43 | 1494.70 |

Main steam `h(66 kg/cm2g, 495 degC) = 3404.22 kJ/kg`;
feedwater `h(70 bar, 150 degC) = 636.30 kJ/kg`.

**Independent cross-check of Tsat** (different method than the code's IF97
Eq. 31): linear interpolation of a coarse published saturation table between
6.5 MPa (280.86 degC) and 7.0 MPa (285.83 degC) to 6.574 MPa abs gives about
281.6 degC, matching the IF97 value 281.61 degC.

---

## 3. Steam-drum geometry and the water-balance constant K (`geometry.py`)

### 3.1 The old value was not a source

`sim.py` asserted `K_LEVEL = 0.22 %/min per TPH` with no derivation. It is **not**
reproduced here. Reconciling drum dimensions to hit 0.22 and then calling the
result DERIVED would launder a guess:

- 0.22 needs a **1.20 m** level-transmitter span on this drum
  (full-span water volume 3.803 m3, computed by the module), or a **22.5 m2**
  free surface at the 0.45 m span (a 17 m long drum). Neither is a real bi-drum.
- Real drum level-transmitter spans are **300-600 mm**.

### 3.2 Drum dimensions - ASSUMED

| symbol | value | range | provenance |
|---|---|---|---|
| `DRUM_ID_M` | 1.30 m | 1.1-1.5 m | **ASSUMED**, AFBC bi-drum design practice for a 60-70 t/h unit; K prop 1/ID |
| `DRUM_LENGTH_M` | 6.50 m | 5.5-8.0 m | **ASSUMED**, tangent-to-tangent; K prop 1/L |
| `LEVEL_SPAN_M` | 0.45 m | `LEVEL_SPAN_RANGE_M = (0.30, 0.60)` | **ASSUMED**, level-transmitter calibrated span, NWL +/- span/2; K prop 1/span |
| `CIRCULATION_RATIO` | 8 | 6-12 | **ASSUMED**, natural circulation; used only to sanity-bound circuit water mass, not for K |

**The FieldMind boiler's drum dimensions are a declared benchmark parameter,
not a measured property.** The plan PDF (`docs/FieldMind_Boiler_Agent_Plan.pdf`
section 1) fixes the operating point - 67 t/h, 67 kg/cm2(g), 495 degC - but
specifies nothing about drum internal diameter, tangent-to-tangent length or
level-transmitter span. The three values above were chosen to be plausible for
the class; they are **inputs to the benchmark, not findings from it**, and every
number that depends on them inherits that status.

### 3.3 Derivation of K(p)

Horizontal-cylinder drum; NWL (50 %) on the centreline; free-surface area at the
water line `A_s = 2*sqrt(2 r h - h^2) * L`, which at NWL is exactly `ID*L`.

```
1 t/h net inflow  = 1000/3600 kg/s = 0.277778 kg/s
volume rate       = 0.277778 / rho_f(p)                    m3/s
dV / d(level %)   = A_s * LEVEL_SPAN_M / 100               m3 per %
level rate        = volume_rate / (dV/dlevel%) * 60       -> %/min

K(p) = (1e5 / 60) / (rho_f(p) * A_s * LEVEL_SPAN_M)
```

`1e5/60 = (1000 kg/h per t/h) / (60 min/h) * (100 % per unit span)`, kept as an
exact expression (a rounded literal `1666.6667` fails the module's
volume-bookkeeping check at the 8th digit).

### 3.3a Provenance of K - DERIVED-from-ASSUMED, not DERIVED

The algebra in 3.3 is derived. The **value** it produces is not: it rests
entirely on the three ASSUMED inputs of 3.2 - `DRUM_ID_M`, `DRUM_LENGTH_M`,
`LEVEL_SPAN_M` - none of which is a measured property of any real drum. Labelling
K plain **DERIVED** oversells it. Its honest provenance is **DERIVED-from-ASSUMED**:
derived algebra, assumed inputs.

Propagating the full declared ranges (ID 1.1-1.5 m, L 5.5-8.0 m, span
0.30-0.60 m) through `K = (1e5/60) / (rho_f * ID * L * span)` at
`rho_f(66 kg/cm2(g)) = 747.40 kg/m3`:

```
K_min  (ID 1.5,  L 8.0, span 0.60) = 1666.667 / (747.40 * 12.00 * 0.60) = 0.310
K_nom  (ID 1.30, L 6.50, span 0.45)                                     = 0.586
K_max  (ID 1.1,  L 5.5, span 0.30) = 1666.667 / (747.40 *  6.05 * 0.30) = 1.229
```

**Uncertainty on K across the declared dimension ranges: 0.31 - 1.23 %/min per
t/h - a 4x band.** The nominal 0.586 is one point inside that band, not a
determined quantity. (`geometry._self_test` asserts only the narrower span-only
sub-range 0.44-0.88; the 0.31-1.23 figure is the honest full band and is
recorded here.)

### 3.4 Result

| quantity | value | note |
|---|---|---|
| A_s at NWL | 8.450 m2 | = ID*L |
| rho_f at 66 kg/cm2(g) | 747.40 kg/m3 | IF97 |
| **K (nominal)** | **0.5864 %/min per t/h** | **DERIVED-from-ASSUMED** (3.3a); 2.67x the old 0.22 |
| K at 55 / 72 kg/cm2(g) | 0.5710 / 0.5948 | K is pressure-dependent through rho_f |
| K band, full declared ranges (ID, L, span) | **0.31 - 1.23** | **4x band**; nominal is one point in it (3.3a) |
| K band, span only (`LEVEL_SPAN_RANGE_M`) | 0.440 - 0.880 | computed in `_self_test` |

**Independent cross-check** (through physical volumes, not the K expression):
at 66 kg/cm2(g), 1 t/h = 16.667 kg/min = 0.022299 m3/min; 1 % of span =
8.45 * 0.45 / 100 = 0.038025 m3; K = 0.022299 / 0.038025 = **0.5864**.

### 3.5 Approximations, stated

- `K_level()` uses A_s **at NWL regardless of actual level**. The water-line
  chord narrows about 2 % at 20 % level (`chord @ 20% vs NWL = 0.978x`), so the
  true K is mildly level-dependent; the fixed nominal value used by the L1
  check is a stated approximation.
- The simulator evaluates `K_level(p)` every tick (pressure-dependent); the L1
  water-balance check (`configs/base.yaml`) uses the single nominal value.

### 3.6 Consequence - water side is about 2.7x faster (NOT re-tuned here)

`configs/base.yaml checks.rates.drum_level` (0.5 %/min over 3 min) and the
`episode_build.state_timeline` DEVIATION band were tuned against the old K.
They are **not** changed in this stage. The before/after report shows family A
and family B reaching their thresholds about 2.7x sooner.

### 3.7 OPEN DISCREPANCY - the RCA over-determines K, and geometry disagrees

**This is an advisor question, not a settled point.**

RCA Case 1 section 2.1, verbatim:

> T-0:00 - Level 50%, steam flow 60 TPH, feed flow 60 TPH, stable.
> T+0:12 - Level drifting down at approx 1% per minute; feed flow reads 4-5 TPH
>          less than steam flow (persistent negative mismatch).
> T+0:25 - Drum level Low alarm at 20%; FCV shows 100% demand, no further
>          increase in feed flow.

The rate ("approx 1% per minute") and the deficit ("4-5 TPH less than steam")
are stated **for the same instant**, T+0:12. Taken together they pin K
empirically:

```
implied K (rate / deficit)                 = 1.0 / 4.5   = 0.222
implied K (50%->20% over T:00..T+0:25)     = 1.2 / 4.5   = 0.267
our geometry K                                            = 0.586
```

So our derived K is **2.2x to 2.6x** a documented event. And no plausible
bi-drum geometry closes the gap: K = 0.22 at a 0.45 m span needs a 22.5 m2 free
surface, i.e. a 17 m long drum; at a real length it needs a 1.2 m level span,
double the top of the assumed range.

**Candidate explanations (unresolved):**

1. The RCA is a "representative composite" (its own section 3 note). "approx
   1%/min" and "4-5 TPH" may be independently rounded field observations, not a
   matched pair - the timeline is itself slightly inconsistent (50%->20% in
   25 min is a 1.2 %/min *average*, not 1.0).
2. Three-element control recovery: the *instantaneous* valve-position deficit is
   4-5 TPH, but the controller keeps clawing feed back, so the *effective*
   time-averaged deficit driving the level is smaller than 4-5 TPH.
3. The RCA drum's level transmitter is calibrated on a wider span than 0.45 m.

**Choice made here, with its cost stated:** we preserve the derived geometry and
calibrate the later severity-tuning step to match the RCA *rate*, which at our K
needs a deficit of about **2.3 t/h** - roughly **half** the 4-5 t/h the RCA
records. We are choosing the rate over the deficit. This disagreement with the
recorded deficit is **not resolved**; it is carried to the advisor.

```
time_to_trip = 40 %span / (K * net_deficit_t/h)          [50 % -> 10 % trip]

  ep_A01 now:  eff 0.77 -> feed cap 0.77*81.6 = 62.8 -> deficit 5.25 t/h
               t_trip = 40 / (0.586 * 5.25) = 13.0 min
  RCA rate ~1 %/min:  deficit ~= 1.0 / 0.586 = 1.7 t/h  (feed_valve_eff ~= 0.81)
  midpoint target for tuning: deficit ~2.3 t/h, feed_valve_effectiveness ~= 0.805
```

Family A visibly trips at about 13 min in this stage's report. Driver
severities are **not** changed in this stage.

### 3.7a Advisor question - two measured numbers settle both the band and the discrepancy

The 4x uncertainty band on K (3.3a) and the 2.2-2.6x disagreement with RCA Case 1
(3.7) are **the same question asked from two directions**, and one answer
probably settles both:

> **Obtain, from the case-study plant, (a) the drum-level transmitter's
> calibrated span and (b) the steam-drum general-arrangement (GA) drawing
> giving internal diameter and tangent-to-tangent length.**

- The **calibrated span** is the single largest lever on K (`K prop 1/span`),
  currently ASSUMED 0.45 m over a 0.30-0.60 m range. RCA Case 1 can only be
  reconciled with our geometry at a ~1.2 m span (3.7), which is off the top of
  that range - so either the assumed span is wrong or the RCA rate/deficit pair
  is not a matched observation. A measured span decides it.
- The **GA drawing** fixes `DRUM_ID_M` and `DRUM_LENGTH_M` (ASSUMED 1.30 m x
  6.50 m), which set the other two factors in `K prop 1/(ID*L*span)`.

With all three measured, the 0.31-1.23 band in 3.3a collapses to a point, K's
provenance moves from **DERIVED-from-ASSUMED** to **DERIVED**, and the RCA
discrepancy either resolves or is confirmed as a rounding artefact in the
composite. Until then both are carried, unresolved.

### 3.8 Feed valve / pump maximum flow

`feed_valve_max_tph()` = `(NOMINAL_STEAM_TPH + NOMINAL_BLOWDOWN_TPH) *
FEED_SIZING_MARGIN` = `(67 + 1) * 1.20` = **81.60 t/h**.

- `FEED_SIZING_MARGIN = 1.20` - **ASSUMED** (range 1.10-1.25), feed-pump / valve
  sizing practice: MCR flow plus three-element-control authority. Affects how
  hard the feed controller can push before it saturates.
- Replaces the old bare `FEED_VALVE_MAX_TPH = 82.0`. Not reverse-engineered from
  it, though note `68 * 1.206 = 82.0`, so the old literal was itself consistent
  with a 20 % margin.

---

## 4. Energy balance and combustion  *(coefficients filled during the `sim.py` rewrite)*

Structure (SI internally):

```
Q_fuel     = m_coal * GCV * eta_boiler                     [W]
Q_steam    = W_steam * (h_ms(p,T_ms) - h_feed(p,T_feed))   [W]   h from steam_tables
Q_evap     = W_steam * h_fg(p)                             [W]
dp/dt      = (Q_absorbed - Q_evap - Q_leak) / (V_steam * (du/dp)_sat)
```

| constant | intended provenance |
|---|---|
| steam duty at MCR about **51.5 MW** | **DERIVED**: `67 t/h * (3404.22 - 636.30) kJ/kg` = `18.61 kg/s * 2767.92 kJ/kg` = 51.5 MW. Independent of any fitted gain. |
| coal GCV base 3400 kcal/kg | **ASSUMED** (range 3000-4200, Indian washery-reject + imported blend). Tied to `coal_cv_factor`; matches `notes_gen.py` `base_cv`. Sets coal mass flow magnitude only. |
| boiler efficiency `eta` = 0.85 | **ASSUMED** (range 0.80-0.87, AFBC on washery-reject). Sets `m_coal` and the energy-balance gain magnitude. |
| ultimate analysis (C/H/O/S/ash/moisture) | **ASSUMED** (Indian washery-reject blend; each fraction with a range). Stoichiometric air is then **DERIVED**. |
| pressure integrator gain | **DERIVED** from `V_steam` (drum steam-space volume, from `geometry`) and `(du/dp)_sat` (from `steam_tables`). Replaces the old `PRESS_GAIN = 4.0`. |
| bed / ms first-order lag tau | see section 6 |

`fuel_availability` stays a `min()` cap on firing (family C mechanism);
`coal_cv_factor` scales GCV (family D); `primary_air` shifts the excess-air /
bed-temperature relation (family D low-PA).

---

## 5. Dissolved-solids balance and boiler-water conductivity

### 5.1 The balance and its units

```
dm_solids/dt = c_fw * W_feed  -  c_bw * (W_blowdown + W_leak)     [kg/s]
c_bw          = 1e6 * m_solids / M_bw(level, p)                    [ppm, mg/kg]
kappa_bw      = c_bw * K_US_PER_PPM                                [uS/cm]
```

`M_bw(level, p)` = `geometry.boiler_water_inventory_kg` = drum water (varies with
level) + circuit water (about fixed).

**Conductivity <-> TDS convention (issue-4 fix).** The standard dilute
NaCl-equivalent relation is `TDS[ppm] ~= 0.55 * EC[uS/cm]`, i.e.
`EC ~= 1.8 * TDS[ppm]`. So `K_US_PER_PPM = 1.8` and `kappa = c_bw * 1.8`
(**not** `c_bw * 0.5`). **ASSUMED**, range 1.4-2.0.

| constant | value | provenance |
|---|---|---|
| `M_bw` at NWL | 10 224 kg | **DERIVED** drum half-volume * rho_f = 3 224 kg, **+ ASSUMED** `CIRCUIT_WATER_MASS_KG = 7000` (range 5000-11000; lower bound sane vs `CIRCULATION_RATIO * (67e3/3600) * ~45 s ~= 6.7 t`) |
| `M_bw` at 20 % level | 9 378 kg | **DERIVED**; only -8.3 % vs NWL |
| `K_US_PER_PPM` | 1.8 uS/cm per ppm | **ASSUMED** (range 1.4-2.0), NaCl-equivalent |
| feedwater conductivity `kappa_fw` | 12 uS/cm | **ASSUMED** (range 6-18). Elevated for a small captive plant with imperfect condensate polishing. Sets the absolute kappa level, not the trend direction. |
| nominal cycles of concentration | 68 | **DERIVED**: `W_feed / W_blowdown = (67 + 1) / 1` |
| **nominal boiler-water conductivity** | **816 uS/cm** (c_bw 453 ppm) | **DERIVED** from the two rows above: `12 * 68`. |
| normal control band | 400-1500 uS/cm | **ASSUMED**; the 816 nominal sits inside it. IS 10496 is **not** cited - its clause text could not be verified offline. A later stage with document access may promote this to CITED with a clause number. |

All three sections (5.1, 5.3, 8) now use `kappa_fw = 12` -> nominal
`kappa_bw = 816 uS/cm`.

### 5.2 Why one ODE gives both Case 1 and Case 11

At steady state `c_bw / c_fw = W_feed / (W_bd + W_leak)` - the cycles of
concentration.

- **Case 11 (family B: tube leak, or CBD stuck open):** `W_leak` (or extra
  `W_bd`) enters the denominator; the controller raises `W_feed` (dilute) to
  hold level. Cycle ratio collapses from 68 toward about 16 for a 3 t/h leak.
  `kappa_bw` **falls hard**.
- **Case 1 (family A: feed short):** the drum boils down, `M_bw` drops, so a
  near-fixed `m_solids` concentrates: `- c_bw * (dM_bw/dt) / M_bw > 0`. But
  `M_bw` only drops 8.3 % over the 50 % -> 20 % level range, and if the
  documented CBD-passing contributory is present it dilutes the other way.

### 5.3 Discriminator framing - leak-exclusion, asymmetric (RESOLVED)

Modelled trajectories (`scratchpad/ds_preview.py`, K = 0.5864, kappa_fw = 12,
K_US_PER_PPM = 1.8, logging every 30 min, one operator grab sample 15 min after
the first ALARM):

| episode | window | kappa_bw start -> end | key samples (uS/cm) |
|---|---|---|---|
| **no fault** | 90 / 240 min | 816 -> 816 (**0.0 %**) | 816 flat at every sample |
| Case 11 `ep_B01` leak 3.5 t/h | 90 min | 816 -> 568 (**-30 %**) | +30 m 776 ; +60 m 661 ; operator 755 |
| Case 11, 150-min window | 150 min | 816 -> 434 (**-47 %**) | +90 m 568 ; +120 m 493 |
| family B, CBD stuck open only (no tube leak) | 90 min | 816 -> 625 (**-23 %**) | +30 m 781 ; +60 m 696 ; operator 766 |
| Case 1 `ep_A01`, blowdown normal | 55 min | 816 -> 933 (**+14 %**) | +30 m 914 ; operator 938 |
| Case 1 `ep_A01`, **CBD ~40 % open** (documented contributory) | 55 min | 816 -> **778 (-5 %)** | +30 m 878 ; operator 857 |

**Rule (matches how the RCA uses the signal):**

- A **sustained fall** in `kappa_bw` => **family B** (tube leak *or* stuck-open
  CBD). RCA Case 11 section 6: falling conductivity "immediately excludes all
  non-leak explanations of the water imbalance."
- **Flat / rising** `kappa_bw` => **not family B**. Family A stays identified by
  feed-valve saturation + feed deficit + level fall. The concentrating signal
  (+3 to +15 %, inverting to -5 % with CBD passing) is **not** claimed as a
  positive Case 1 signature. RCA Case 1 section 6: rising conductivity "supports
  H3 only partially."

**What it does NOT do, stated so it is not over-claimed:**

1. It discriminates **family A from family B**, *not* leak from blowdown. A
   stuck-open CBD (`ep_B04`) removes boiler water at boiler-water concentration
   exactly as a tube leak does and dilutes in the same direction (-23 % vs the
   leak's -30 % above) - both are family B. Blowdown is not one of the six
   tags, so a genuine CBD change is indistinguishable from a leak on
   conductivity alone. Stated false-positive exposure.
2. It does not positively confirm Case 1.

### 5.4 The "sustained fall" threshold - DERIVED, and no-fault drift shown

**No-fault drift is exactly 0.0 %** (`ds_preview.py` "no fault" rows, 90 and
240 min): with `m_solids` initialised to its equilibrium value
`c_fw * cycles * M_bw`, and `W_feed = W_steam + W_blowdown` at steady state, the
balance holds `c_bw` constant. The only no-fault movement in a real episode is
analyser noise (+/-2 %) plus slow OU load wander nudging `W_feed`; call the
realistic no-fault band **+/-5 %**.

Family B floor, from the same runs: `kappa_bw` crosses **-10 % by about 45-50
min** and reaches -23 % (CBD only) to -30 % (3 t/h leak) by 90 min. Steeper
leaks (`ep_B02`, 6 t/h) cross -10 % sooner.

So the trigger:

> a monotone fall of **>= 10 % relative to the pre-episode baseline band,
> sustained across >= 3 consecutive 30-min logged samples**

is the smallest change a family-B event reliably produces and that no-fault
operation (0 % +/- 5 %) does not. Recorded as **DERIVED from the solids
balance**; re-checked against the regenerated family-B episodes in the
before/after report.

### 5.5 Sample cadence and source (RESOLVED)

- **Source:** an **online conductivity analyser on the CBD line, logged
  periodically** - **ASSUMED**; many AFBC captive units have one. This is *not*
  modelled as manual grab sampling: a 30-min manual lab cadence is unrealistic
  (real manual sampling is shift-based), and adopting a fake cadence to make a
  trend visible would be the same failure mode as tuning K.
- **If the modelled plant has only manual shift sampling, conductivity cannot
  serve as an in-episode discriminator at all, and the tier-C modality claim
  for the affected episodes would need rethinking.** Recorded so the assumption
  is visible.
- Pre-episode history at -24 h, -16 h, -8 h, 0 to anchor the baseline band.
- Logged samples every 30 min of episode time.
- One `operator_requested` grab sample 10-20 min (seeded jitter) after the
  first ALARM-severity condition - realistic under either sampling regime.
- Analyser / lab noise **ASSUMED** +/-2 %.

### 5.6 Format note

`records.json` gains `water_chemistry_log` (see `notes_gen.build_records`).
**The agent's retrieval layer (L3) does not yet read `records.json` - known
bug 3 in CLAUDE.md, fixed in a later stage.** The format is frozen now so the
later wiring is a plumbing change only.

---

## 6. Time constants  *(FITTED values filled during the `sim.py` rewrite + regen)*

Deterministic tag relaxation stays **fast**, per the CLAUDE.md stage-1
correction ("do NOT slow bed or ms relaxation by 30-170x"; the steam->bed
increment cross-correlation peaks at lag 0). The long autocorrelation in the
real record comes from slow **driver** drift (section 7), not slow tag
relaxation.

| tau | intended provenance |
|---|---|
| drum pressure | **FITTED**: `fingerprint.json.tags.drum_pressure.ar1.timescale_minutes = 44.53` |
| bed temperature | kept fast (minutes). The fingerprint's `bed_temp_avg.ar1.timescale_minutes = 254.9` is inherited from slow load variation, not the bed's own response - CLAUDE.md stage-1 correction. |
| main steam temperature | kept fast (minutes); `ms.ar1 = 706.7 min` likewise inherited. |

Achieved autocorrelation vs the fingerprint targets is reported after
regeneration (before/after report, verification step 5).

---

## 7. Noise and driver-drift model  *(FITTED values filled during regen)*

### 7.0 Shrink-and-swell gain `G_sw`  --  DERIVED-from-ASSUMED (sub-model 1)

`sim.py` adds a fast pressure-driven term to the indicated drum level on top of
the collapsed-liquid level from the mass balance:

```
level_swell = -G_sw * (p - p_nom)          [p in kgf/cm2(g)],  G_sw > 0
G_sw = (ALPHA_SW * V_SW_M3) / (rho_g(p_nom) * VOL_PER_PCT_M3)
       * d(rho_g)/dp|p_nom * (Pa per kgf/cm2)
```

**Structure - DERIVED.** A void volume `V_void = ALPHA_SW * V_SW_M3` seen by the
level tap holds steam whose density tracks drum pressure. On the seconds
timescale the void *steam mass* is ~constant, so
`V_void = m_void / rho_g(p)` gives `dV_void/dp = -(V_void/rho_g) * d(rho_g)/dp`,
and `dL[%] = dV_void / VOL_PER_PCT_M3`. `d(rho_g)/dp > 0` -> pressure UP
compresses the voids -> level DOWN (shrink); pressure DOWN (load increase) ->
voids expand -> level UP (swell). Sign cross-checked against RCA Case 5
("shrink then swell" on a load rejection) and Case 4 (load increase ->
"level rises on swell").

**Inputs - ASSUMED, cannot be fitted.** `fingerprint.json` has no `drum_level`
column (`FINGERPRINT.md` line 26), so neither factor of `V_void` can be fitted.

| symbol | value | range | provenance |
|---|---|---|---|
| `V_SW_M3` | 9.0 m3 | 4 - 14 m3 | **ASSUMED**: drum-span water (4.31 m3) + the void-bearing part of the ~9.4 m3 evaporator-circuit water |
| `ALPHA_SW` | 0.20 | 0.08 - 0.35 | **ASSUMED**: span-averaged void fraction (drum region ~0.03, upper risers ~0.4) |

**Result** (`python3 -m data.generator.sim`, IF97 `rho_g(66 kg/cm2(g)) = 34.06`,
`d(rho_g)/dp = 5.723e-6 kg/m3/Pa`):

| quantity | value |
|---|---|
| **`G_sw` nominal** | **0.780 %/(kgf/cm2)** |
| `G_sw` band over the ASSUMED ranges | **0.139 - 2.123** (~15x) |

Independent re-derivation: `d(rho_g)/dp` recomputed from `rho_g` at exactly
`p_nom +/- 1 kgf/cm2` (bracket ~98x wider than the code's 1 kPa central
difference) gives `G_sw = 0.780`, **0.00 % difference** - a genuine curvature
check on `rho_g(p)`.

**SCOPE - stated limitation.** `G_sw` captures **only the density effect**:
voids compressing / expanding as `rho_g` tracks `p`. It **omits the
void-fraction change driven by steaming rate** - more firing makes more bubbles
and swells the level *at constant pressure*. Verified magnitude: a 5 kg/cm2
pressure excursion gives **~3.9 % of span** from the density term modelled here,
against **10 - 20 %** typical for real swell on a large load step. So the
modelled term is plausibly the **minority contribution**. It affects **families
A and B**, where the indicated level then reads something other than true water
mass; the L1 water-balance residual absorbs the difference and must be tuned
with that in mind. A steaming-rate void term is a candidate for a later stage;
not added now because its coefficient would itself be unfittable ASSUMED.

### 7.1 Driver drift - cross-correlated Ornstein-Uhlenbeck

The multi-hour wander is produced by OU processes on the drivers, not by tag
relaxation:

| driver | tau | provenance |
|---|---|---|
| `load_demand` | 26.6 min | **FITTED**: `fingerprint.json.tags.steam_flow.ar1.timescale_minutes` |
| `heat_absorption` / `coal_cv_factor` slow terms | hours | **FITTED** to the 1 h drift horizons (`drift_by_horizon`: bed 11.5 degC, ms 5.2 degC) |

OU innovations are **cross-correlated** (shared load factor) so
`fingerprint.json.cross_tag_correlation.pearson_level` steam<->bed about **+0.87**
is reproduced. Achieved value reported after regeneration.

### 7.2 Measurement noise - white, added at emit only

Dropped from the old ad-hoc dict to the fingerprint's white-noise estimates
(`tags.<tag>.measurement_noise.hf_noise_est_2nd_diff`):

| tag | new sigma | provenance |
|---|---|---|
| `bed_temp_avg` | 0.057 degC | **FITTED** (absolute - same instrument class) |
| `ms_temperature` | 0.026 degC | **FITTED** (absolute) |
| `steam_flow` | 0.109 t/h | **FITTED** |
| `drum_pressure` | **0.019** kg/cm2 | **DERIVED** from the **FITTED** 0.028 kg/cm2 by span scaling (transmitter noise prop span; 67 / 99.6) |
| `drum_level` | 0.15 % (unchanged) | **ASSUMED** - the fingerprint has no `drum_level` column (`FINGERPRINT.md` line 26) |
| `feed_water_flow` | 0.109 t/h | **ASSUMED** - no reference column; mirrors `steam_flow` |

Noise is added to the emitted copy only; it does not feed the controllers.

---

## 8. `records.json` water-chemistry log format

See sections 5.5 / 5.6. Schema (values **computed from the section 5.1 balance**,
never hand-authored; `kappa_fw = 12` -> baseline about 816 uS/cm):

```json
"water_chemistry_log": [
  {"t": -86400, "sample": "boiler_water", "conductivity_uS_cm": 812, "source": "analyser"},
  {"t": -57600, "sample": "boiler_water", "conductivity_uS_cm": 818, "source": "analyser"},
  {"t": -28800, "sample": "boiler_water", "conductivity_uS_cm": 815, "source": "analyser"},
  {"t": 0,      "sample": "boiler_water", "conductivity_uS_cm": 816, "source": "analyser"},
  {"t": 1800,   "sample": "boiler_water", "conductivity_uS_cm": 781, "source": "analyser"},
  {"t": 2900,   "sample": "boiler_water", "conductivity_uS_cm": 766, "source": "operator_requested"}
]
```

(The in-episode values above are the family-B `CBD stuck open` trajectory from
section 5.3; a no-fault episode stays flat at about 816.)

---

## 9. Load coefficient re-fit

`configs/base.yaml checks.load_coef_degc_per_tph` is currently 2.75.

- It is **re-fitted** to the regenerated normal episodes (least-squares
  `slope(bed) vs slope(steam_flow)` over N01-N06), **FITTED** with the fit R2
  recorded.
- It is **NOT** set to the fingerprint's measured 3.90 degC/(t/h): that was a
  different boiler at 774 degC bed / 99.6 kg/cm2
  (`load_following.coefficients.bed_temp_avg.level_regression`), and CLAUDE.md's
  correction is explicit that our variability model differs.

The new value and R2 go in the before/after report and here on completion.
