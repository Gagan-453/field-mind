"""
=============================================================================
 PHYSICS-LITE BOILER SIMULATOR  (Plan §3.6)
=============================================================================

Generates the six-tag time series for one episode.

THE KEY DESIGN RULE: faults are injected at DRIVER level, never by editing a
tag afterwards. A fault sets `feed_valve_effectiveness = 0.77` and every
downstream tag then moves because the physics moves it. That is what keeps
all six tags mutually consistent, so a fault shows up as a genuine
MULTI-SIGNAL PATTERN rather than a dent in one trace.

The second key rule: GROUND TRUTH IS EMITTED BY THE GENERATOR, not written
afterwards. It knows exactly which driver it changed and when, so labels
cannot drift from the data.

Two balances must close, and the check layer relies on both:
    WATER   d(m_liquid)/dt = feed - steam - blowdown - leak         [kg/s]
            indicated level = liquid level (mass / geometry) + shrink-swell(p)
    ENERGY  pressure and bed temperature respond to heat in vs heat absorbed

INTERNAL UNITS ARE SI (kg, s, Pa, K, m3). The six emitted columns keep their
engineering units (t/h, %, kg/cm2(g), degC); conversion happens at emit.
Every constant is DERIVED / CITED / FITTED / STANDARD / ASSUMED per
data/physics/DERIVATIONS.md -- the section reference is on each line.

REWRITE STATUS (staged, per CLAUDE.md "one stage at a time"):
    [x] sub-model 1  water balance + shrink-and-swell (drho_g/dp)   -- THIS FILE
    [x] sub-model 2  energy balance: coal ultimate analysis -> stoichiometric
                     air + Dulong GCV; steam-table pressure integrator with a
                     PHYSICAL pressure capacitance e_p (NOT fitted to the
                     drum_pressure ar1 timescale); bed / ms deviation gains
                     each derived from the combustion mass/energy balance.
    [ ] sub-model 3  dissolved-solids balance
    [ ] sub-model 4  cross-correlated OU drivers + fingerprint measurement noise
The load-swing placeholder (`swing`) and the emit-noise dict are still
PRE-REWRITE, replaced in sub-model 4.

Run  `python3 -m data.generator.sim`  for self-tests, direction checks and an
independent re-derivation of the shrink-and-swell gain.

Everything here runs OFFLINE on the host. numpy is fine.
=============================================================================
"""

from __future__ import annotations

import math
import random
import warnings
from dataclasses import dataclass, field

from data.physics.geometry import (
    LEVEL_SPAN_M,
    NOMINAL_DRUM_KGFCM2G,
    boiler_water_inventory_kg,
    drum_water_volume_m3,
    feed_valve_max_tph,
    water_surface_area_m2,
)
from data.physics.steam_tables import (
    Tsat_K,
    drho_g_dp_kg_m3_per_Pa,
    h_liquid_J_kg,
    h_vapour_J_kg,
    hfg_J_kg,
    kgfcm2g_to_Pa,
    rho_f_kg_m3,
    rho_g_kg_m3,
    sat_liquid,
    sat_vapour,
)

# Nominal operating point: 67 TPH, 67 kg/cm2(g), 495 degC.
# CITED: Plan §1 / RCA Case 1 §1 (67 t/h, 495 degC). Drum pressure runs at
# NOMINAL_DRUM_KGFCM2G = 66 (1 kg/cm2 margin below MCR) so it matches the
# geometry module's nominal state -- DERIVATIONS.md §1.
NOMINAL = {
    "drum_level": 50.0, "feed_water_flow": 67.0, "steam_flow": 67.0,
    "drum_pressure": 66.0, "bed_temp_avg": 850.0, "ms_temperature": 495.0,
}

DT_S = 5.0                       # raw sample period. CITED: Plan §3.2; FITTED
                                 # fingerprint.json.sampling.dt_seconds_median.
KGPS_PER_TPH = 1000.0 / 3600.0   # exact
TPH_PER_KGPS = 3600.0 / 1000.0   # exact


# =======================================================================
#  WATER-SIDE constants  (DERIVATIONS.md §3, §7)
# =======================================================================
P_NOM_KGFCM2G = NOMINAL_DRUM_KGFCM2G                        # 66.0 ; CITED geometry
_P_NOM_PA = kgfcm2g_to_Pa(P_NOM_KGFCM2G)
_PA_PER_KGFCM2 = kgfcm2g_to_Pa(1.0) - kgfcm2g_to_Pa(0.0)   # 98066.5 Pa, exact (STANDARD)

# DERIVED (geometry): drum water volume at NWL and the m3 that one indicated
# percent of transmitter span corresponds to.  K_level(p) is exactly
# (net kg/s / rho_f) / VOL_PER_PCT_M3, so tracking mass and mapping through
# VOL_PER_PCT_M3 reproduces K without a second literal -- DERIVATIONS.md §3.4.
V_DRUM_50_M3 = drum_water_volume_m3(50.0)                  # 4.314 m3  (DERIVATIONS §3, §5.2)
VOL_PER_PCT_M3 = water_surface_area_m2(50.0) * LEVEL_SPAN_M / 100.0   # 0.038025 m3/%

# Physical clamp on the collapsed-liquid inventory: the level transmitter
# cannot read outside [0, 100] % of span, and the water balance must not
# integrate an unphysical negative / runaway mass (sub-model 3 divides by
# boiler-water inventory). Floor / ceiling = rho_f(p_nom) * drum water volume
# at the bottom / top of the transmitter span.
M_LIQ_FLOOR_KG = rho_f_kg_m3(_P_NOM_PA) * drum_water_volume_m3(0.0)     # ~1832 kg
M_LIQ_CEIL_KG = rho_f_kg_m3(_P_NOM_PA) * drum_water_volume_m3(100.0)    # ~4617 kg

# --- Shrink-and-swell gain  G_sw  [%/(kgf/cm2)]  --  DERIVED-from-ASSUMED -----
# STRUCTURE is DERIVED from d(rho_g)/dp: a void volume  V_void = ALPHA_SW * V_SW_M3
# seen by the level tap holds steam whose density tracks drum pressure. On the
# fast (seconds) timescale the void STEAM MASS is ~constant, so
#     V_void = m_void / rho_g(p)   =>   dV_void/dp = -(V_void / rho_g) * d(rho_g)/dp
# and an indicated-level increment  dL[%] = dV_void / VOL_PER_PCT_M3. Hence
#     level_swell = -G_sw * (p - p_nom)          [p in kgf/cm2(g)],  G_sw > 0
#     G_sw = (ALPHA_SW * V_SW_M3) / (rho_g(p_nom) * VOL_PER_PCT_M3)
#            * d(rho_g)/dp|p_nom * (Pa per kgf/cm2)
# Sign: d(rho_g)/dp > 0, so pressure UP -> voids compress -> level DOWN (shrink);
#       pressure DOWN (load increase) -> voids expand -> level UP (swell).
#       Cross-checked: RCA Case 5 "shrink then swell" on a load rejection (p up
#       -> shrink first); RCA Case 4 load increase -> "level rises on swell".
#
# SCOPE (stated limitation, DERIVATIONS.md §7): this captures ONLY the density
# effect -- voids compressing / expanding as rho_g tracks p. It OMITS the
# void-fraction change driven by steaming rate (more firing -> more bubbles ->
# swell at constant pressure). A 5 kg/cm2 excursion gives ~3.9 % of span from
# the density term here, against 10-20 % typical for real swell on a large load
# step -- so this is plausibly the MINORITY contribution. It affects families A
# and B, where the transmitter then reads something other than true water mass.
#
# V_SW_M3, ALPHA_SW are ASSUMED with ranges: the fingerprint has no drum_level
# column (FINGERPRINT.md line 26) so neither can be fitted. See DERIVATIONS.md §7.
V_SW_M3 = 9.0       # ASSUMED (range 4-14 m3): drum-span water (4.31 m3) plus the
                    # void-bearing part of the ~9.4 m3 evaporator-circuit water.
ALPHA_SW = 0.20     # ASSUMED (range 0.08-0.35): span-averaged void fraction in V_SW_M3
                    # (drum region ~0.03, upper risers ~0.4).


def _shrink_swell_gain(v_sw: float = V_SW_M3, alpha: float = ALPHA_SW) -> float:
    """G_sw [%/(kgf/cm2)] -- DERIVED-from-ASSUMED, see the block comment above."""
    rho_g0 = rho_g_kg_m3(_P_NOM_PA)
    drhog_dp = drho_g_dp_kg_m3_per_Pa(_P_NOM_PA)         # kg/m3 per Pa (>0)
    return ((alpha * v_sw) / (rho_g0 * VOL_PER_PCT_M3)
            * drhog_dp * _PA_PER_KGFCM2)


G_SW_PCT_PER_KGFCM2 = _shrink_swell_gain()   # ~0.78 ; band 0.14-2.12 (DERIVATIONS §7)


# =======================================================================
#  ENERGY-SIDE constants  (sub-model 2)  --  DERIVATIONS.md §4
# =======================================================================
# The rule (CLAUDE.md): every gain below is DERIVED from ONE coal ultimate
# analysis + IF97 steam-table enthalpies + a small set of ASSUMED bed / metal
# masses that each carry a range. No bare literal survives from the pre-rewrite
# `bed_target` expression.

# ---- 1. Coal: ONE ASSUMED ultimate analysis; air_st AND GCV derived from it.
# CLAUDE.md "ASSUMED inputs describing the same object must be mutually
# consistent": the old code took GCV = 3400 kcal/kg ASSUMED *directly* while a
# separately-assumed analysis implied air_st ~ 5.46 kg/kg. Dulong ties them --
# an analysis giving air_st ~ 5.46 implies GCV ~ 4000-4100, not 3400. So we fix
# ONE analysis (mass fractions, as-fired; Indian washery-reject / imported
# blend) and derive both. `_coal_consistency()` is the self-test.
COAL_ULT = {           # ASSUMED, as-fired mass fractions; ranges in DERIVATIONS §4
    "C":   0.415,      #  range 0.38 - 0.45
    "H":   0.029,      #  range 0.025 - 0.033
    "O":   0.075,      #  range 0.060 - 0.090
    "N":   0.009,      #  range 0.006 - 0.012
    "S":   0.0045,     #  range 0.003 - 0.006
    "ash": 0.335,      #  range 0.30 - 0.38
    "M":   0.1325,     #  range 0.10 - 0.16
}
_O2_MASS_FRAC_AIR = 0.2315   # STANDARD: mass fraction O2 in dry air (23.15 %)
_KCAL_PER_KJ = 1.0 / 4.1868  # STANDARD: thermochemical calorie


def _stoich_air_kg_per_kg(ult: dict = COAL_ULT) -> float:
    """DERIVED: theoretical (stoichiometric) air, kg air / kg as-fired fuel.

        O2 needed = 2.667 C + 7.937 H + 0.998 S - O(in fuel)     [kg O2 / kg]
        air_st    = O2 needed / 0.2315
    (2.667 = 32/12, 7.937 = 8*(1 - ...) ~ 8, 0.998 ~ 32/32; standard
    combustion stoichiometry, e.g. Rayaprolu / Basu AFBC texts.)
    """
    o2 = (2.667 * ult["C"] + 7.937 * ult["H"] + 0.998 * ult["S"] - ult["O"])
    return o2 / _O2_MASS_FRAC_AIR


def _dulong_gcv_kcal_per_kg(ult: dict = COAL_ULT) -> float:
    """DERIVED: gross calorific value by Dulong, kcal / kg as-fired.

        GCV = 8080 C + 34500 (H - O/8) + 2240 S            [kcal/kg]
    """
    return (8080.0 * ult["C"]
            + 34500.0 * (ult["H"] - ult["O"] / 8.0)
            + 2240.0 * ult["S"])


AIR_ST = _stoich_air_kg_per_kg()                    # ~5.47 kg/kg   DERIVED
GCV_KCAL_PER_KG = _dulong_gcv_kcal_per_kg()         # ~4040 kcal/kg DERIVED
GCV_J_PER_KG = GCV_KCAL_PER_KG / _KCAL_PER_KJ * 1.0e3   # ~1.69e7 J/kg

# Fuel-independent heat release per kg of stoichiometric air is ~3.0 MJ
# (~725 kcal) for solid fuels -- the basis of the "constant flue-gas" rule.
# GCV_kcal / air_st must land in that band; (3400, 5.46) gives 623 and FAILS.
_KCAL_PER_KG_AIR_BAND = (700.0, 780.0)

ETA_BOILER = 0.85      # ASSUMED (range 0.80 - 0.87, AFBC on washery-reject).
                       # Affects M_COAL_NOM and every energy-balance gain.
LAMBDA_EXCESS = 1.25   # ASSUMED (range 1.15 - 1.35): total excess-air ratio at
                       # MCR. Affects flue-gas mass flow -> bed-temperature gains.
PA_AIR_FRACTION = 0.55 # ASSUMED (range 0.45 - 0.65): fraction of combustion air
                       # entering as primary (fluidising) air on an AFBC bed.
                       # Sets the E8 primary-air valid range and K_PA.
T_FW_C = 150.0         # ASSUMED (range 140 - 160): economiser-outlet feedwater
                       # temperature. Affects M_COAL_NOM (duty) magnitude only.
T_FLUE_REF_C = 200.0   # ASSUMED (range 150 - 260): APH-heated primary-air inlet
                       # temperature; the reference the bed sits above. Sets the
                       # (T_bed - T_ref) span used by K_FUEL, K_CV, K_PA.

# ---- 2. Steam-side duty, DERIVED from IF97 enthalpies at the operating point.
_H_MS_NOM = h_vapour_J_kg(_P_NOM_PA, NOMINAL["ms_temperature"] + 273.15)   # ~3.404e6
_H_FW_NOM = h_liquid_J_kg(_P_NOM_PA, T_FW_C + 273.15)                      # ~0.636e6
_W_STEAM_NOM_KGPS = NOMINAL["steam_flow"] * KGPS_PER_TPH                   # 18.611 kg/s
Q_STEAM_NOM = _W_STEAM_NOM_KGPS * (_H_MS_NOM - _H_FW_NOM)   # ~5.15e7 W  DERIVED
Q_FUEL_NOM = Q_STEAM_NOM / ETA_BOILER                       # ~6.06e7 W  gross
M_COAL_NOM = Q_FUEL_NOM / GCV_J_PER_KG                       # ~3.58 kg/s DERIVED

# ---- 3. Bed thermal conductance: the denominator of the bed-temperature gains.
# Two parallel sinks hold the bed temperature down:
#   flue gas  G_FG  = m_fluegas * cp_g               (~3.1e4 W/K)
#   in-bed water walls  G_WW = beta_furnace * Q_FUEL_NOM / (T_bed - Tsat)
# The water-wall sink is the larger one -- an AFBC bed is strongly clamped by the
# boiling evaporator surface immersed in it. Omitting it (dividing only by G_FG)
# made the bed ~2.5x too sensitive to every heat perturbation: a 3.5 t/h leak
# quenched the *average* bed 45 degC, family E crossed the 880 alarm. Both are
# fixed by using G_BED_EFF = G_FG + G_WW for the heat-source / heat-sink terms.
C_PG = 1150.0          # ASSUMED (range 1100 - 1250 J/kg/K): mean flue-gas cp at
                       # bed temperature. Affects G_FG -> bed gains and K_PA.
BETA_FURNACE = 0.45    # ASSUMED (range 0.35 - 0.55): fraction of gross fuel heat
                       # absorbed by water walls in the bed / furnace zone (the
                       # rest is picked up downstream or lost). Sets G_WW.
_M_FLUEGAS_NOM = (M_COAL_NOM * (1.0 - COAL_ULT["ash"])
                  + M_COAL_NOM * AIR_ST * LAMBDA_EXCESS)     # ~26.9 kg/s DERIVED
G_FG_NOM = _M_FLUEGAS_NOM * C_PG                             # ~3.1e4 W/K DERIVED
_TSAT_NOM_C = Tsat_K(_P_NOM_PA) - 273.15                     # ~281.6 degC IF97
G_WW_NOM = BETA_FURNACE * Q_FUEL_NOM / (NOMINAL["bed_temp_avg"] - _TSAT_NOM_C)
G_BED_EFF = G_FG_NOM + G_WW_NOM                             # ~7.9e4 W/K DERIVED
_T_BED_SPAN = NOMINAL["bed_temp_avg"] - T_FLUE_REF_C         # 650 K (bed above ref)

# ---- 4. Bed-temperature deviation gains (first-order lag to a driver-set
#         target; the target is T_BED_NOM + sum of these deviation terms).
#   K_COMB : retained-heat imbalance (released - absorbed) -> bed.
#            [K per unit relative imbalance]  -- family E fouling
#   K_FUEL : released heat below what the load needs -> bed cooler   (family C).
#   K_CV   : high-CV coal, air set for the old CV -> bed hotter      (family D).
#   K_PA   : low primary air -> less excess-air flue-gas dilution -> bed hotter
#            (family D). This one is a FLUE-GAS-temperature effect, so it is
#            divided by G_FG_NOM, not G_BED_EFF -- reducing excess air raises the
#            gas temperature directly and the water-wall clamp buffers it less.
#   K_QUENCH lives in step() (needs live p for the flash fraction).  (family B)
K_COMB = Q_FUEL_NOM / G_BED_EFF                             # ~0.77e3 K  DERIVED
K_FUEL = Q_FUEL_NOM / G_BED_EFF                             # ~0.77e3 K  DERIVED
K_CV = Q_FUEL_NOM / G_BED_EFF                               # ~0.77e3 K  DERIVED
K_PA = PA_AIR_FRACTION * LAMBDA_EXCESS * _T_BED_SPAN        # ~447 K     DERIVED
#   (K_PA structure: f_PA * lambda gives the fraction of stoichiometric-air
#    dilution removed as PA falls; * (T_bed - T_ref) converts it to a bed-temp
#    rise. It already carries the G_FG normalisation implicitly via lambda.)
K_BED_LOAD = 2.75      # ASSUMED (range 2.0 - 4.0 degC per t/h): steady load-
                       # following bed-temperature rise. Anchored to
                       # configs/base.yaml checks.load_coef_degc_per_tph = 2.75
                       # (unchanged here) and bounded above by the fingerprint's
                       # bed~load slope 3.9 degC/(t/h) (different boiler, 774 degC
                       # bed -- CLAUDE.md §9 says do not simply copy it).

# h_f and h_fg at 1 atm -- the state the leaking saturated water flashes toward.
# DERIVED from IF97 (not literals): saturation properties at standard atmosphere.
_ATM_PA = kgfcm2g_to_Pa(0.0)              # gauge 0 = standard atmosphere (101325 Pa)
_H_F_ATM = sat_liquid(_ATM_PA)["h"]        # ~4.19e5 J/kg
_H_FG_ATM = hfg_J_kg(_ATM_PA)             # ~2.26e6 J/kg

# E8 -- primary_air VALID RANGE. The model raises bed temperature monotonically
# as PA falls (K_PA * (1 - PA)); it has NO air-limited turnover. Below the point
# where primary + secondary air can no longer meet stoichiometric demand the bed
# would in reality go sub-stoichiometric (CO up, bed temp rolls over), which
# this model does not represent. That point:
#     PA_MIN = 1 - (LAMBDA_EXCESS - 1) / (PA_AIR_FRACTION * LAMBDA_EXCESS)
# so the primary_air driver is only physical on [PA_MIN, ~1.15]. Family D uses
# 0.80 and 0.84, both inside it.
PRIMARY_AIR_MIN = 1.0 - (LAMBDA_EXCESS - 1.0) / (PA_AIR_FRACTION * LAMBDA_EXCESS)

# ---- 5. Bed / main-steam thermal time constants -- kept FAST (minutes), per
#         the CLAUDE.md stage-1 correction (steam->bed increment x-corr peaks at
#         lag 0). The long autocorrelation comes from the OU drivers, sub-model 4.
M_BED_KG = 11000.0     # ASSUMED (range 8000 - 16000): fluidised-bed solids
                       # inventory (sand + ash + fuel char). Affects tau_bed only.
C_BED = 1000.0         # ASSUMED (range 900 - 1100 J/kg/K): bed-material cp
                       # (silica sand / ash). Affects tau_bed only.
TAU_BED_S = (M_BED_KG * C_BED) / G_FG_NOM                   # ~355 s  DERIVED
M_SH_METAL_KG = 6000.0 # ASSUMED (range 3500 - 10000): primary + secondary
                       # superheater tube bundles + headers + desuperheater +
                       # interconnecting pipe metal. Affects tau_ms only.
C_STEEL = 490.0        # ASSUMED (range 470 - 510 J/kg/K): carbon steel cp.
_CP_STEAM = 2900.0     # ASSUMED (range 2800 - 3500 J/kg/K): superheated-steam cp
                       # at ~66 bar, 400-495 degC. Affects tau_ms only.
_G_SH = _W_STEAM_NOM_KGPS * _CP_STEAM                       # steam-side W/K (~5.4e4)
TAU_MS_S = (M_SH_METAL_KG * C_STEEL) / _G_SH                # ~55 s   DERIVED
K_MS_BED = 0.35        # ASSUMED (range 0.28 - 0.40): superheater outlet
                       # sensitivity to bed / flue-gas temperature.
# E12 -- ms vs load. See DERIVATIONS §4 / §9: RCA Case 4 shows ms FALLING on a
# sharp load rise (firing lag + swell carry-over: 492 -> 428 degC in 8 min);
# the fingerprint's steady-state ms~load slope is +0.31 degC/(t/h) at R^2 0.03
# (i.e. NOT a relationship). We model the Case-4 transient direction (K_MS_FLOW
# > 0: more steam mass through a fixed superheater surface -> less superheat per
# kg), and do NOT impose the fingerprint slope. Disagreement recorded, not
# resolved (report).
K_MS_FLOW = 0.45       # ASSUMED (range 0.2 - 0.8 degC per t/h of steam above
                       # nominal). Sign is the physics; magnitude kept small so
                       # |steady-state ms~load slope| stays within the
                       # fingerprint's own scatter.

# ---- 6. Pressure capacitance e_p [J/Pa]  --  PHYSICAL, per the correction.
# dp/dt = (Q_evap_supply - W_steam * hfg) / E_P. e_p is the energy to raise
# saturation pressure by 1 Pa at ~constant volume:
#     boiler water sensible : M_bw   * cp_bw   * dTsat/dp
#     drum + tube metal     : M_metal* cp_steel* dTsat/dp
#     steam-space latent    : V_steam* (drho_g/dp) * hfg
# NOT fitted to fingerprint drum_pressure.ar1.timescale_minutes = 44.53: that
# timescale is inherited input slowness (CLAUDE.md: "do not fit plant time
# constants to fingerprint autocorrelation"). Fitting it wants e_p ~ 1.3e4 J/Pa,
# ~13x the physical estimate -- that 13x gap is the diagnosis, not a footnote.
# The OU load driver (sub-model 4) supplies the slow pressure wander instead;
# achieved drum_pressure autocorrelation is reported after sub-model 4.
_M_BW_KG = boiler_water_inventory_kg(50.0, _P_NOM_PA)       # ~10224 kg  geometry
_CP_BW = sat_liquid(_P_NOM_PA)["cp"]                        # IF97 (~5.4e3 J/kg/K)
M_DRUM_METAL_KG = 18000.0   # ASSUMED (range 12000 - 26000): drum shell + water-
                            # wall / downcomer / riser tube steel at saturation
                            # temperature. Affects e_p (hence pressure speed).
_DP_PROBE = 2.0e3
_DTSAT_DP = (Tsat_K(_P_NOM_PA + _DP_PROBE)
             - Tsat_K(_P_NOM_PA - _DP_PROBE)) / (2.0 * _DP_PROBE)   # ~1.01e-5 K/Pa
# Drum steam space at NWL: the free surface sits on the centreline, so by
# symmetry the steam half-volume equals the water half-volume (V_DRUM_50_M3).
_V_STEAM_M3 = V_DRUM_50_M3
E_P = (_M_BW_KG * _CP_BW * _DTSAT_DP
       + M_DRUM_METAL_KG * C_STEEL * _DTSAT_DP
       + _V_STEAM_M3 * drho_g_dp_kg_m3_per_Pa(_P_NOM_PA) * hfg_J_kg(_P_NOM_PA))
# Cross-check band from correction 1's independent physical estimate:
# 0.8 - 1.2e3 J/Pa, tau_p ~ 2.7 - 4.1 min. The derivation above lands ~0.68e3
# (water sensible dominates: ~550 of it). That is ~1.2x below the low end of
# the correction band -- recorded as a disagreement, well inside 2x, NO stop
# rule. What matters: both physical figures are ~18-19x below the value an ar1
# fit to drum_pressure.timescale_minutes = 44.53 would demand (~1.3e4 J/Pa).
_E_P_PHYS_BAND = (0.8e3, 1.2e3)
_E_P_AR1_FIT = 1.3e4         # what fitting the 44.53-min ar1 wants; NOT used.



@dataclass
class Drivers:
    """The physical knobs. A fault is a schedule of changes to these.

    Nothing outside this class may touch a tag value directly -- that is what
    guarantees the balances still close after a fault is injected.
    """
    load_demand: float = 67.0          # TPH of steam the turbine is pulling
    feed_valve_effectiveness: float = 1.0   # 1.0 = valve does what it is told
    fuel_availability: float = 1.15    # max relative heat obtainable from the fuel.
                                       # >1 on purpose: a healthy boiler has firing
                                       # headroom. Family C removes that headroom
                                       # (wet coal bridging, feeder trip), which is
                                       # what makes pressure sag.
    heat_absorption: float = 1.0       # how well the water side takes that heat
    blowdown_tph: float = 1.0          # normal continuous blowdown
    leak_tph: float = 0.0              # unaccounted water loss
    coal_cv_factor: float = 1.0        # calorific value vs feeder calibration
    primary_air: float = 1.0           # relative PA flow


@dataclass
class Schedule:
    """One driver change, ramped in over `ramp_min` starting at `t_start_s`."""
    t_start_s: float
    driver: str
    target: float
    ramp_min: float = 5.0


@dataclass
class EpisodeSpec:
    episode_id: str
    family: str                        # N | A | B | C | D | E
    tier: str                          # A | B | C  (modality-necessity tier)
    duration_min: float
    schedules: list[Schedule] = field(default_factory=list)
    root_cause_id: str = ""
    root_cause_text: str = ""
    required_modalities: list[str] = field(default_factory=lambda: ["timeseries"])
    correct_action_ids: list[str] = field(default_factory=list)
    fault_onset_s: float | None = None
    caught_in_time: bool = False       # operator intervenes and it recovers
    dropout_tag: str | None = None     # instrument failure injection
    injection_present: bool = False    # prompt-injection note present
    repeat_of: str | None = None
    contributory: list[str] = field(default_factory=list)
    seed: int = 0


class BoilerSim:
    """Integrates the six tags forward at 5-second resolution."""

    def __init__(self, spec: EpisodeSpec):
        self.spec = spec
        self.rng = random.Random(spec.seed)
        self.d = Drivers()
        self.state = dict(NOMINAL)
        # Feed controller integral term. A real 3-element controller; this is a
        # single-element PI on level, which is enough to make feed RESPOND to
        # level. Kept in t/h (a controller, not physics); its output converts
        # to kg/s for the mass balance.
        self._integral = 0.0
        self._fire = 1.0          # firing rate, relative to nominal
        # Collapsed-liquid water mass in the drum-span region [kg]. At the
        # nominal state this is rho_f(p_nom) * V_DRUM_50_M3 -> indicated 50 %.
        self._m_liq = rho_f_kg_m3(_P_NOM_PA) * V_DRUM_50_M3
        # None until the inventory clamp is hit; then "floor" / "ceiling".
        self.m_liq_saturated: str | None = None
        # Per-step diagnostics (NOT emitted / NOT in the CSV). One dict per
        # step with the clean internals the tests need to check the code path:
        #   t, level_liquid (mass path), level_swell (void term), p_clean.
        self.diag: list[dict] = []

    # -------------------------------------------------------------------
    def _apply_schedules(self, t_s: float) -> None:
        """Ramp each scheduled driver change in over its ramp window."""
        for s in self.spec.schedules:
            if t_s < s.t_start_s:
                continue
            base = getattr(Drivers(), s.driver)
            frac = min(1.0, (t_s - s.t_start_s) / max(s.ramp_min * 60, 1e-9))
            setattr(self.d, s.driver, base + (s.target - base) * frac)

    # -------------------------------------------------------------------
    def _clamp_inventory(self, t_s: float) -> None:
        """Hold the collapsed-liquid mass to the transmitter span and warn once."""
        which = None
        if self._m_liq < M_LIQ_FLOOR_KG:
            self._m_liq, which = M_LIQ_FLOOR_KG, "floor"
        elif self._m_liq > M_LIQ_CEIL_KG:
            self._m_liq, which = M_LIQ_CEIL_KG, "ceiling"
        if which and self.m_liq_saturated is None:
            self.m_liq_saturated = which
            warnings.warn(
                f"{self.spec.episode_id}: drum water inventory hit its {which} "
                f"({self._m_liq:.0f} kg) at t={t_s:.0f}s; indicated level pinned. "
                f"The water balance is saturated from here -- check driver "
                f"severity, do not read the flat trace as physics.",
                RuntimeWarning, stacklevel=3)

    # -------------------------------------------------------------------
    def step(self, t_s: float) -> dict:
        d, st = self.d, self.state
        dt_min = DT_S / 60.0
        self._apply_schedules(t_s)

        p_kgfcm2g = st["drum_pressure"]
        p_Pa = kgfcm2g_to_Pa(p_kgfcm2g)

        # ---- steam demand: the turbine pulls, with slow load swings ----
        # (swing is the placeholder load wander; sub-model 4 replaces it with a
        # cross-correlated OU process fitted to the fingerprint.)
        swing = 2.0 * math.sin(t_s / 1800.0)          # +/- 2 TPH over 30 min
        # The turbine cannot pass rated flow on sagging pressure. Without this
        # coupling a fuel-side fault drives pressure to zero unchecked, which
        # no real plant does.
        throttle = max(0.3, min(1.0, p_kgfcm2g / 60.0))
        steam = (d.load_demand + swing) * throttle     # t/h

        # ================= WATER SIDE  (SI internally) ===================
        # Single-element PI on INDICATED drum level (the transmitter sees the
        # swell too). Closed loop, so feed RESPONDS to level -- which is what
        # makes family B (leak) look different from family A (feed short).
        err = NOMINAL["drum_level"] - st["drum_level"]                    # %
        self._integral = max(-25.0, min(25.0, self._integral + err * dt_min * 2.0))
        demand_tph = steam + 3.0 * err + self._integral + d.blowdown_tph
        demand_tph = max(0.0, min(feed_valve_max_tph(), demand_tph))

        # THE FAULT ENTERS HERE for family A. A seized actuator limits valve
        # TRAVEL, which caps deliverable FLOW. It does not scale demand -- a
        # scaled demand would let the controller wind up and recover, whereas a
        # hard cap means feed simply cannot meet steam and the level falls at a
        # rate the water balance computes exactly.
        feed_tph = min(demand_tph, d.feed_valve_effectiveness * feed_valve_max_tph())

        # Mass balance [kg/s -> kg]. This is geometry.K_level(p) re-expressed as
        # mass; the L1 water-balance check inverts exactly this relation.
        w_feed = feed_tph * KGPS_PER_TPH
        w_steam = steam * KGPS_PER_TPH
        w_bd = d.blowdown_tph * KGPS_PER_TPH
        w_leak = d.leak_tph * KGPS_PER_TPH
        self._m_liq += (w_feed - w_steam - w_bd - w_leak) * DT_S
        self._clamp_inventory(t_s)

        # Collapsed-liquid indicated level from mass + geometry (rho_f is
        # pressure-dependent; the L1 check uses the single nominal K).
        rho_f_now = rho_f_kg_m3(p_Pa)
        level_liquid = 50.0 + (self._m_liq / rho_f_now - V_DRUM_50_M3) / VOL_PER_PCT_M3

        # Shrink-and-swell: fast void response to pressure, from d(rho_g)/dp.
        #   p UP  -> voids compress -> level DOWN (shrink)
        #   p DOWN (load increase) -> voids expand -> level UP (swell)
        level_swell = -G_SW_PCT_PER_KGFCM2 * (p_kgfcm2g - P_NOM_KGFCM2G)

        st["drum_level"] = max(0.0, min(100.0, level_liquid + level_swell))
        st["feed_water_flow"] = feed_tph
        st["steam_flow"] = steam
        # Diagnostics (NOT emitted). level_indicated_clean is the composed,
        # pre-noise value actually written to st["drum_level"]; the tests assert
        # it equals level_liquid + level_swell EXACTLY (composition), separately
        # from checking the emit noise size.
        self._diag_pending = {"t": t_s, "level_liquid": level_liquid,
                              "level_swell": level_swell,
                              "level_indicated_clean": st["drum_level"],
                              "p_clean": p_kgfcm2g}

        # ================= ENERGY SIDE  (sub-model 2) ====================
        # Combustion control: feeder speed tracks load with a pressure trim.
        # WITHOUT this loop a load reduction leaves fuel unchanged and the bed
        # runs away -- which is not a fault, it is a missing controller.
        p_err = NOMINAL["drum_pressure"] - st["drum_pressure"]           # kg/cm2
        fire_for_load = steam / NOMINAL["steam_flow"]
        fire_target = max(0.3, min(1.25, fire_for_load + 0.06 * p_err))
        # Rate-limited: feeder + fuel-transport lag (~1 min). ASSUMED, DERIVATIONS §4.
        self._fire += (fire_target - self._fire) * (DT_S / 60.0)

        # Relative heat. fuel_availability is a CAP on firing, not a multiplier
        # (family C: the feeder runs faster, the coal still does not reach the
        # bed, the loop saturates). coal_cv_factor scales released heat (family
        # D). heat_absorption is the family-E fouling term.
        fire_capped = min(self._fire, d.fuel_availability)
        heat_released = fire_capped * d.coal_cv_factor                   # rel. to nominal
        heat_absorbed = heat_released * d.heat_absorption               # rel. to nominal
        Q_released = heat_released * Q_FUEL_NOM                          # W, gross in bed
        Q_absorbed = heat_absorbed * ETA_BOILER * Q_FUEL_NOM            # W, to the water

        # ---- leak: SATURATED boiler water into the furnace (family B, "E10") ----
        # Directions: leak -> drum inventory lost + extra cold make-up feed ->
        # drum pressure FALLS; the droplets take latent heat from the flue gas to
        # vaporise -> bed COOLS (RCA Case 11: "bed temperature dropped sharply").
        # The water is saturated at drum pressure, so it flashes x ~ 37 % on its
        # OWN sensible heat as it drops to furnace (~atmospheric) pressure; only
        # (1 - x) draws furnace latent heat. NOT double-counted with the
        # feedwater-side load below: that term is w_feed * (h_f - h_fw) sensible
        # heat added to the drum water by the raised make-up feed (a load on the
        # pressure side); this term is (1 - x) * h_fg_atm latent heat pulled from
        # the flue gas (a load on the bed). Different enthalpies, different sides.
        h_f_drum = sat_liquid(p_Pa)["h"]
        flash_x = max(0.0, min(0.9, (h_f_drum - _H_F_ATM) / _H_FG_ATM))   # ~0.366
        Q_quench = w_leak * (1.0 - flash_x) * _H_FG_ATM                  # W, from flue gas

        # ---- pressure integrator with the PHYSICAL capacitance E_P ----
        # Q_evap_supply = absorbed heat  -  feedwater sensible heating to
        # saturation (charged on the ACTUAL feed, already raised by w_leak)  -
        # superheater pickup. At the nominal point this identically equals
        # w_steam * hfg(p), so dp/dt = 0 with no imbalance and no fitted gain.
        h_fw = h_liquid_J_kg(p_Pa, T_FW_C + 273.15)
        h_g_p = sat_vapour(p_Pa)["h"]
        h_ms_p = h_vapour_J_kg(p_Pa, st["ms_temperature"] + 273.15)
        Q_evap_supply = (Q_absorbed
                         - w_feed * (h_f_drum - h_fw)
                         - w_steam * (h_ms_p - h_g_p))
        dp_dt_Pa_s = (Q_evap_supply - w_steam * hfg_J_kg(p_Pa)) / E_P
        st["drum_pressure"] += dp_dt_Pa_s * DT_S / _PA_PER_KGFCM2
        st["drum_pressure"] = max(5.0, st["drum_pressure"])

        # ---- bed temperature: first-order lag (tau ~ 6 min) toward a target ----
        # built from deviation terms, each gain DERIVED from the combustion
        # mass/energy balance (DERIVATIONS §4), NOT a bare literal:
        #   load       K_BED_LOAD * (steam - nominal)      -- load-following rise
        #   fouling    K_COMB * (released - absorbed)       -- family E (retained
        #              heat; the ONLY fouling bed term -- NOT the controller's
        #              pressure-trim over-fire, which is a response, not a cause)
        #   fuel cap   K_FUEL * min(0, fuel_availability - fire_for_load)  -- < 0
        #              only while the family-C fuel cap actually bites
        #   high CV    K_CV * (coal_cv_factor - 1)          -- family D
        #   low PA     K_PA * (1 - min(1, primary_air))     -- family D, valid
        #              only for primary_air >= PRIMARY_AIR_MIN (~0.64)
        #   leak       -Q_quench / G_BED_EFF                -- family B
        fire_cap_deficit = min(0.0, d.fuel_availability - fire_for_load)
        bed_dev = (K_BED_LOAD * (steam - NOMINAL["steam_flow"])
                   + K_COMB * (heat_released - heat_absorbed)
                   + K_FUEL * fire_cap_deficit
                   + K_CV * (d.coal_cv_factor - 1.0)
                   + K_PA * (1.0 - min(1.0, d.primary_air))
                   - Q_quench / G_BED_EFF)
        bed_target = NOMINAL["bed_temp_avg"] + bed_dev
        st["bed_temp_avg"] += (bed_target - st["bed_temp_avg"]) * (DT_S / TAU_BED_S)

        # ---- main steam temperature: lag (tau ~ 1-2 min) toward a target ----
        # ms tracks bed / flue-gas temperature (K_MS_BED); more steam mass flow
        # through a fixed superheater surface gives less superheat per kg
        # (K_MS_FLOW > 0). The negative flow term is the RCA Case 4 direction
        # (ms fell 492 -> 428 degC on a sharp load rise). The fingerprint's
        # steady-state ms~load slope is +0.31 degC/(t/h) at R^2 0.03 -- not a
        # relationship -- and is deliberately NOT imposed. Disagreement recorded.
        target_ms = (NOMINAL["ms_temperature"]
                     + K_MS_BED * (st["bed_temp_avg"] - NOMINAL["bed_temp_avg"])
                     - K_MS_FLOW * (steam - NOMINAL["steam_flow"]))
        st["ms_temperature"] += (target_ms - st["ms_temperature"]) * (DT_S / TAU_MS_S)

        # Diagnostics for the energy-side tests (NOT emitted). *_clean are the
        # pre-noise values step() actually wrote; the rest are the internal
        # quantities the sub-model-2 checks re-derive against.
        self._diag_pending.update(
            {"bed_clean": st["bed_temp_avg"], "ms_clean": st["ms_temperature"],
             "bed_target": bed_target, "bed_dev": bed_dev, "Q_quench": Q_quench,
             "dp_dt_Pa_s": dp_dt_Pa_s, "steam_clean": steam,
             "fire_capped": fire_capped, "heat_released": heat_released,
             "heat_absorbed": heat_absorbed})
        self.diag.append(self._diag_pending)

        # ---- measurement noise, per-tag (PRE-REWRITE -- sub-model 4) ----
        out = {"t": t_s}
        noise = {"drum_level": 0.15, "feed_water_flow": 0.35, "steam_flow": 0.35,
                 "drum_pressure": 0.05, "bed_temp_avg": 1.2, "ms_temperature": 0.8}
        for tag, v in st.items():
            out[tag] = round(v + self.rng.gauss(0, noise[tag]), 3)
        return out

    # -------------------------------------------------------------------
    def run(self) -> list[dict]:
        rows, n = [], int(self.spec.duration_min * 60 / DT_S)
        for i in range(n):
            rows.append(self.step(i * DT_S))
        if self.spec.dropout_tag:
            rows = self._inject_dropout(rows)
        return rows

    def _inject_dropout(self, rows: list[dict]) -> list[dict]:
        """Freeze one tag partway through.

        The agent must notice the INSTRUMENT is bad rather than diagnosing a
        plant fault. Six of the thirty episodes carry one of these.
        """
        tag = self.spec.dropout_tag
        start = int(len(rows) * 0.55)
        frozen = rows[start][tag]
        for r in rows[start:]:
            r[tag] = frozen
        return rows


# =========================================================================
#  SELF-TESTS  --  run via `python3 -m data.generator.sim`
# =========================================================================
def _spec(name="t", dur_min=60.0, schedules=None, **kw) -> EpisodeSpec:
    return EpisodeSpec(episode_id=name, family=kw.pop("family", "N"),
                       tier="A", duration_min=dur_min,
                       schedules=schedules or [], **kw)


def _series(rows, key):
    return [r[key] for r in rows]


def _self_test() -> None:
    """Invariants that must hold regardless of tuning."""
    errs = []

    # 1. clean start: no-fault episode stays in band and never saturates.
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)   # a saturation warning fails here
        sim = BoilerSim(_spec("selftest_normal", 60.0))
        rows = sim.run()
    lvl = _series(rows, "drum_level")
    if abs(lvl[0] - 50.0) > 0.6:
        errs.append(f"start level {lvl[0]:.2f} not ~50 (noise sd 0.15)")
    if max(abs(x - 50.0) for x in lvl) > 4.0:
        errs.append(f"no-fault level left +/-4 band: range "
                    f"{min(lvl):.2f}..{max(lvl):.2f}")
    if sim.m_liq_saturated is not None:
        errs.append("no-fault episode saturated the inventory clamp")

    # 2. inventory clamp floor is the physical value the instruction specified.
    floor = rho_f_kg_m3(_P_NOM_PA) * drum_water_volume_m3(0.0)
    if abs(M_LIQ_FLOOR_KG - floor) > 1e-6:
        errs.append(f"M_LIQ_FLOOR_KG {M_LIQ_FLOOR_KG} != rho_f*V(0%) {floor}")

    # 3. severe sustained feed shortage: level pins at 0, mass pins at floor,
    #    warning fires (does NOT integrate to a negative / runaway mass).
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        sim = BoilerSim(_spec("selftest_starve", 90.0, family="A",
                              schedules=[Schedule(300.0, "feed_valve_effectiveness",
                                                  0.55, 3.0)]))
        rows = sim.run()
        fired = any(issubclass(x.category, RuntimeWarning) for x in w)
    if sim._m_liq < M_LIQ_FLOOR_KG - 1e-6:
        errs.append(f"inventory ran below floor: {sim._m_liq:.1f} kg")
    if sim.m_liq_saturated != "floor" or not fired:
        errs.append("feed-shortage saturation not flagged (clamp/warn missing)")
    if min(_series(rows, "drum_level")) > 1.0:
        errs.append("severe feed shortage never drove indicated level to ~0")

    # ================= sub-model 2: energy-balance invariants =============
    # 4. Coal ASSUMED-input CONSISTENCY (CLAUDE.md "ASSUMED inputs describing
    #    the same object must be mutually consistent"). GCV_kcal / air_st is
    #    ~fuel-independent (~3 MJ per kg stoichiometric air). The old pair
    #    (GCV 3400 ASSUMED directly, air_st ~5.46 from a separate analysis)
    #    gives 623 -- OUTSIDE the band. One analysis, both derived -> in band.
    ratio = GCV_KCAL_PER_KG / AIR_ST
    if not (_KCAL_PER_KG_AIR_BAND[0] <= ratio <= _KCAL_PER_KG_AIR_BAND[1]):
        errs.append(f"coal GCV/air_st = {ratio:.0f} kcal per kg-air, outside "
                    f"{_KCAL_PER_KG_AIR_BAND} -- ultimate analysis not self-consistent")
    if _KCAL_PER_KG_AIR_BAND[0] <= 3400.0 / 5.46 <= _KCAL_PER_KG_AIR_BAND[1]:
        errs.append("band too wide: the inconsistent (3400, 5.46) pair should fail it")

    # 5. Nominal energy balance closes with no fitted constant: a 90-min
    #    no-fault run holds pressure and bed within their normal bands.
    sim = BoilerSim(_spec("selftest_energy_normal", 90.0))
    rows = sim.run()
    p = _series(rows, "drum_pressure")
    bed = _series(rows, "bed_temp_avg")
    if max(abs(x - NOMINAL["drum_pressure"]) for x in p) > 1.0:
        errs.append(f"no-fault pressure left +/-1 kg/cm2: {min(p):.2f}..{max(p):.2f}")
    if max(abs(x - NOMINAL["bed_temp_avg"]) for x in bed) > 20.0:
        errs.append(f"no-fault bed left +/-20 degC: {min(bed):.1f}..{max(bed):.1f}")

    # 6. e_p is the PHYSICAL capacitance, NOT a fit to the 44.53-min ar1
    #    timescale. Must sit within 2x of the correction's physical band and
    #    stay an order of magnitude below what the ar1 fit would demand.
    if not (_E_P_PHYS_BAND[0] / 2.0 <= E_P <= _E_P_PHYS_BAND[1] * 2.0):
        errs.append(f"E_P {E_P:.0f} J/Pa not within 2x of physical band {_E_P_PHYS_BAND}")
    if E_P > _E_P_AR1_FIT / 5.0:
        errs.append(f"E_P {E_P:.0f} within 5x of the ar1 fit {_E_P_AR1_FIT:.0f} -- looks fitted")

    # 7. family E (fouling) crosses NO limit. An episode here that reaches the
    #    880 bed alarm is a mislabel (episode_build.py), not a severe one; and
    #    the bed must still rise enough for the long-drift check to have a hope.
    sim = BoilerSim(_spec("selftest_fouling", 220.0, family="E",
                          schedules=[Schedule(300.0, "heat_absorption", 0.985, 100.0)]))
    bedE = _series(sim.run(), "bed_temp_avg")
    if max(bedE) >= 880.0:
        errs.append(f"family E bed reached {max(bedE):.1f} >= 880 alarm (mislabelled)")
    if max(bedE) - NOMINAL["bed_temp_avg"] < 8.0:
        errs.append(f"family E bed rose only {max(bedE) - 850:.1f} degC -- too weak to trend")

    if errs:
        raise AssertionError("sim self-test FAILED:\n  " + "\n  ".join(errs))
    print("sim self-test passed "
          f"(clamp floor {M_LIQ_FLOOR_KG:.0f} kg / ceil {M_LIQ_CEIL_KG:.0f} kg; "
          f"GCV {GCV_KCAL_PER_KG:.0f} kcal/kg, air_st {AIR_ST:.2f} kg/kg -> "
          f"{GCV_KCAL_PER_KG / AIR_ST:.0f} kcal/kg-air; E_P {E_P:.0f} J/Pa).")


def _window_mean(rows, key, t0, t1):
    xs = [r[key] for r in rows if t0 <= r["t"] <= t1]
    return sum(xs) / len(xs)


def _dwin(diag, key, t0, t1):
    xs = [d[key] for d in diag if t0 <= d["t"] <= t1]
    return sum(xs) / len(xs)


def _ols_slope(xs, ys):
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / sxx


def _exact_composition_check(sim, rows):
    """Split into two assertions the instruction asked to keep separate.

      (a) COMPOSITION is exact: the pre-noise value step() wrote to
          st['drum_level'] equals level_liquid + level_swell to 1e-9. Cannot be
          fooled by any tolerance -- it catches step() dropping the term,
          negating it in the compose line, or scaling it.
      (b) The only thing between level_indicated_clean and the emitted
          drum_level is the emit noise: max abs diff < 0.9 (~6 sd) AND the RMS
          sits in [0.08, 0.24] around the sd=0.15 the emit loop adds.

    Only valid where the [0,100] clamp is not active (load-step runs); pass
    such runs. Raises AssertionError; returns (max_compose_err, noise_rms).
    """
    diag = sim.diag
    assert len(diag) == len(rows), "diag / rows length mismatch"
    compose_err = [abs(d["level_indicated_clean"]
                       - (d["level_liquid"] + d["level_swell"])) for d in diag]
    max_compose = max(compose_err)
    if max_compose >= 1e-9:
        raise AssertionError(
            f"composition not exact: max |indicated_clean - (liquid + swell)| "
            f"= {max_compose:.3e} (>= 1e-9) -- step() is not adding swell as written")
    noise = [r["drum_level"] - d["level_indicated_clean"] for r, d in zip(rows, diag)]
    max_noise = max(abs(n) for n in noise)
    rms = (sum(n * n for n in noise) / len(noise)) ** 0.5
    if max_noise >= 0.9 or not (0.08 <= rms <= 0.24):
        raise AssertionError(
            f"emit-noise inconsistent: max |drum_level - indicated_clean| "
            f"= {max_noise:.3f}, rms = {rms:.3f} (expect ~0.15)")
    return max_compose, rms


def _swell_trace_check(sim, rows, tol_slope=0.10):
    """OLS slope of (emitted drum_level - mass-path level_liquid) on
    (p_clean - p_nom) over the whole run must equal -G_sw within tol_slope.
    This is the pressure->indicated-level gain measured from the EMITTED data
    through the emit noise, compared against the module's real G_sw -- so a
    sign flip or a magnitude error in step() fails it even though the mutated
    code's own diag stays internally consistent.

    Raises AssertionError; returns slope.
    """
    diag = sim.diag
    xs = [d["p_clean"] - P_NOM_KGFCM2G for d in diag]
    ys = [r["drum_level"] - d["level_liquid"] for r, d in zip(rows, diag)]
    slope = _ols_slope(xs, ys)
    if abs(slope - (-G_SW_PCT_PER_KGFCM2)) >= tol_slope:
        raise AssertionError(
            f"pressure->level gain in emitted trace = {slope:.3f}, "
            f"expected -G_sw = {-G_SW_PCT_PER_KGFCM2:.3f} (tol {tol_slope})")
    return slope


def _direction_checks() -> None:
    """Sign claims verified against the EMITTED trace / returned state.

    Sub-model 2 replaced the PRESS_GAIN placeholder with a physical pressure
    integrator, so checks 1, 2 and 5 are no longer PROVISIONAL. Checks 6-8 are
    the sub-model-2 additions (E10 leak, E8 primary air, E12 ms vs load).
    """
    print("\ndirection checks (expected sign -> measured):")

    # -- 1 & 2: shrink-and-swell SIGN, from the emitted trace.
    # Load steps kept inside feed-valve max (81.6 t/h) and fuel ceiling
    # (1.15*67 ~ 77) so the mass path does not saturate. The pressure move is
    # a TRANSIENT in the pre-rewrite energy model, so we pick the sample where
    # p_clean is furthest from nominal and check the emitted swell offset
    # (drum_level - mass-path level_liquid) there. Non-tautological: emitted
    # data, real stimulus, real response, compared to the module G_sw.
    # Quantitative gate = the whole-run trace slope (600 samples, all the
    # pressure variation) inside _swell_trace_check: |slope - (-G_sw)| < 0.10.
    # The extreme-pressure sample is a second, weaker confirmation: at the
    # transient peak the emitted offset must (i) have the right sign and
    # (ii) match the swell prediction -G_sw*dp within 25 %. Steps are 67->77
    # up (fuel ceiling ~77) and 67->57 down (alarm_lo 55), the largest that
    # stay in-envelope; window is p_peak +/- 0.4 averaged.
    def _swell_sign(sim, rows, direction):
        diag = sim.diag
        ce, rms = _exact_composition_check(sim, rows)
        slope = _swell_trace_check(sim, rows)
        if direction == "swell":                        # load up  -> p sags
            pk = min(d["p_clean"] for d in diag)
            near = [(r, d) for r, d in zip(rows, diag) if d["p_clean"] <= pk + 0.4]
        else:                                           # load down -> p rises
            pk = max(d["p_clean"] for d in diag)
            near = [(r, d) for r, d in zip(rows, diag) if d["p_clean"] >= pk - 0.4]
        dp = sum(d["p_clean"] - P_NOM_KGFCM2G for _, d in near) / len(near)
        offset = sum(r["drum_level"] - d["level_liquid"] for r, d in near) / len(near)
        predicted = -G_SW_PCT_PER_KGFCM2 * dp
        sign_ok = (offset > 0) if direction == "swell" else (offset < 0)
        match_ok = abs(offset - predicted) < 0.25 * abs(predicted)
        return dict(pk=pk, dp=dp, n=len(near), offset=offset, predicted=predicted,
                    slope=slope, rms=rms, ok=(sign_ok and match_ok))

    inc_sim = BoilerSim(_spec("dir_load_up", 50.0, family="N",
                              schedules=[Schedule(600.0, "load_demand", 77.0, 2.0)]))
    inc = inc_sim.run()
    r1 = _swell_sign(inc_sim, inc, "swell")
    ok1 = r1["ok"]
    print(f"  load +10 t/h: p peak {r1['pk']:.2f} kg/cm2 "
          f"(dp {r1['dp']:+.2f}, n={r1['n']}); emitted offset {r1['offset']:+.3f} % "
          f"vs -G_sw*dp {r1['predicted']:+.3f} % (expect > 0, swell); "
          f"trace slope {r1['slope']:+.3f} vs {-G_SW_PCT_PER_KGFCM2:+.3f}  "
          f"[{'OK' if ok1 else 'FAIL'}]")

    dec_sim = BoilerSim(_spec("dir_load_dn", 50.0, family="N",
                              schedules=[Schedule(600.0, "load_demand", 57.0, 2.0)]))
    dec = dec_sim.run()
    r2 = _swell_sign(dec_sim, dec, "shrink")
    ok2 = r2["ok"]
    print(f"  load -10 t/h: p peak {r2['pk']:.2f} kg/cm2 "
          f"(dp {r2['dp']:+.2f}, n={r2['n']}); emitted offset {r2['offset']:+.3f} % "
          f"vs -G_sw*dp {r2['predicted']:+.3f} % (expect < 0, shrink); "
          f"trace slope {r2['slope']:+.3f} vs {-G_SW_PCT_PER_KGFCM2:+.3f}  "
          f"[{'OK' if ok2 else 'FAIL'}]")

    # -- 3. family A (feed valve capped) -> feed < steam, level falls
    fa = BoilerSim(_spec("dir_family_A", 60.0, family="A",
                         schedules=[Schedule(600.0, "feed_valve_effectiveness",
                                             0.70, 3.0)])).run()
    feed = _window_mean(fa, "feed_water_flow", 2400, 3000)
    steam = _window_mean(fa, "steam_flow", 2400, 3000)
    lvl0 = _window_mean(fa, "drum_level", 300, 570)
    lvl1 = _window_mean(fa, "drum_level", 2400, 3000)
    ok3 = (feed < steam) and (lvl1 < lvl0 - 5.0)
    print(f"  family A: feed {feed:.1f} < steam {steam:.1f} t/h, "
          f"level {lvl0:.1f}->{lvl1:.1f} %  [{'OK' if ok3 else 'FAIL'}]")

    # -- 4a. family B (leak) -> controller raises feed above steam, level only droops
    fb = BoilerSim(_spec("dir_family_B", 90.0, family="B",
                         schedules=[Schedule(900.0, "leak_tph", 4.0, 8.0)])).run()
    feed = _window_mean(fb, "feed_water_flow", 3600, 4800)
    steam = _window_mean(fb, "steam_flow", 3600, 4800)
    lvl1 = _window_mean(fb, "drum_level", 3600, 4800)
    ok4 = (feed - steam > 2.0) and (lvl1 > 40.0)
    print(f"  family B: feed {feed:.1f} > steam {steam:.1f} t/h "
          f"(gap {feed - steam:+.1f}), level holds at {lvl1:.1f} %  "
          f"[{'OK' if ok4 else 'FAIL'}]")

    # -- 5. fuel availability capped -> pressure sags -> throttle -> steam falls
    fc = BoilerSim(_spec("dir_fuel_cap", 60.0, family="C",
                         schedules=[Schedule(600.0, "fuel_availability",
                                             0.75, 10.0)])).run()
    p0 = _window_mean(fc, "drum_pressure", 300, 570)
    p1 = _window_mean(fc, "drum_pressure", 2400, 3000)
    s0 = _window_mean(fc, "steam_flow", 300, 570)
    s1 = _window_mean(fc, "steam_flow", 2400, 3000)
    ok5 = (p1 < p0 - 1.0) and (s1 < s0 - 1.0)
    print(f"  fuel cap 0.75: pressure {p0:.1f}->{p1:.1f} kg/cm2 (sag), "
          f"steam {s0:.1f}->{s1:.1f} t/h (turbine throttles)  "
          f"[{'OK' if ok5 else 'FAIL'}]")

    # -- 6. E10  tube leak -> drum pressure FALLS and bed temperature COOLS.
    # Pressure: the make-up feed the controller adds carries w_leak*(h_f - h_fw)
    # of sensible heat that then leaves with the leaked saturated water -> less
    # heat to evaporation -> p down. Bed: the (1 - flash_x) fraction of the
    # droplet takes latent heat from the flue gas to vaporise -> bed down.
    # (The non-double-counting of these two -- different enthalpies, different
    # state variables -- is proven by mutations M3/M4 in _mutation_check.)
    lk = BoilerSim(_spec("dir_leak", 80.0, family="B",
                         schedules=[Schedule(600.0, "leak_tph", 8.0, 6.0)])).run()
    p0 = _window_mean(lk, "drum_pressure", 300, 570)
    p1 = _window_mean(lk, "drum_pressure", 3600, 4500)
    b0 = _window_mean(lk, "bed_temp_avg", 300, 570)
    b1 = _window_mean(lk, "bed_temp_avg", 3600, 4500)
    f1 = _window_mean(lk, "feed_water_flow", 3600, 4500)
    s1 = _window_mean(lk, "steam_flow", 3600, 4500)
    ok6 = (p1 < p0 - 0.15) and (b1 < b0 - 8.0) and (f1 > s1 + 3.0)
    print(f"  leak 8 t/h: pressure {p0:.2f}->{p1:.2f} (falls), "
          f"bed {b0:.1f}->{b1:.1f} (cools), feed {f1:.1f} > steam {s1:.1f}  "
          f"[{'OK' if ok6 else 'FAIL'}]")

    # -- 7. E8  low primary air -> bed HOTTER, monotone in PA over the VALID
    # range [PRIMARY_AIR_MIN, 1.0]. The model has no air-limited turnover, so
    # below PRIMARY_AIR_MIN (~0.64) it keeps rising, which is unphysical -- that
    # bound is asserted here so a future driver schedule cannot cross it silently.
    pa_beds = []
    for pa in (1.00, 0.90, 0.80, 0.70):
        r = BoilerSim(_spec(f"dir_pa_{pa}", 55.0, family="D",
                            schedules=[Schedule(600.0, "primary_air", pa, 8.0)])).run()
        pa_beds.append(_window_mean(r, "bed_temp_avg", 2400, 3000))
    monotone = all(a < b - 3.0 for a, b in zip(pa_beds, pa_beds[1:]))  # PA down -> bed up
    ok7 = monotone and (0.55 < PRIMARY_AIR_MIN < 0.75) and (pa_beds[2] > pa_beds[0] + 40.0)
    print(f"  primary_air 1.00/0.90/0.80/0.70 -> bed "
          f"{'/'.join(f'{b:.0f}' for b in pa_beds)} degC (monotone up as PA falls); "
          f"valid range PA >= {PRIMARY_AIR_MIN:.2f}  [{'OK' if ok7 else 'FAIL'}]")

    # -- 8. E12  sharp load rise -> ms transient DIP (RCA Case 4 direction:
    # firing lags, steam mass through the superheater jumps first), then RECOVERS
    # as the bed catches up. We do NOT impose the fingerprint's +0.31 degC/(t/h)
    # steady-state slope (R^2 0.03 -- not a relationship). Disagreement recorded.
    e12 = BoilerSim(_spec("dir_ms_load", 45.0, family="N",
                          schedules=[Schedule(600.0, "load_demand", 77.0, 1.0)]))
    e12r = e12.run()
    ms_pre = _window_mean(e12r, "ms_temperature", 300, 570)
    ms_dip = _window_mean(e12r, "ms_temperature", 660, 900)      # 1-5 min after step
    ms_rec = _window_mean(e12r, "ms_temperature", 1800, 2400)    # 20-30 min after
    ok8 = (ms_dip < ms_pre - 1.0) and (ms_rec > ms_dip + 2.0)
    print(f"  load 67->77: ms {ms_pre:.2f} -> dip {ms_dip:.2f} (Case-4 fall) "
          f"-> recover {ms_rec:.2f}  [{'OK' if ok8 else 'FAIL'}]")

    if not all([ok1, ok2, ok3, ok4, ok5, ok6, ok7, ok8]):
        raise AssertionError("direction check FAILED -- a sub-model sign is wrong")
    print("  all eight direction checks OK")


def _headline_recheck() -> None:
    """Re-derive the shrink-and-swell gain G_sw by a method different from the
    code's. The code calls steam_tables.drho_g_dp_kg_m3_per_Pa (central
    difference, dp = 1000 Pa). Here: evaluate rho_g at exactly p_nom +/- 1
    kgf/cm2 (a bracket ~100x wider, different endpoints) and rebuild G_sw by
    hand from the block-comment formula.
    """
    p_lo = kgfcm2g_to_Pa(P_NOM_KGFCM2G - 1.0)
    p_hi = kgfcm2g_to_Pa(P_NOM_KGFCM2G + 1.0)
    rho_g_lo, rho_g_hi = rho_g_kg_m3(p_lo), rho_g_kg_m3(p_hi)
    rho_g0 = rho_g_kg_m3(_P_NOM_PA)
    slope_indep = (rho_g_hi - rho_g_lo) / (p_hi - p_lo)          # kg/m3 per Pa
    g_indep = ((ALPHA_SW * V_SW_M3) / (rho_g0 * VOL_PER_PCT_M3)
               * slope_indep * _PA_PER_KGFCM2)

    slope_code = drho_g_dp_kg_m3_per_Pa(_P_NOM_PA)
    rel = abs(g_indep - G_SW_PCT_PER_KGFCM2) / G_SW_PCT_PER_KGFCM2

    print("\nindependent re-derivation of G_sw (headline number for sub-model 1):")
    print(f"  rho_g(p_nom)                 = {rho_g0:.4f} kg/m3")
    print(f"  d(rho_g)/dp  code (dp=1kPa)  = {slope_code:.4e} kg/m3/Pa")
    print(f"  d(rho_g)/dp  indep (+/-1 kgf)= {slope_indep:.4e} kg/m3/Pa")
    print(f"  G_sw  code                   = {G_SW_PCT_PER_KGFCM2:.4f} %/(kgf/cm2)")
    print(f"  G_sw  independent            = {g_indep:.4f} %/(kgf/cm2)")
    print(f"  relative difference          = {rel * 100:.2f} %")
    # band across the ASSUMED ranges of V_SW_M3, ALPHA_SW
    g_min = _shrink_swell_gain(4.0, 0.08)
    g_max = _shrink_swell_gain(14.0, 0.35)
    print(f"  band over ASSUMED V_SW 4-14 m3, ALPHA_SW 0.08-0.35 : "
          f"{g_min:.3f} - {g_max:.3f}")
    if rel > 0.03:
        raise AssertionError(f"G_sw re-derivation disagrees by {rel*100:.1f}% (>3%)")

    # ---- sub-model 2 headline numbers, each by a DIFFERENT route -----------
    # (a) air_st: code uses the mass-fraction shortcut (2.667 C + 7.937 H +
    #     0.998 S - O). Independent: a kmol-balance (O2 = C + H/4 + S - O/2,
    #     air = O2 / 0.20948 mol frac, x 28.9647 kg/kmol).
    u = COAL_ULT
    o2_kmol = (u["C"] / 12.011 + u["H"] / (4 * 1.008)
               + u["S"] / 32.06 - u["O"] / (2 * 15.999))
    air_mol = o2_kmol / 0.20948 * 28.9647
    rel_air = abs(air_mol - AIR_ST) / AIR_ST
    # (b) GCV: code uses Dulong. Independent: the Boie correlation
    #     (35160 C + 116225 H - 11090 O + 6280 N + 10465 S, kJ/kg).
    gcv_boie = (35160.0 * u["C"] + 116225.0 * u["H"] - 11090.0 * u["O"]
                + 6280.0 * u["N"] + 10465.0 * u["S"]) * _KCAL_PER_KJ
    rel_gcv = abs(gcv_boie - GCV_KCAL_PER_KG) / GCV_KCAL_PER_KG
    print("\nindependent re-derivation of the sub-model-2 headline numbers:")
    print(f"  air_st  code (mass shortcut) = {AIR_ST:.4f} kg/kg")
    print(f"  air_st  indep (kmol balance) = {air_mol:.4f} kg/kg   "
          f"rel diff {rel_air * 100:.2f} %")
    print(f"  GCV     code (Dulong)        = {GCV_KCAL_PER_KG:.1f} kcal/kg")
    print(f"  GCV     indep (Boie)         = {gcv_boie:.1f} kcal/kg   "
          f"rel diff {rel_gcv * 100:.2f} %")
    print(f"  GCV/air_st  = {GCV_KCAL_PER_KG / AIR_ST:.0f} kcal per kg-air "
          f"(band {_KCAL_PER_KG_AIR_BAND}); the inconsistent (3400, 5.46) pair "
          f"-> {3400 / 5.46:.0f}, fails")
    print(f"  E_P = {E_P:.0f} J/Pa  (physical; correction band "
          f"{_E_P_PHYS_BAND[0]:.0f}-{_E_P_PHYS_BAND[1]:.0f}); an ar1 fit to the "
          f"44.53-min timescale wants ~{_E_P_AR1_FIT:.0f} -- NOT used")
    if rel_air > 0.02:
        raise AssertionError(f"air_st re-derivation disagrees by {rel_air*100:.1f}% (>2%)")
    if rel_gcv > 0.05:
        raise AssertionError(f"GCV re-derivation disagrees by {rel_gcv*100:.1f}% (>5%)")


def _mutation_check() -> None:
    """Break what the swell tests test; confirm a test actually fails.

    Two mutations of `step()`, applied to the SOURCE and exec'd in a fresh
    namespace (the check functions still see this module's real constants):

      M1  drop `+ level_swell` from the compose line  -- diag still logs the
          real level_swell, so the composed value no longer matches it.
      M2  flip the sign of level_swell               -- the mutated code's own
          diag stays internally consistent; only the module-constant comparison
          exposes it.
    """
    import pathlib

    src = pathlib.Path(__file__).read_text()
    load_up = dict(episode_id="mut", family="N", tier="A", duration_min=50.0)
    mutations = [
        ("M1 drop swell from compose line",
         'st["drum_level"] = max(0.0, min(100.0, level_liquid + level_swell))',
         'st["drum_level"] = max(0.0, min(100.0, level_liquid))'),
        ("M2 flip swell sign",
         "level_swell = -G_SW_PCT_PER_KGFCM2 * (p_kgfcm2g - P_NOM_KGFCM2G)",
         "level_swell = +G_SW_PCT_PER_KGFCM2 * (p_kgfcm2g - P_NOM_KGFCM2G)"),
    ]

    print("\nmutation check (corrupt step(), confirm a test fails):")
    for label, old, new in mutations:
        if old not in src:
            raise AssertionError(f"{label}: mutation target string not found")
        ns: dict = {}
        exec(compile(src.replace(old, new, 1), "<mutated sim>", "exec"), ns)
        sim = ns["BoilerSim"](ns["EpisodeSpec"](
            schedules=[ns["Schedule"](600.0, "load_demand", 82.0, 2.0)], **load_up))
        rows = sim.run()

        caught = []
        try:
            _exact_composition_check(sim, rows)
        except AssertionError:
            caught.append("exact-composition (a)")
        try:
            _swell_trace_check(sim, rows)
        except AssertionError:
            caught.append("trace-slope (b)")
        off_b = (_window_mean(rows, "drum_level", 300, 570)
                 - _dwin(sim.diag, "level_liquid", 300, 570))
        off_a = (_window_mean(rows, "drum_level", 1500, 3000)
                 - _dwin(sim.diag, "level_liquid", 1500, 3000))
        if not (off_a > off_b + 0.3):
            caught.append("direction-1 sign")

        if not caught:
            raise AssertionError(
                f"{label}: NOTHING caught it -- a swell test is inert, "
                f"delete or replace it")
        print(f"  {label}: caught by {', '.join(caught)}")

    # sanity: unmutated source passes all three
    sim = BoilerSim(_spec("mut_baseline", 50.0, family="N",
                          schedules=[Schedule(600.0, "load_demand", 82.0, 2.0)]))
    rows = sim.run()
    _exact_composition_check(sim, rows)
    _swell_trace_check(sim, rows)
    print("  baseline (unmutated): all three pass")

    # ================= sub-model 2 mutations =============================
    # Each corrupts ONE energy-side constant / term and confirms a specific
    # check (self-test or direction check) flips. M3 / M4 are the E10
    # non-double-count proof: the bed-quench term and the feedwater-load term
    # move DIFFERENT tags, so killing one leaves the other's effect intact.
    def _leak_run(source):
        ns: dict = {}
        exec(compile(source, "<mut>", "exec"), ns)
        sim = ns["BoilerSim"](ns["EpisodeSpec"](
            episode_id="mut_leak", family="B", tier="A", duration_min=80.0,
            schedules=[ns["Schedule"](600.0, "leak_tph", 8.0, 6.0)]))
        rows = sim.run()
        return (_window_mean(rows, "bed_temp_avg", 300, 570)
                - _window_mean(rows, "bed_temp_avg", 3600, 4500),      # bed drop
                _window_mean(rows, "drum_pressure", 300, 570)
                - _window_mean(rows, "drum_pressure", 3600, 4500))     # p drop

    bed_drop0, p_drop0 = _leak_run(src)
    print("\nsub-model-2 mutation check:")
    print(f"  baseline leak 8 t/h: bed drop {bed_drop0:+.1f} degC, "
          f"pressure drop {p_drop0:+.2f} kg/cm2")

    e_muts = [
        ("M3 kill bed quench (Q_quench -> 0)",
         "Q_quench = w_leak * (1.0 - flash_x) * _H_FG_ATM",
         "Q_quench = 0.0 * (w_leak * (1.0 - flash_x) * _H_FG_ATM)",
         "leak_bed"),
        ("M4 kill feedwater-load term",
         "                         - w_feed * (h_f_drum - h_fw)",
         "                         - 0.0 * w_feed * (h_f_drum - h_fw)",
         "leak_p"),
        ("M5 corrupt a Dulong coefficient (8080 -> 5080)",
         "return (8080.0 * ult[\"C\"]",
         "return (5080.0 * ult[\"C\"]",
         "consistency"),
        ("M6 flip the E12 ms-vs-flow sign",
         "                     - K_MS_FLOW * (steam - NOMINAL[\"steam_flow\"]))",
         "                     + K_MS_FLOW * (steam - NOMINAL[\"steam_flow\"]))",
         "ms_dir"),
    ]
    for label, old, new, kind in e_muts:
        if old not in src:
            raise AssertionError(f"{label}: mutation target string not found")
        mutated = src.replace(old, new, 1)
        caught = None
        if kind == "leak_bed":               # bed stops cooling, pressure still falls
            bd, pd = _leak_run(mutated)      # bd, pd are pre-minus-post (a DROP is +ve)
            if abs(bd) < 8.0 and pd > 0.10:
                caught = f"bed drop -> {bd:+.1f} degC (gone), pressure still drops {pd:+.2f}"
        elif kind == "leak_p":               # pressure fall gone, bed still cools
            bd, pd = _leak_run(mutated)
            if pd < p_drop0 - 0.20 and bd > 8.0:
                caught = f"pressure drop -> {pd:+.2f} (was {p_drop0:+.2f}), bed still drops {bd:+.1f}"
        elif kind == "consistency":          # GCV/air_st leaves the band -> self-test 4
            ns: dict = {}
            exec(compile(mutated, "<mut>", "exec"), ns)
            r = ns["GCV_KCAL_PER_KG"] / ns["AIR_ST"]
            if not (_KCAL_PER_KG_AIR_BAND[0] <= r <= _KCAL_PER_KG_AIR_BAND[1]):
                caught = f"GCV/air_st -> {r:.0f} kcal/kg-air, outside {_KCAL_PER_KG_AIR_BAND}"
        elif kind == "ms_dir":               # load-up ms no longer dips
            ns: dict = {}
            exec(compile(mutated, "<mut>", "exec"), ns)
            sim = ns["BoilerSim"](ns["EpisodeSpec"](
                episode_id="mut_ms", family="N", tier="A", duration_min=45.0,
                schedules=[ns["Schedule"](600.0, "load_demand", 77.0, 1.0)]))
            rr = sim.run()
            dip = (_window_mean(rr, "ms_temperature", 660, 900)
                   - _window_mean(rr, "ms_temperature", 300, 570))
            if dip >= 0.0:
                caught = f"ms change after load step -> {dip:+.2f} degC (no longer a dip)"
        if not caught:
            raise AssertionError(f"{label}: NOTHING caught it -- an energy check is inert")
        print(f"  {label}: caught -- {caught}")


if __name__ == "__main__":
    _self_test()
    _direction_checks()
    _headline_recheck()
    _mutation_check()
