"""
Diagnostician (model agent, a Job): the single agent's L4, unchanged.

Builds the job whose work is Diagnostician.run on THIS tick's evidence. The
Diagnostician object was constructed on the LaneBackend facade, so its call
goes to whichever lane the scheduler picks. It reads the board (facts,
retrieval, findings, belief, trust) and writes nothing: its envelope returns
as a Result, and only the gate puts it on the board.
"""

from __future__ import annotations

from types import SimpleNamespace

from ...agent.l1_symbolize import evidence_packet
from ...agent.orchestrator import evidence_max_facts, wm_summary

NAME = "diagnostician"


def priority_for(level: str) -> int:
    """P1 urgent diagnosis (trip predicted / CRITICAL fact, i.e. triage URGENT),
    else P2 (plan p.10)."""
    return 1 if level == "URGENT" else 2


class DiagnosticianAgent:
    def __init__(self, diag, cfg: dict):
        self.diag = diag
        self.cfg = cfg

    def make_job(self, bb, scheduler, tick: int, level: str, rung: int,
                 submit_s: float):
        facts = bb.read("facts").facts_of(tick)
        retrieved = bb.read("retrieval")
        summary_view = SimpleNamespace(open_findings=bb.read("findings"),
                                       hypotheses=bb.read("belief"),
                                       trusted_tags=bb.read("trust"))

        def work():
            with bb.step(NAME):
                evidence = evidence_packet(
                    facts, max_facts=evidence_max_facts(level, rung))
                return self.diag.run(tick, evidence, dict(retrieved), facts,
                                     wm_summary(summary_view))

        return scheduler.new_job(NAME, evidence_tick=tick,
                                 priority=priority_for(level),
                                 max_answer_tokens=self.cfg["max_tokens"],
                                 submit_s=submit_s, work=work)
