"""
=============================================================================
 EPISODE BUILDER  (Plan §3.3 catalogue, §3.4 tiers, §3.5 distractors)
=============================================================================

Builds all 30 episodes: 6 normal + 24 faults across five families.

    N  6  normal, load swings, soot-blow          tests false positives
    A  6  water side, feed path                   feed < steam, heat side untouched
    B  5  water side, leak                        feed > steam yet level only holds
    C  6  fuel / heat side                        pressure and bed fall together
    D  4  bed temperature                         bed climbs at steady load
    E  3  slow drift                              nothing crosses a limit

MODALITY-NECESSITY TIERS (§3.4) -- the most important dataset decision. If
every episode were solvable from the time series alone we would have built a
time-series benchmark with text stapled on, and the multimodal claim would be
empty. So:

    tier A  12  solvable from the numbers alone
    tier B  12  needs the numbers plus ONE text source
    tier C   6  needs two sources, or memory of a past episode

The evaluator checks tier compliance directly (T8): run with text removed and
confirm tier B/C accuracy collapses. If it does not, the episode is
mislabelled and gets rebuilt.

Run:  python -m data.generator.episode_build --out data/episodes
=============================================================================
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

from .sim import BoilerSim, EpisodeSpec, Schedule
from .notes_gen import build_notes, build_records, build_queries


# =======================================================================
#  THE 30-EPISODE CATALOGUE
# =======================================================================

def catalogue() -> list[EpisodeSpec]:
    eps: list[EpisodeSpec] = []
    S = Schedule

    # ---- N: normal (6). Steady operation and load swings. Tests Q5. ----
    for i in range(6):
        eps.append(EpisodeSpec(
            episode_id=f"ep_N{i+1:02d}_normal", family="N", tier="A",
            duration_min=[45, 60, 60, 90, 45, 75][i],
            schedules=([S(1200, "load_demand", 60.0, 10.0)] if i in (2, 4) else []),
            root_cause_id="NONE", root_cause_text="No fault. Normal operation.",
            correct_action_ids=[], seed=100 + i))

    # ---- A: water side, feed path (6). Feed cannot deliver. ----
    a_specs = [
        ("fcv_seize", 0.77, 8.0, "RCA-01", "FCV actuator stem seizure",
         ["ACT-014", "ACT-002", "ACT-031"], "B", ["timeseries", "notes"]),
        ("fcv_seize_fast", 0.62, 3.0, "RCA-01", "FCV actuator stem seizure",
         ["ACT-014", "ACT-002", "ACT-031"], "A", ["timeseries"]),
        ("bfp_suction", 0.55, 4.0, "RCA-02", "BFP suction loss from low deaerator level",
         ["ACT-005", "ACT-002", "ACT-031"], "B", ["timeseries", "notes"]),
        ("strainer_choke", 0.79, 25.0, "RCA-03", "Feed strainer progressively choked",
         ["ACT-007", "ACT-014"], "C", ["timeseries", "notes", "records"]),
        ("fcv_caught", 0.74, 6.0, "RCA-01", "FCV actuator stem seizure, operator intervened",
         ["ACT-014", "ACT-031"], "A", ["timeseries"]),
        ("fcv_seize_repeat", 0.75, 8.0, "RCA-01", "FCV actuator stem seizure",
         ["ACT-014", "ACT-002", "ACT-031"], "C", ["timeseries", "notes"]),
    ]
    for i, (name, eff, ramp, rc, txt, acts, tier, mods) in enumerate(a_specs):
        onset = 600.0
        sch = [S(onset, "feed_valve_effectiveness", eff, ramp)]
        caught = "caught" in name
        if caught:
            # The operator opens the bypass: effectiveness partly recovers.
            sch.append(S(onset + 1500, "feed_valve_effectiveness", 0.95, 4.0))
        eps.append(EpisodeSpec(
            episode_id=f"ep_A{i+1:02d}_{name}", family="A", tier=tier,
            duration_min=[55, 45, 50, 120, 60, 55][i], schedules=sch,
            root_cause_id=rc, root_cause_text=txt, required_modalities=mods,
            correct_action_ids=acts, fault_onset_s=onset, caught_in_time=caught,
            contributory=(["CBD valve left ~40% open at handover"] if i == 0 else []),
            repeat_of=("ep_A01_fcv_seize" if name.endswith("repeat") else None),
            dropout_tag=("feed_water_flow" if i == 4 else None),
            injection_present=(i == 1), seed=200 + i))

    # ---- B: water side, leak (5). Feed exceeds steam yet level only holds. ----
    b_specs = [
        ("tube_leak", 3.5, 12.0, "C", ["timeseries", "notes", "records"]),
        ("tube_leak_fast", 6.0, 4.0, "A", ["timeseries"]),
        ("tube_leak_slow", 2.2, 30.0, "B", ["timeseries", "notes"]),
        ("cbd_left_open", 4.0, 2.0, "B", ["timeseries", "notes"]),
        ("tube_leak_repeat", 3.5, 12.0, "C", ["timeseries", "notes"]),
    ]
    for i, (name, leak, ramp, tier, mods) in enumerate(b_specs):
        cbd = "cbd" in name
        eps.append(EpisodeSpec(
            episode_id=f"ep_B{i+1:02d}_{name}", family="B", tier=tier,
            duration_min=[90, 45, 150, 60, 90][i],
            schedules=[S(900, "leak_tph", leak, ramp)],
            root_cause_id=("RCA-01b" if cbd else "RCA-04"),
            root_cause_text=("CBD valve left open at handover" if cbd
                             else "Water wall tube erosion and split"),
            required_modalities=mods,
            correct_action_ids=(["ACT-021", "ACT-002"] if cbd
                                else ["ACT-009", "ACT-031", "ACT-002"]),
            fault_onset_s=900.0,
            repeat_of=("ep_B01_tube_leak" if name.endswith("repeat") else None),
            dropout_tag=("drum_level" if i == 2 else None), seed=300 + i))

    # ---- C: fuel / heat side (6). Pressure and bed fall together. ----
    c_specs = [
        ("wet_coal", 0.80, 15.0, "RCA-05", "Wet coal bridging in the hopper",
         ["ACT-011", "ACT-012"], "C", ["timeseries", "notes", "records"]),
        ("feeder_trip", 0.62, 1.0, "RCA-06", "Coal feeder 2 tripped on overload",
         ["ACT-012", "ACT-002"], "A", ["timeseries"]),
        ("wet_coal_mild", 0.88, 25.0, "RCA-05", "Wet coal bridging in the hopper",
         ["ACT-011", "ACT-012"], "B", ["timeseries", "notes"]),
        ("feeder_trip_caught", 0.65, 1.0, "RCA-06", "Coal feeder 2 tripped, restarted",
         ["ACT-012", "ACT-002"], "A", ["timeseries"]),
        ("low_cv_coal", 0.84, 20.0, "RCA-05", "Low calorific value coal consignment",
         ["ACT-011", "ACT-018"], "C", ["timeseries", "records"]),
        ("wet_coal_repeat", 0.80, 15.0, "RCA-05", "Wet coal bridging in the hopper",
         ["ACT-011", "ACT-012"], "B", ["timeseries", "notes"]),
    ]
    for i, (name, hi, ramp, rc, txt, acts, tier, mods) in enumerate(c_specs):
        sch = [Schedule(900, "fuel_availability", hi, ramp)]
        caught = "caught" in name
        if caught:
            sch.append(Schedule(900 + 1200, "fuel_availability", 1.15, 3.0))
        eps.append(EpisodeSpec(
            episode_id=f"ep_C{i+1:02d}_{name}", family="C", tier=tier,
            duration_min=[75, 45, 90, 60, 100, 75][i], schedules=sch,
            root_cause_id=rc, root_cause_text=txt, required_modalities=mods,
            correct_action_ids=acts, fault_onset_s=900.0, caught_in_time=caught,
            repeat_of=("ep_C01_wet_coal" if name.endswith("repeat") else None),
            dropout_tag=("drum_pressure" if i == 4 else None),
            injection_present=(i == 2), seed=400 + i))

    # ---- D: bed temperature (4). Bed climbs toward the 940 degC trip. ----
    d_specs = [
        ("high_cv_coal", "coal_cv_factor", 1.16, 12.0, "RCA-07",
         "High-CV coal fired without feeder recalibration",
         ["ACT-018", "ACT-019", "ACT-002"], "C", ["timeseries", "records"]),
        ("low_primary_air", "primary_air", 0.80, 8.0, "RCA-08",
         "Primary air damper left low after maintenance",
         ["ACT-019", "ACT-018"], "B", ["timeseries", "notes"]),
        ("high_cv_severe", "coal_cv_factor", 1.24, 6.0, "RCA-07",
         "High-CV coal fired without feeder recalibration",
         ["ACT-018", "ACT-019", "ACT-002"], "A", ["timeseries"]),
        ("low_pa_caught", "primary_air", 0.84, 8.0, "RCA-08",
         "Primary air damper left low, corrected by operator",
         ["ACT-019"], "A", ["timeseries"]),
    ]
    for i, (name, drv, tgt, ramp, rc, txt, acts, tier, mods) in enumerate(d_specs):
        sch = [Schedule(600, drv, tgt, ramp)]
        caught = "caught" in name
        if caught:
            sch.append(Schedule(600 + 1500, drv, 1.0, 5.0))
        eps.append(EpisodeSpec(
            episode_id=f"ep_D{i+1:02d}_{name}", family="D", tier=tier,
            duration_min=[70, 60, 50, 65][i], schedules=sch,
            root_cause_id=rc, root_cause_text=txt, required_modalities=mods,
            correct_action_ids=acts, fault_onset_s=600.0, caught_in_time=caught,
            seed=500 + i))

    # ---- E: slow drift (3). THE FAMILY THAT MATTERS MOST. ----
    # Nothing ever crosses a threshold. The only signal is a slow change in the
    # RELATIONSHIP between tags at constant load. This is also the case that
    # breaks naive self-learning, because an adaptive baseline will happily
    # learn the drift as the new normal (guarded by baseline freeze, §8.2).
    # Absorption drops only a FEW PERCENT. It has to be gentle enough that
    # nothing crosses a limit -- that is the definition of family E, and an
    # episode here that trips is a mislabelled episode, not a severe one.
    for i, (absorb, ramp, dur) in enumerate([(0.986, 120.0, 240),
                                             (0.989, 180.0, 200),
                                             (0.985, 90.0, 180)]):
        eps.append(EpisodeSpec(
            episode_id=f"ep_E{i+1:02d}_fouling_drift", family="E", tier="B",
            duration_min=dur,
            schedules=[Schedule(300, "heat_absorption", absorb, ramp)],
            root_cause_id="RCA-09",
            root_cause_text="Progressive heat transfer surface fouling",
            required_modalities=["timeseries", "records"],
            correct_action_ids=["ACT-024", "ACT-025"],
            fault_onset_s=300.0, seed=600 + i))

    return eps


# =======================================================================
#  Ground truth, derived from the simulation rather than asserted
# =======================================================================

def state_timeline(spec: EpisodeSpec, rows: list[dict]) -> list:
    """Label each second range by the state the PHYSICS is actually in.

    Derived from the simulated tag values, not from the fault schedule alone:
    a fault that was injected but has not yet moved anything measurable is
    genuinely still NORMAL, and labelling it otherwise would make detection
    lead time (T6) meaningless.
    """
    tl, cur, start = [], "NORMAL", 0.0
    for r in rows:
        lvl, bed = r["drum_level"], r["bed_temp_avg"]
        gap = abs(r["feed_water_flow"] - r["steam_flow"])
        if lvl < 10 or bed > 940:
            s = "TRIP_IMMINENT"
        elif lvl < 20 or bed > 880 or r["drum_pressure"] < 55:
            s = "ALARM"
        elif abs(lvl - 50) > 6 or abs(bed - 850) > 25 or gap > 4:
            s = "DEVIATION"
        else:
            s = "NORMAL"
        if s != cur:
            tl.append([start, r["t"], cur])
            cur, start = s, r["t"]
    tl.append([start, rows[-1]["t"], cur])
    return tl


def build_episode(spec: EpisodeSpec, out_dir: Path) -> dict:
    d = out_dir / spec.episode_id
    d.mkdir(parents=True, exist_ok=True)
    rng = random.Random(spec.seed)

    # ---- 1. time series ----
    sim = BoilerSim(spec)
    rows = sim.run()
    with open(d / "timeseries.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- 2. notes, records, queries ----
    notes = build_notes(spec, rows, rng)
    with open(d / "notes.jsonl", "w") as fh:
        for n in notes:
            fh.write(json.dumps(n) + "\n")
    # sub-model 3: the sampled boiler-water conductivity log goes in records.json
    # (not one of the six frozen tags). L3 does not read it yet -- known bug 3.
    wchem = sim.water_chemistry_log(rng)
    (d / "records.json").write_text(
        json.dumps(build_records(spec, rng, wchem), indent=2))
    (d / "query.txt").write_text("\n".join(build_queries(spec)))

    # ---- 3. ground truth, emitted BY the generator ----
    tl = state_timeline(spec, rows)
    trip = next((s for s, _, st in tl if st == "TRIP_IMMINENT"), None)
    gt = {
        "episode_id": spec.episode_id, "family": spec.family, "tier": spec.tier,
        "duration_min": spec.duration_min, "tick_period_s": 30,
        "required_modalities": spec.required_modalities,
        "fault_onset_t": spec.fault_onset_s, "trip_t": trip,
        "root_cause_id": spec.root_cause_id,
        "root_cause_text": spec.root_cause_text,
        "contributory": spec.contributory,
        "state_timeline": tl,
        "correct_action_ids": spec.correct_action_ids,
        "distractor_note_ids": [n["id"] for n in notes if n.get("distractor")],
        "repeat_of_episode_id": spec.repeat_of,
        "injection_present": spec.injection_present,
        "dropout_tag": spec.dropout_tag,
        "caught_in_time": spec.caught_in_time,
        "_provenance": "SYNTHETIC. Generated by data/generator. Not measured plant data.",
    }
    (d / "ground_truth.json").write_text(json.dumps(gt, indent=2))
    return gt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/episodes")
    ap.add_argument("--only", default="", help="substring filter on episode id")
    args = ap.parse_args()

    out = Path(args.out)
    specs = [s for s in catalogue() if args.only in s.episode_id]
    fams: dict[str, int] = {}
    for spec in specs:
        gt = build_episode(spec, out)
        fams[spec.family] = fams.get(spec.family, 0) + 1
        print(f"  {spec.episode_id:34s} tier {spec.tier}  "
              f"{spec.duration_min:5.0f} min  trip_t={gt['trip_t']}")
    print(f"\n{len(specs)} episodes written to {out}")
    print("by family:", dict(sorted(fams.items())))


if __name__ == "__main__":
    main()
