"""
=============================================================================
 MULTI-AGENT ORCHESTRATOR  --  Phase 1: plumbing only, lockstep
 (docs/multi_agent_plan.pdf, "Architecture", "Build order" Phase 1)
=============================================================================

The single agent's pipeline, cut into agents that talk only through the
blackboard, with the model calls run as Jobs on two lanes by the scheduler.
SAME logic, SAME order as fieldmind/agent/orchestrator.Orchestrator.tick:

  gate.begin_tick                                    (status reset)
  P0  sensor -> triage -> [QUIET: gate publishes, done]
      sensor.signature -> retriever+belief -> gate (deterministic assessment)
  P1/P2  diagnostician job  -> gate (evidence-tick citations, merge)
  P3     verifier job       -> gate (verdict)
      gate+memory (approve, shown confidence, assessment, events)

Lockstep: every job finishes inside its tick (the scheduler drains the queue
before the gate runs), so results are comparable to the single agent field
for field. Real time is Session 6.

Every agent step runs inside `bb.step(agent)`; with multi.audit_writes on, a
step that changes a section it does not own raises.
=============================================================================
"""

from __future__ import annotations

import time

from ..agent.orchestrator import top_confidence
from ..schemas import TAGS
from . import compact
from ..runtime.llm_backend import make_backend
from .agents.diagnostician import DiagnosticianAgent
from .agents.gate import GateMemoryAgent
from .agents.retriever import RetrieverAgent
from .agents.sensor import SensorAgent
from .agents.text_reader import TextReaderAgent
from .agents.triage import TriageAgent
from .agents.verifier import VerifierAgent
from .blackboard import Blackboard
from .lanes import SimLane
from .scheduler import Scheduler

MODEL_LEVELS = ("WATCH", "INVESTIGATE", "URGENT")


class MultiOrchestrator:
    def __init__(self, checks, retriever, diag, ver, gate, acfg: dict,
                 mcfg: dict, scheduler: Scheduler):
        self.cfg = acfg
        self.mcfg = mcfg
        self.scheduler = scheduler
        self.sensor = SensorAgent(checks)
        self.triage = TriageAgent(acfg)
        self.retriever = RetrieverAgent(retriever, acfg)
        sw = compact.compact_switches(mcfg.get("compact"))
        letters = {}
        if sw["schema"]:
            import json
            from pathlib import Path
            letters, _ = compact.group_letters(
                json.loads(Path(mcfg["case_groups"]).read_text()),
                [c["case_id"] for c in retriever.cases.cases])
        self.diag = DiagnosticianAgent(diag, acfg, mcfg, letters)
        self.ver = VerifierAgent(ver, acfg, mcfg)
        self.gate = GateMemoryAgent(gate, ver, acfg)
        self.compact = mcfg.get("compact") or {}
        self.text = None
        if self.compact.get("text_reader"):
            vocab = compact.NoteVocab(TAGS, retriever.asset.equipment,
                                      mcfg["text_reader"])
            self.text = TextReaderAgent(diag.backend, retriever.notes, vocab, mcfg,
                                        log_prompts=bool(acfg.get("log_prompts")))
        self.operator_query = ""
        self.rung = 0                       # ladder not built (Session 6)
        self.bb: Blackboard | None = None
        self.last_telemetry: dict = {}
        self.p0_ms: list[float] = []

    def bind(self, wm) -> None:
        self.bb = Blackboard(wm, audit=bool(self.mcfg.get("audit_writes", True)))

    # ===================================================================
    def tick(self, wm, window, tick_no: int, timestamp: str, now_s: float):
        bb = self.bb
        if bb is None or bb.wm is not wm:
            raise RuntimeError("bind(wm) the blackboard before ticking")
        t_tick = time.perf_counter()

        with bb.step("gate"):
            self.gate.begin_tick(bb, self.rung)

        # ---------------- P0 hard path ------------------------------------
        with bb.step("sensor"):
            facts, check_ms = self.sensor.run(bb, window, tick_no)
        with bb.step("triage"):
            level, _reason, state = self.triage.run(bb, facts)
        with bb.step("gate"):
            asmt = self.gate.open_assessment(bb, tick_no, timestamp, state,
                                             facts, level)

        if level == "QUIET" or self.rung >= 5:
            with bb.step("gate"):
                self.gate.publish_quiet(bb, asmt, tick_no, state, check_ms, t_tick)
            p0 = (time.perf_counter() - t_tick) * 1000
            # A note can arrive on a quiet tick. It is read then, AFTER the
            # assessment is out: the tick never waits for a model.
            text = self._read_notes(bb, tick_no, now_s, facts)
            self._record(tick_no, p0, [], None, text=text)
            return asmt

        with bb.step("sensor"):
            signature = self.sensor.signature(bb, window, facts)
        with bb.step("retriever"):
            retrieved, ranked, ranking = self.retriever.run(
                bb, facts, signature, now_s, level, tick_no, self.operator_query)
        with bb.step("gate"):
            claims, p0_asmt = self.gate.deterministic(
                bb, asmt, ranked, ranking, facts, retrieved, state)
        p0 = (time.perf_counter() - t_tick) * 1000   # deterministic assessment out

        # ---------------- model jobs (lockstep) ---------------------------
        # Notes first: in lockstep every note that has arrived is read before
        # the diagnosis prompt is built (this does NOT hold in real time).
        text = self._read_notes(bb, tick_no, now_s, facts)
        results = []
        llm_used = False
        submit_s = now_s
        if self.rung < 5 and level in MODEL_LEVELS:
            with bb.step("scheduler"):
                jobs = self.diag.make_jobs(bb, self.scheduler, tick_no, level,
                                           self.rung, submit_s)
                for job in jobs:
                    self.scheduler.submit(job)
                bb.write("jobs", [j.to_dict() for j in jobs], "scheduler")
                got = self.scheduler.run_lockstep(now_s)
            # Phase 3 with split_on_change: a tick whose sides are all unchanged
            # makes no diagnosis call; llm_invoked is then set by the verifier
            llm_used = bool(jobs)
            results += got
            if self.diag.split:
                # Phase 3: both sides' answers, checked one by one, merged once
                with bb.step("gate"):
                    claims = self.gate.fold_sides(bb, asmt, claims, got, tick_no,
                                                  reuse=self.diag.on_change)
            else:
                for r in got:
                    with bb.step("gate"):
                        claims = self.gate.fold_diagnosis(bb, asmt, claims, r, tick_no)
            # the verifier is submitted when the LAST side answer is in
            for r in got:
                if r.finish_s is not None:
                    submit_s = max(submit_s, r.finish_s)

        top_conf = top_confidence(claims)
        if self.ver.should_run(level, top_conf, self.rung):
            with bb.step("scheduler"):
                job = self.ver.make_job(bb, self.scheduler, tick_no, claims,
                                        submit_s)
                self.scheduler.submit(job)
                bb.write("jobs", [job.to_dict()], "scheduler")
                got = self.scheduler.run_lockstep(now_s)
            results += got
            # a verifier call is a model call: llm_invoked keeps its Phase 2
            # meaning ("a model was called this tick")
            llm_used = llm_used or bool(got)
            for r in got:
                with bb.step("gate"):
                    claims = self.gate.apply_verdict(bb, asmt, claims, r, tick_no)

        # ---------------- gate + memory -----------------------------------
        with bb.step("gate"):
            hard_ms = self.gate.finalize(bb, asmt, claims, facts, retrieved,
                                         state, tick_no, check_ms, llm_used,
                                         t_tick)
        self._record(tick_no, p0, results, p0_asmt, hard_ms, text=text)
        return asmt

    # ===================================================================
    def _read_notes(self, bb, tick: int, now_s: float, facts) -> list[dict]:
        """One text-reader job per note that has arrived and is unread. The
        gate checks each answer; the text reader writes the checked note-fact."""
        if self.text is None:
            return []
        notes = self.text.arrivals(bb, now_s)
        if not notes:
            return []
        active = {t for f in facts for t in f.tags if f.severity != "INFO"}
        with bb.step("scheduler"):
            jobs = [self.text.make_job(bb, self.scheduler, tick, n, active, now_s)
                    for n in notes]
            for job in jobs:
                self.scheduler.submit(job)
            bb.write("jobs", [j.to_dict() for j in jobs], "scheduler")
            got = self.scheduler.run_lockstep(now_s)
        out = []
        for r in got:
            checked = self.gate.check_notefact(r, self.text.vocab)
            with bb.step("text_reader"):
                entry = self.text.accept(bb, r, checked)
            out.append({"notefact": entry, "envelope": r.envelope.to_dict(),
                        "result": r.telemetry()})
        return out

    def _record(self, tick, p0_ms, results, p0_asmt, hard_ms=None,
                text=None) -> None:
        self.p0_ms.append(p0_ms)
        self.last_telemetry = {
            "p0_ms": round(p0_ms, 4),
            "p0_deadline_miss": p0_ms > self.cfg.get("hard_stage_deadline_ms", 200),
            "hard_ms": None if hard_ms is None else round(hard_ms, 4),
            "deterministic": p0_asmt,
            "results": [r.telemetry() for r in results],
            "text": text or [],
            "compact": list(self.gate.compact_log),
        }
        self.gate.compact_log.clear()

    def run_telemetry(self) -> dict:
        p = sorted(self.p0_ms)
        pct = (lambda q: round(p[min(len(p) - 1, int(q * len(p)))], 4)) if p else (lambda q: None)
        return {"placement": self.scheduler.placement,
                "compact_switches": dict(self.diag.sw),
                "split": self.diag.split,
                "split_on_change": self.diag.on_change,
                "ver_incomplete_verdicts": self.gate.ver_incomplete,
                "ver_over_limit": self.gate.ver_over_limit,
                "lanes": [l.telemetry() for l in self.scheduler.lanes],
                "jobs_dispatched": len(self.scheduler.dispatched),
                "jobs_replaced": len(self.scheduler.replaced),
                "stale_dropped": list(self.gate.stale_dropped),
                "text_calls": self.text.calls if self.text else 0,
                "text_parse_failures": self.text.parse_failures if self.text else 0,
                "notefacts_rejected": self.text.rejected if self.text else 0,
                "p0_ms_p50": pct(0.5), "p0_ms_p95": pct(0.95),
                "p0_ms_max": p[-1] if p else None,
                "audit_writes": self.bb.audit if self.bb else None,
                "section_writes": dict(self.bb.writes) if self.bb else {}}


# =======================================================================
def make_lanes(cfg: dict, shared_backend) -> list[SimLane]:
    """One SimLane per multi.lanes entry, in config order (ties go to the
    first). Same model on both lanes (plan rule 3): on llamaserver each lane
    gets its own server URL; on any other backend the lanes share one."""
    lanes = []
    for name, lc in cfg["multi"]["lanes"].items():
        if cfg["llm"]["backend"] == "llamaserver":
            llm = dict(cfg["llm"])
            llm["llamaserver"] = {**cfg["llm"].get("llamaserver", {}),
                                  "url": lc["url"], "lane": name}
            backend = make_backend(llm)
        else:
            backend = shared_backend
        lanes.append(SimLane(name, backend, lc["prefill_tok_s"], lc["decode_tok_s"]))
    return lanes

