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
    [ ] sub-model 2  energy balance: coal-GCV stoichiometry + steam-table
                     pressure integrator replacing PRESS_GAIN
    [ ] sub-model 3  dissolved-solids balance
    [ ] sub-model 4  cross-correlated OU drivers + fingerprint measurement noise
The energy / bed / ms block below is the PRE-REWRITE code, fed by the new
water side via `steam` (t/h). It is replaced wholesale in sub-model 2; its
constants (PRESS_GAIN, the bed_target literals) are NOT yet sourced.

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
    drum_water_volume_m3,
    feed_valve_max_tph,
    water_surface_area_m2,
)
from data.physics.steam_tables import (
    drho_g_dp_kg_m3_per_Pa,
    kgfcm2g_to_Pa,
    rho_f_kg_m3,
    rho_g_kg_m3,
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

# --- ENERGY-SIDE constant NOT YET SOURCED (replaced in sub-model 2) ----------
PRESS_GAIN = 4.0     # kg/cm2 per minute per unit relative energy imbalance. ASSUMED,
                     # pre-rewrite. Sub-model 2 replaces this with a pressure
                     # integrator derived from V_steam and (du/dp)_sat.

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
        self.diag.append({"t": t_s, "level_liquid": level_liquid,
                          "level_swell": level_swell,
                          "level_indicated_clean": st["drum_level"],
                          "p_clean": p_kgfcm2g})

        # ================= ENERGY SIDE  (PRE-REWRITE -- sub-model 2) ======
        # Combustion control: feeder speed tracks load with a pressure trim.
        # WITHOUT this loop a load reduction leaves fuel unchanged and the bed
        # runs away -- which is not a fault, it is a missing controller.
        p_err = NOMINAL["drum_pressure"] - st["drum_pressure"]
        fire_target = (steam / NOMINAL["steam_flow"]) + 0.06 * p_err
        fire_target = max(0.3, min(1.25, fire_target))
        # Rate-limited: the control cannot compensate a step instantly.
        self._fire += (fire_target - self._fire) * 0.05

        # Heat actually released. Fuel availability is a CAP on firing, not a
        # multiplier: with wet coal the feeder can run faster and still not get
        # the coal into the bed, so the control loop saturates and the deficit
        # is real. That saturation is the whole of family C.
        heat_released = min(self._fire, d.fuel_availability) * d.coal_cv_factor
        heat_absorbed = heat_released * d.heat_absorption

        # A tube leak dumps water into the furnace: that heat raises leaking
        # water instead of making saleable steam. It is a LOSS on the pressure
        # side and a COOLING term on the bed -- which is why family B looks
        # nothing like family A despite both being water-side faults.
        leak_rel = d.leak_tph / NOMINAL["steam_flow"]

        # Pressure integrates absorbed heat minus steam drawn off minus loss.
        st["drum_pressure"] += (heat_absorbed - steam / NOMINAL["steam_flow"]
                                - leak_rel) * PRESS_GAIN * dt_min
        st["drum_pressure"] = max(5.0, st["drum_pressure"])

        # Bed temperature: first-order lag toward a target set by the drivers.
        #   term 1  heat released but not absorbed accumulates in the bed
        #   term 2  less fuel in the bed simply runs cooler          (family C)
        #   term 3  high-CV coal burns hotter for the same feeder speed, and
        #           the pressure trim CANNOT correct this -- air is set for the
        #           old CV. This is what makes family D detectable at all.
        #   term 4  low primary air raises local bed temperature the same way.
        #   term 5  leaking water quenches the bed                   (family B)
        bed_target = (850.0
                      + 900.0 * (heat_released - heat_absorbed)
                      + 250.0 * (heat_released - 1.0)
                      + 450.0 * (d.coal_cv_factor - 1.0)
                      + 400.0 * (1.0 - min(1.0, d.primary_air))
                      - 200.0 * leak_rel)
        st["bed_temp_avg"] += (bed_target - st["bed_temp_avg"]) * 0.010

        # Main steam temperature follows the bed with lag, moderated by flow.
        target_ms = NOMINAL["ms_temperature"] + (st["bed_temp_avg"] - 850.0) * 0.35 \
            - (steam - NOMINAL["steam_flow"]) * 0.6
        st["ms_temperature"] += (target_ms - st["ms_temperature"]) * 0.02

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

    if errs:
        raise AssertionError("sim self-test FAILED:\n  " + "\n  ".join(errs))
    print("sim self-test passed "
          f"(clamp floor {M_LIQ_FLOOR_KG:.0f} kg / ceil {M_LIQ_CEIL_KG:.0f} kg).")


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
    Checks 1, 2 and 4b key on pressure movement from the PRE-REWRITE energy
    block (PRESS_GAIN, unsourced) -- PROVISIONAL, re-run after sub-model 2.
    """
    print("\ndirection checks (expected sign -> measured; PROVISIONAL = pre-rewrite energy):")

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
    print(f"  load +10 t/h  [PROVISIONAL]: p peak {r1['pk']:.2f} kg/cm2 "
          f"(dp {r1['dp']:+.2f}, n={r1['n']}); emitted offset {r1['offset']:+.3f} % "
          f"vs -G_sw*dp {r1['predicted']:+.3f} % (expect > 0, swell); "
          f"trace slope {r1['slope']:+.3f} vs {-G_SW_PCT_PER_KGFCM2:+.3f}  "
          f"[{'OK' if ok1 else 'FAIL'}]")

    dec_sim = BoilerSim(_spec("dir_load_dn", 50.0, family="N",
                              schedules=[Schedule(600.0, "load_demand", 57.0, 2.0)]))
    dec = dec_sim.run()
    r2 = _swell_sign(dec_sim, dec, "shrink")
    ok2 = r2["ok"]
    print(f"  load -10 t/h  [PROVISIONAL]: p peak {r2['pk']:.2f} kg/cm2 "
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

    # -- 4b. fuel availability capped -> pressure sags -> throttle -> steam falls
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

    if not all([ok1, ok2, ok3, ok4, ok5]):
        raise AssertionError("direction check FAILED -- a sub-model sign is wrong")
    print("  all five direction checks OK")


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


if __name__ == "__main__":
    _self_test()
    _direction_checks()
    _headline_recheck()
    _mutation_check()
