"""
Verifier (model agent, a Job, P3): the single agent's L5, unchanged.

Runs on the gate's checked diagnosis claims and the evidence tick's facts.
Writes nothing to the board: the gate applies its answer to the verdict.
"""

from __future__ import annotations

NAME = "verifier"
PRIORITY = 3


class VerifierAgent:
    def __init__(self, ver, cfg: dict):
        self.ver = ver
        self.cfg = cfg

    def should_run(self, level: str, top_conf: float, rung: int) -> bool:
        return rung < 1 and self.ver.should_run(level, top_conf)

    def make_job(self, bb, scheduler, tick: int, claims: dict, submit_s: float):
        facts = bb.read("facts").facts_of(tick)

        def work():
            with bb.step(NAME):
                return self.ver.run(tick, claims, facts)

        return scheduler.new_job(NAME, evidence_tick=tick, priority=PRIORITY,
                                 max_answer_tokens=self.cfg["max_tokens"],
                                 submit_s=submit_s, work=work)
