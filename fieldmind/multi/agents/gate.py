"""
Gate and memory agent (code, every tick): L6 + L7.

The ONLY agent that puts a model answer on the board. For every Result it
  1. drops it if stale (older than one tick -- Phase 1 stub; the "unless that
     side's evidence is unchanged" clause needs sides, Phase 3),
  2. checks its cited fact IDs against the facts of the answer's EVIDENCE
     tick (not the current tick), then folds it in with the single agent's
     own merge / verifier-apply,
and then approves actions, decides escalation, stamps the display-only shown
confidence, publishes the assessment and appends this tick's events.

Writes: status, diagnosis, verdict, events, assessment.

It also publishes a DETERMINISTIC assessment at the end of the hard path
(P0), before any model job: the same approve() on belief's claims. That is
the plan's rule 1 ("the tick never waits for a model"); in Phase 1 it is
timed and recorded as telemetry, and the assessment that is compared and
scored is still the final one, so decisions match the single agent.
"""

from __future__ import annotations

import copy
import dataclasses
import time
from types import SimpleNamespace

from ...agent.l1_symbolize import headline
from ...agent.orchestrator import (fold_diagnosis, initial_claims,
                                   quiet_deadline_miss, rung_marker,
                                   stamp_shown_confidence, tick_deadline_miss)
from ...schemas import Assessment
from .. import compact

NAME = "gate"


class GateMemoryAgent:
    def __init__(self, gate, ver, cfg: dict):
        self.gate = gate
        self.ver = ver
        self.cfg = cfg
        self.hard_deadline_ms = cfg.get("hard_stage_deadline_ms", 200)
        self.tick_budget_ms = cfg.get("tick_period_s", 30) * 1000
        self.stale_dropped: list[dict] = []

    # ------------------------------------------------------------------
    def begin_tick(self, bb, rung: int) -> None:
        """Only the degradation ladder persists across ticks (known bug 1)."""
        bb.write("status", {"degraded_mode": rung_marker(rung)}, NAME)

    def open_assessment(self, bb, tick: int, timestamp: str, state: str,
                        facts: list, level: str) -> Assessment:
        asmt = Assessment(tick=tick, timestamp=timestamp, state=state,
                          headline=headline(facts),
                          facts=[f.to_dict() for f in facts],
                          triage=level,
                          degraded_mode=bb.read("status")["degraded_mode"])
        bb.write("assessment", asmt, NAME)
        return asmt

    def _log_events(self, bb, tick: int, outboxes: tuple) -> None:
        log = bb.mutable("events", NAME)
        for box in outboxes:
            t, events = bb.read(box)
            if t == tick:
                log.extend(events)

    def publish_quiet(self, bb, asmt: Assessment, tick: int, state: str,
                      check_ms: float, t_tick: float) -> None:
        asmt.actions = []
        asmt.tick_latency_ms = (time.perf_counter() - t_tick) * 1000
        asmt.deadline_miss = quiet_deadline_miss(check_ms, self.hard_deadline_ms)
        self._log_events(bb, tick, ("outbox.sensor",))
        bb.write("status", {"tick": tick, "state": state}, NAME)

    # ------------------------------------------------------------------
    def deterministic(self, bb, asmt: Assessment, ranked, ranking, facts,
                      retrieved, state: str) -> tuple[dict, dict]:
        """Belief's claims into the diagnosis slot, and the P0 deterministic
        assessment (telemetry)."""
        asmt.belief_ranking = ranking
        claims = initial_claims(asmt.headline, ranked)
        bb.write("diagnosis", claims, NAME)
        actions, escalate, _ = self.gate.approve(claims["hypotheses"], facts,
                                                 retrieved, state)
        p0 = {"rank1": claims["hypotheses"][0]["case_ref"] if claims["hypotheses"] else None,
              "actions": [a.id for a in actions], "escalate": escalate}
        return claims, p0

    # ------------------------------------------------------------------
    def is_stale(self, result, now_tick: int) -> bool:
        return now_tick - result.evidence_tick > 1

    def _drop_if_stale(self, result, now_tick: int) -> bool:
        if self.is_stale(result, now_tick):
            result.stale = True
            self.stale_dropped.append({"job_id": result.job.job_id,
                                       "agent": result.job.agent,
                                       "evidence_tick": result.evidence_tick,
                                       "now_tick": now_tick})
            return True
        return False

    def fold_diagnosis(self, bb, asmt: Assessment, claims: dict, result,
                       now_tick: int) -> dict:
        env = result.envelope
        asmt.envelopes.append(env.to_dict())
        if self._drop_if_stale(result, now_tick):
            return claims
        evidence_facts = bb.read("facts").facts_of(result.evidence_tick)
        if result.evidence_tick != now_tick:
            # Fact ids are tick-local in the prompt. An answer from an earlier
            # tick is checked, merged and published with STAMPED ids
            # (t84.F3), so L6 can never take it for the current tick's F3.
            env, evidence_facts = self._stamped(env, evidence_facts,
                                                result.evidence_tick)
        claims, degraded = fold_diagnosis(claims, env, evidence_facts,
                                          self.gate, self.cfg)
        bb.write("diagnosis", claims, NAME)
        if degraded is not None:
            bb.write("status", {"degraded_mode": degraded}, NAME)
            asmt.degraded_mode = degraded
        return claims

    @staticmethod
    def _stamped(env, facts, tick: int):
        stamp = lambda i: f"t{tick}.{i}"
        payload = copy.deepcopy(env.payload)
        for h in payload.get("hypotheses", []) or []:
            h["supports"] = [stamp(s) for s in h.get("supports", [])]
        env = dataclasses.replace(env, payload=payload,
                                  cited_facts=[stamp(c) for c in env.cited_facts])
        return env, [dataclasses.replace(f, id=stamp(f.id)) for f in facts]

    def check_notefact(self, result, vocab) -> tuple[bool, str]:
        """A text-reader answer may reach the board only if the call succeeded
        and every value is from the vocabulary. Returns (ok, why)."""
        env = result.envelope
        if env.status != "ok":
            return False, f"{env.status}: {env.error}"
        return compact.check_note_answer(env.payload, vocab)

    def apply_verdict(self, bb, asmt: Assessment, claims: dict, result,
                      now_tick: int) -> dict:
        env = result.envelope
        asmt.envelopes.append(env.to_dict())
        if self._drop_if_stale(result, now_tick):
            return claims
        if env.status == "ok":
            claims = self.ver.apply(claims, env.payload)
        bb.write("verdict", claims, NAME)
        return claims

    # ------------------------------------------------------------------
    def finalize(self, bb, asmt: Assessment, claims: dict, facts, retrieved,
                 state: str, tick: int, check_ms: float, llm_used: bool,
                 t_tick: float) -> float:
        """L6 approve, shown confidence, assemble, L7 write. Returns hard_ms."""
        t0 = time.perf_counter()
        actions, escalate, unexplained = self.gate.approve(
            claims["hypotheses"], facts, retrieved, state)
        hard_ms = check_ms + (time.perf_counter() - t0) * 1000

        shown = stamp_shown_confidence(
            claims, SimpleNamespace(hypotheses=bb.read("belief")))

        asmt.hypotheses = claims["hypotheses"]
        asmt.actions = [a.__dict__ for a in actions]
        asmt.escalate = escalate
        asmt.unexplained = claims.get("unexplained", []) + unexplained
        asmt.confidence = shown[0] if shown else 0.0
        asmt.headline = claims.get("headline") or asmt.headline
        asmt.llm_invoked = llm_used
        asmt.tick_latency_ms = (time.perf_counter() - t_tick) * 1000
        asmt.deadline_miss = tick_deadline_miss(
            hard_ms, asmt.tick_latency_ms, self.hard_deadline_ms,
            self.tick_budget_ms)

        self._log_events(bb, tick, ("outbox.sensor", "outbox.retriever"))
        bb.write("status", {"tick": tick, "state": state}, NAME)
        return hard_ms
