"""
=============================================================================
 ORCHESTRATOR  --  one tick, start to finish  (Plan §2, §7, §11.5)
=============================================================================

PLAIN PYTHON. NOT A MODEL. It decides which agents run, in what order, with
what budget.

  L0 Ingest              read samples into the rolling window          ~0
  L1 Deterministic       limit/rate/balance/validity/pattern -> Facts  ~ms
  L2 Triage              decide if the expensive stages run at all     ~ms
  L3 Retrieval           signature match + note search                 embed
  L4 Diagnosis           Diagnostician agent                           LLM
  L5 Verification        Verifier agent                                LLM
  L6 Action gate         validate, look up actions, decide escalation  ~ms
  L7 Memory write        update world model, checkpoint                ~ms

The single most important structural idea: the language model never sees raw
numbers, and never has the last word. L1 turns numbers into facts, L6 turns
the model's answer into an approved action. The model works in the middle.

THE TICK NEVER FAILS. Every model path has a deterministic fallback, and a
deadline miss is a recorded metric, not a hidden error.
=============================================================================
"""

from __future__ import annotations

import time

from ..schemas import Assessment, TAGS
from . import world_model as wmod
from .l1_symbolize import build_signature, evidence_packet, headline
from .l1_checks import _slope_per_min
from .l2_triage import triage


class Orchestrator:
    def __init__(self, checks, retriever, diagnostician, verifier, gate, cfg):
        self.checks = checks
        self.retriever = retriever
        self.diag = diagnostician
        self.ver = verifier
        self.gate = gate
        self.cfg = cfg
        self.policy = cfg.get("policy", "sequential")   # sequential|pipelined|conditional
        # The operator's question for this episode (query.txt, known bug 4).
        # Set by the harness after construction; "" when there is none.
        self.operator_query = ""
        self.tick_budget_ms = cfg.get("tick_period_s", 30) * 1000
        self.hard_deadline_ms = cfg.get("hard_stage_deadline_ms", 200)
        self.llm_budget_ms = cfg.get("llm_budget_ms", 8000)
        # Degradation ladder rung, 0 = full pipeline (Plan §11.5)
        self.rung = 0

    # ===================================================================
    def tick(self, wm, window, tick_no: int, timestamp: str,
             now_s: float) -> Assessment:
        t_tick = time.perf_counter()

        # ---------------- L1: deterministic checks (HARD stage) ----------
        t0 = time.perf_counter()
        facts = self.checks.run(window, tick_no, wm.trusted_tags)
        hard_ms = (time.perf_counter() - t0) * 1000

        # A tag flagged by VALIDITY leaves the trusted set. Any balance that
        # depended on it is reported as SUSPENDED, never silently skipped.
        for f in facts:
            if f.check == "VALIDITY":
                wm.trusted_tags.discard(f.tags[0])

        # Cache latest values for the trip-prediction extrapolation in triage.
        for tag in TAGS:
            v = window.latest(tag)
            if v is not None:
                wm.residuals[f"last_{tag}"] = v

        wmod.update_findings(wm, facts, tick_no)
        wmod.update_baselines(wm, window, tick_no)

        # ---------------- L2: triage (the cost controller) ---------------
        level, reason = triage(facts, wm, self.cfg)
        state = wmod.derive_state(facts, level, wm)

        asmt = Assessment(tick=tick_no, timestamp=timestamp, state=state,
                          headline=headline(facts),
                          facts=[f.to_dict() for f in facts],
                          triage=level, degraded_mode=wm.degraded_mode)

        # ---- QUIET: stop here. No LLM. This is what keeps average cost low.
        if level == "QUIET" or self.rung >= 5:
            asmt.actions = []
            asmt.tick_latency_ms = (time.perf_counter() - t_tick) * 1000
            asmt.deadline_miss = hard_ms > self.hard_deadline_ms
            wm.tick = tick_no
            wm.state = state
            return asmt

        # ---------------- L3: retrieval ----------------------------------
        slopes = self._slopes(window)
        signature = build_signature(facts, slopes)
        retrieved = self.retriever.retrieve(facts, signature, now_s, level,
                                            operator_query=self.operator_query)

        # Deterministic belief update runs BEFORE the model. If the LLM never
        # answers, we still have ranked hypotheses from signature matching
        # alone -- that is the phase-3 baseline and it is the safe floor.
        wmod.update_hypotheses(wm, facts, retrieved["cases"], tick_no)
        ranked = wmod.rank_hypotheses(wm, top=3)
        claims = {"headline": asmt.headline,
                  "hypotheses": [{"rank": i + 1, "cause": h.cause,
                                  "confidence": h.confidence,
                                  "supports": h.supports,
                                  "case_ref": h.case_ref,
                                  "discriminator": h.discriminator}
                                 for i, h in enumerate(ranked)],
                  "unexplained": []}

        # ---------------- L4: Diagnostician (SOFT stage) -----------------
        envelopes = []
        llm_used = False
        if self.rung < 5 and level in ("WATCH", "INVESTIGATE", "URGENT"):
            evidence = evidence_packet(
                facts, max_facts=6 if (level == "URGENT" or self.rung >= 2) else 12)
            env = self.diag.run(tick_no, evidence, retrieved, facts,
                                self._wm_summary(wm))
            envelopes.append(env.to_dict())
            llm_used = True

            if env.status == "ok":
                cit = self.gate.check_citations(env.cited_facts, facts)
                if cit["faithfulness"] >= self.cfg.get("min_faithfulness", 0.5):
                    claims = self._merge(claims, env.payload)
                else:
                    # The model cited facts that do not exist. Its ranking is
                    # not trustworthy, so we keep the deterministic one and
                    # record why. This is the T3 failure path.
                    claims["unexplained"].append(
                        f"diagnostician cited non-existent facts {cit['invalid']}; "
                        f"deterministic ranking retained")
            else:
                # timeout / invalid_schema -> deterministic output, marked.
                wm.degraded_mode = f"llm_{env.status}"
                asmt.degraded_mode = wm.degraded_mode

        # ---------------- L5: Verifier (SOFT stage) ----------------------
        top_conf = claims["hypotheses"][0]["confidence"] if claims["hypotheses"] else 0.0
        if self.rung < 1 and self.ver.should_run(level, top_conf):
            venv = self.ver.run(tick_no, claims, facts)
            envelopes.append(venv.to_dict())
            if venv.status == "ok":
                claims = self.ver.apply(claims, venv.payload)

        # ---------------- L6: action gate (HARD stage) -------------------
        t0 = time.perf_counter()
        actions, escalate, unexplained = self.gate.approve(
            claims["hypotheses"], facts, retrieved, state)
        hard_ms += (time.perf_counter() - t0) * 1000

        # ---------------- assemble --------------------------------------
        asmt.hypotheses = claims["hypotheses"]
        asmt.actions = [a.__dict__ for a in actions]
        asmt.escalate = escalate
        asmt.unexplained = claims.get("unexplained", []) + unexplained
        asmt.confidence = top_conf
        asmt.headline = claims.get("headline") or asmt.headline
        asmt.llm_invoked = llm_used
        asmt.envelopes = envelopes
        asmt.tick_latency_ms = (time.perf_counter() - t_tick) * 1000

        # C1: HARD stages must meet their deadline on EVERY tick, miss rate 0.
        # C2: end-to-end p95 within the tick period.
        asmt.deadline_miss = (hard_ms > self.hard_deadline_ms or
                              asmt.tick_latency_ms > self.tick_budget_ms)

        # ---------------- L7: memory write -------------------------------
        wm.tick = tick_no
        wm.state = state
        return asmt

    # ===================================================================
    #  Degradation ladder (Plan §11.5). Each rung is a measurable
    #  operating point, and the ladder IS the mixed-criticality
    #  contribution made concrete: SOFT stages degrade by SUBSTITUTION,
    #  HARD stages (L1, L6) always survive.
    # ===================================================================
    LADDER = [
        "full pipeline, NPU, 1B + Verifier",
        "Verifier becomes conditional",
        "context 4096 -> 2048, retrieval depth reduced",
        "Diagnostician moves NPU -> CPU",
        "Diagnostician 1B -> 270M",
        "LLM off entirely; deterministic facts and rule-derived actions only",
    ]

    def degrade(self, wm, reason: str) -> str:
        """Step down one rung. Called on thermal or energy pressure."""
        if self.rung < len(self.LADDER) - 1:
            self.rung += 1
        if self.rung >= 2:
            self.cfg["retrieval"]["k_notes"] = 3
            self.cfg["retrieval"]["k_cases"] = 3
        if self.rung >= 1:
            self.ver.cfg["verifier"] = "conditional"
        wm.degraded_mode = f"rung{self.rung}:{self.LADDER[self.rung]}"
        return wm.degraded_mode

    def recover(self, wm) -> None:
        self.rung = max(0, self.rung - 1)
        wm.degraded_mode = None if self.rung == 0 else \
            f"rung{self.rung}:{self.LADDER[self.rung]}"

    # ===================================================================
    @staticmethod
    def _slopes(window) -> dict:
        """Per-tag slope over the last 10 minutes, for the signature."""
        out = {}
        n = int(10 * 60 / window.dt_s)
        for tag in TAGS:
            s = window.series(tag)
            out[tag] = _slope_per_min(s[-n:], window.dt_s) if len(s) >= 6 else 0.0
        return out

    @staticmethod
    def _wm_summary(wm) -> str:
        """A few tokens of carried belief. Deliberately terse: the world model
        is large and most of it is not decision-relevant this tick."""
        open_f = [f.detail for f in wm.open_findings if not f.resolved][:3]
        hyps = [f"{h.cause}({h.confidence:.2f})"
                for h in wmod.rank_hypotheses(wm, 2)]
        untrusted = sorted(set(TAGS) - wm.trusted_tags)
        parts = []
        if open_f:
            parts.append("open findings: " + "; ".join(open_f))
        if hyps:
            parts.append("current hypotheses: " + ", ".join(hyps))
        if untrusted:
            parts.append("UNTRUSTED TAGS: " + ", ".join(untrusted))
        return " | ".join(parts) or "no prior findings this episode"

    @staticmethod
    def _merge(deterministic: dict, model: dict) -> dict:
        """Model ranking wins on ORDER and WORDING; the deterministic layer
        wins on which fact ids are cited. That split is the whole design: the
        model is allowed to reason, not to assert evidence."""
        out = dict(model)
        out.setdefault("unexplained", [])
        out["unexplained"] += deterministic.get("unexplained", [])
        if not out.get("hypotheses"):
            out["hypotheses"] = deterministic["hypotheses"]
        for i, h in enumerate(out["hypotheses"]):
            h["rank"] = i + 1
            h["confidence"] = float(h["confidence"])
        return out
