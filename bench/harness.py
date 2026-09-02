"""
=============================================================================
 HARNESS  --  replays an episode tick by tick  (Plan §3.2)
=============================================================================

The harness holds the clock. At each tick the agent may see:
  - sensor samples up to now (rolling 60-minute window, older data summarised)
  - engineer notes and records timestamped AT OR BEFORE now
  - its own world model from the previous tick
  - NOTHING FROM THE FUTURE -- the harness enforces this, which is the whole
    point of tick-based evaluation.

Why tick-based matters for the result: it makes DETECTION LEAD TIME
measurable -- how many minutes before the trip did the agent first say the
right thing. A one-shot benchmark cannot measure that, and lead time is the
metric a plant engineer actually cares about.

Wall-clock replay is accelerated. The agent is measured on COMPUTE PER TICK,
not on how fast the clock moves.
=============================================================================
"""

from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from fieldmind.agent.l0_ingest import SensorWindow
from fieldmind.agent.l1_checks import CheckLayer
from fieldmind.agent.l3_retrieve import Retriever
from fieldmind.agent.l4_diagnose import Diagnostician
from fieldmind.agent.l5_verify import Verifier
from fieldmind.agent.l6_gate import ActionCatalogue, Gate
from fieldmind.agent.orchestrator import Orchestrator
from fieldmind.agent.world_model import new_world_model
from fieldmind.kb.stores import (AssetModel, CaseLibrary, ExperienceStore,
                                 NotesStore)
from fieldmind.runtime.llm_backend import make_backend

EPOCH = datetime(2026, 8, 21, 6, 0, 0)


class Episode:
    """Loads one episode off disk. Nothing here may return future data."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.id = self.path.name
        with open(self.path / "timeseries.csv") as fh:
            self.rows = [{k: float(v) for k, v in r.items()}
                         for r in csv.DictReader(fh)]
        nf = self.path / "notes.jsonl"
        self.notes = [json.loads(l) for l in nf.read_text().splitlines()
                      if l.strip()] if nf.exists() else []
        self.ground_truth = json.loads((self.path / "ground_truth.json").read_text())
        self.records = json.loads((self.path / "records.json").read_text()) \
            if (self.path / "records.json").exists() else {}
        # query.txt: three operator query variants (vague / specific / wrong-
        # premise, notes_gen.build_queries). The agent is handed the SPECIFIC
        # one as the operator's question; the wrong-premise variant is kept for
        # a future T-series sweep. Previously this file was written and never
        # read (known bug 4).
        qf = self.path / "query.txt"
        self.queries = [l.strip() for l in qf.read_text().splitlines()
                        if l.strip()] if qf.exists() else []
        self.operator_query = (self.queries[1] if len(self.queries) >= 2
                               else (self.queries[0] if self.queries else ""))

    def samples_between(self, t0: float, t1: float) -> list[dict]:
        return [r for r in self.rows if t0 <= r["t"] < t1]

    @property
    def duration_s(self) -> float:
        return self.rows[-1]["t"]


def build_agent(cfg: dict, notes: list[dict], records: dict | None = None):
    """Wire the pipeline. One place, so a sweep can rebuild it per configuration.

    `records` is the episode's records.json (coal lab reports, maintenance
    history, boiler-water conductivity log). Eight of the thirty episodes list
    `records` as a required modality; without this argument tier C was
    untestable (known bug 3).
    """
    p = cfg["paths"]
    backend = make_backend(cfg["llm"])          # <-- THE MODEL SWITCH

    asset = AssetModel(Path(p["asset_model"]))
    cases = CaseLibrary(Path(p["case_library"]))
    notes_store = NotesStore(notes)
    experience = ExperienceStore(Path(p["experience"]))
    catalogue = ActionCatalogue(Path(p["action_catalogue"]))

    acfg = cfg["agent"]
    checks = CheckLayer(cfg["checks"])
    retriever = Retriever(asset, cases, notes_store, experience, acfg,
                          records=records or {})
    diag = Diagnostician(backend, acfg)
    ver = Verifier(backend, acfg)
    gate = Gate(catalogue, acfg)
    orch = Orchestrator(checks, retriever, diag, ver, gate, acfg)
    return orch, asset, cases, experience, backend, diag, ver


def run_episode(ep: Episode, cfg: dict, ablate_text: bool = False,
                verbose: bool = False) -> dict:
    """Replay one episode. `ablate_text` removes every note -- that is the T8
    modality ablation, and tier B/C accuracy MUST collapse under it or the
    episode is mislabelled."""
    notes = [] if ablate_text else ep.notes
    # records.json is a separate modality from notes -- text ablation (T8)
    # removes notes, not the coal lab report / conductivity log.
    orch, asset, cases, experience, backend, diag, ver = build_agent(
        cfg, notes, ep.records)
    orch.operator_query = ep.operator_query

    tick_s = cfg["agent"]["tick_period_s"]
    window = SensorWindow(window_min=60.0,
                          sample_period_s=cfg["checks"]["sample_period_s"])
    wm = new_world_model(ep.id, asset.equipment)

    assessments, t0 = [], time.perf_counter()
    n_ticks = int(ep.duration_s // tick_s)

    for k in range(n_ticks):
        t_start, t_end = k * tick_s, (k + 1) * tick_s

        # ---- feed only samples belonging to this tick. The window is the
        #      ONLY channel by which sensor data reaches the agent.
        for row in ep.samples_between(t_start, t_end):
            window.append(row["t"], row)

        if not window.ready(min_minutes=5.0):
            continue                       # still filling; do not guess

        ts = (EPOCH + timedelta(seconds=t_end)).isoformat()
        asmt = orch.tick(wm, window, k, ts, now_s=t_end)
        assessments.append(asmt.to_dict())

        if verbose and (asmt.triage != "QUIET" or k % 40 == 0):
            top = asmt.hypotheses[0]["cause"][:46] if asmt.hypotheses else "-"
            print(f"  t{k:4d} {asmt.state:13s} {asmt.triage:11s} "
                  f"{asmt.headline[:58]:58s} | {top}")

    wall = time.perf_counter() - t0
    return {
        "episode_id": ep.id,
        "backend": cfg["llm"]["backend"],
        "n_ticks": len(assessments),
        "assessments": assessments,
        "ground_truth": ep.ground_truth,
        "wall_clock_s": round(wall, 2),
        "llm_invocation_rate": round(
            sum(a["llm_invoked"] for a in assessments) / max(1, len(assessments)), 3),
        "parse_failure_rate": round(
            diag.parse_failures / max(1, diag.calls), 3),
        "verifier_disagreement_rate": round(
            ver.disagreements / max(1, ver.calls), 3),
        "deadline_miss_rate": round(
            sum(a["deadline_miss"] for a in assessments) / max(1, len(assessments)), 4),
        "ablate_text": ablate_text,
    }
