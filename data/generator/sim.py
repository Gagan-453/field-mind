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
    WATER   d(level)/dt = (feed - steam - blowdown - leak) * K
    ENERGY  pressure and bed temperature respond to heat in vs heat absorbed

Everything here runs OFFLINE on the host. numpy is fine.
=============================================================================
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

# Nominal operating point: 67 TPH, 67 kg/cm2(g), 495 degC.
NOMINAL = {
    "drum_level": 50.0, "feed_water_flow": 67.0, "steam_flow": 67.0,
    "drum_pressure": 66.0, "bed_temp_avg": 850.0, "ms_temperature": 495.0,
}

K_LEVEL = 0.22        # %/min per TPH of net water inflow
FEED_VALVE_MAX_TPH = 82.0   # flow at 100% valve travel; a seized actuator caps this
PRESS_GAIN = 4.0      # kg/cm2 per minute per unit of relative energy imbalance
DT_S = 5.0            # raw sample period


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
        # level rather than being an independent trace.
        self._integral = 0.0
        self._fire = 1.0          # firing rate, relative to nominal

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
    def step(self, t_s: float) -> dict:
        d, st = self.d, self.state
        dt_min = DT_S / 60.0
        self._apply_schedules(t_s)

        # ---- steam demand: the turbine pulls, with slow load swings ----
        swing = 2.0 * math.sin(t_s / 1800.0)          # +/- 2 TPH over 30 min
        # The turbine cannot pass rated flow on sagging pressure. Without this
        # coupling a fuel-side fault drives pressure to zero unchecked, which
        # no real plant does.
        throttle = max(0.3, min(1.0, st["drum_pressure"] / 60.0))
        steam = (d.load_demand + swing) * throttle

        # ================= WATER SIDE =================================
        # Feed controller: PI on drum level. This is a closed loop, so feed
        # RESPONDS to level rather than being an independent trace -- which is
        # what makes family B (leak) look different from family A (feed short).
        err = NOMINAL["drum_level"] - st["drum_level"]
        self._integral = max(-25, min(25, self._integral + err * dt_min * 2.0))
        demand = steam + 3.0 * err + self._integral + d.blowdown_tph
        demand = max(0.0, min(FEED_VALVE_MAX_TPH, demand))

        # THE FAULT ENTERS HERE for family A. A seized actuator limits valve
        # TRAVEL, which caps deliverable FLOW. It does not scale demand -- that
        # distinction matters: a scaled demand would let the controller wind up
        # and recover, whereas a hard cap means feed simply cannot meet steam,
        # and the level falls at a rate the water balance can compute exactly.
        feed = min(demand, d.feed_valve_effectiveness * FEED_VALVE_MAX_TPH)

        # Water (mass) balance -> drum level. This is a genuine integration and
        # the L1 balance check inverts exactly this relation.
        net = feed - steam - d.blowdown_tph - d.leak_tph
        st["drum_level"] = max(0.0, min(100.0,
                                        st["drum_level"] + net * K_LEVEL * dt_min))

        # ================= ENERGY SIDE ================================
        # Combustion control: feeder speed tracks load with a pressure trim.
        # WITHOUT this loop a load reduction leaves fuel unchanged and the bed
        # runs away -- which is not a fault, it is a missing controller, and it
        # would make every normal episode trip.
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

        st["steam_flow"] = steam
        st["feed_water_flow"] = feed

        # ---- measurement noise, per-tag, realistic magnitudes ----
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
