"""
Diagnostician (model agent, a Job).

`multi.compact.schema` off: the single agent's L4, unchanged (Phase 1). The
job's work is Diagnostician.run on THIS tick's evidence; the Diagnostician
object was constructed on the LaneBackend facade, so its call goes to whichever
lane the scheduler picks.

`schema` on (Phase 2 commit 5): the compact prompt (compact.build_diagnosis),
answer format B' capped at multi.answer_caps.diagnostician, one repair call.
The line map built with the prompt travels with the job; the gate expands the
answer through it. The counters (calls, parse failures) stay on the single
agent's Diagnostician, so the run file's diag_calls / parse_failure_rate keep
their meaning.

Reads the board (facts, retrieval, findings, belief, trust, notefacts,
recordfacts) and writes nothing: its envelope returns as a Result, and only the
gate puts it on the board.
"""

from __future__ import annotations

from types import SimpleNamespace

from ...agent.l1_symbolize import evidence_packet
from ...agent.orchestrator import evidence_max_facts, wm_summary
from ...schemas import TAGS
from .. import compact
from ._call import call_model

NAME = "diagnostician"


def priority_for(level: str) -> int:
    """P1 urgent diagnosis (trip predicted / CRITICAL fact, i.e. triage URGENT),
    else P2 (plan p.10)."""
    return 1 if level == "URGENT" else 2


class DiagnosticianAgent:
    def __init__(self, diag, cfg: dict, mcfg: dict | None = None,
                 letters: dict | None = None):
        self.diag = diag
        self.cfg = cfg
        mcfg = mcfg or {}
        self.sw = compact.compact_switches(mcfg.get("compact"))
        self.letters = letters or {}
        self.cap = (mcfg.get("answer_caps") or {}).get("diagnostician", 60)
        self.guard_cpt = mcfg.get("compact_guard_cpt")
        if self.sw["schema"]:
            self.templates = {"body": compact.load_prompt("diag_compact.txt"),
                              "rules_full": compact.load_prompt("diag_rules_full.txt"),
                              "rules_compact": compact.load_prompt("diag_rules_compact.txt")}
            self.repair = compact.load_prompt("repair_lines.txt")

    def make_job(self, bb, scheduler, tick: int, level: str, rung: int,
                 submit_s: float):
        if self.sw["schema"]:
            return self._compact_job(bb, scheduler, tick, level, rung, submit_s)
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

    # ------------------------------------------------------------------
    def _compact_job(self, bb, scheduler, tick, level, rung, submit_s):
        facts = bb.read("facts").facts_of(tick)
        retrieved = bb.read("retrieval")
        belief = bb.read("belief")
        trust = bb.read("trust")
        summary_view = SimpleNamespace(open_findings=bb.read("findings"),
                                       hypotheses=belief, trusted_tags=trust)
        prompt, line_map, hint, info = compact.build_diagnosis(
            self.sw, self.templates, facts=facts,
            level_cap=evidence_max_facts(level, rung), retrieved=dict(retrieved),
            notefacts=dict(bb.read("notefacts")),
            recordfacts=list(bb.read("recordfacts")), belief=list(belief),
            untrusted=sorted(set(TAGS) - set(trust)),
            wm_text=wm_summary(summary_view), now_s=submit_s,
            evidence_tick=tick, letters=self.letters, cap=self.cap,
            guard_cpt=self.guard_cpt)
        line_map["info"] = info
        diag = self.diag

        def work():
            with bb.step(NAME):
                diag.calls += 1
                env, failed = call_model(
                    diag.backend, prompt, NAME, self.cap, hint, NAME, tick,
                    compact.check_diag_answer_shape, repair_template=self.repair,
                    log_prompts=diag.log_prompts)
                diag.parse_failures += failed
                diag.retries += env.retries
                env.retrieved_cases = list(line_map["retrieved_cases"])
                return env

        job = scheduler.new_job(NAME, evidence_tick=tick,
                                priority=priority_for(level),
                                max_answer_tokens=self.cap,
                                submit_s=submit_s, work=work)
        job.line_map = line_map
        return job
