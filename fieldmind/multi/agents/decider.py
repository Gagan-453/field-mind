"""
Decider (model agent, a Job, P3): bev-decider-0.4B picks among belief's
leading cases (reports/bev_decider.md; human sign-off 2026-10-07).

One `choice` question per call, in the /v1/systemone format bev-decide
serves:
  state     the tick's facts, as the compact diagnosis prompt shows them
            ("[check/severity] detail", severity order, at most 9 lines) --
            facts only, never raw readings (invariant 1)
  options   belief's top `multi.decider.top_k` live cases with a case id, in
            belief's order, each "<case id>: <cause>" (bev cuts an option at
            64 tokens itself)
  question  `multi.decider.question`, one fixed sentence

Called only when its evidence changed (the offered cases, the signature, the
open findings with their severity), as the side diagnosticians are under
split_on_change, so an unchanged tick adds no fresh answer. Fewer than two
offered cases: no call (a choice among one says nothing).

Writes nothing to the board. The gate checks the answer (every offered case
has a probability in [0, 1], nothing else is named) and adds it to the nudge
offsets as one more fresh answer; belief is never written (plan rule: model
answers never write belief).
"""

from __future__ import annotations

import json

from ...agent.l4_diagnose import est_tokens
from ...runtime.llm_backend import call_record
from ...schemas import AgentEnvelope
from .. import compact, merge_rules

NAME = "decider"
ROLE = "decider"
PRIORITY = 3
QUESTION_ID = "root_cause"


class DeciderAgent:
    def __init__(self, backend, dcfg: dict, log_prompts: bool = False):
        self.backend = backend
        self.top_k = int(dcfg["top_k"])
        self.question = str(dcfg["question"])
        if self.top_k < 2:
            raise ValueError("multi.decider.top_k must be at least 2")
        self.log_prompts = log_prompts
        self.calls = 0
        self.failed = 0

    # ------------------------------------------------------------------
    def offered(self, bb) -> list:
        """Belief's top live hypotheses with a case id, belief's order
        (rank_hypotheses: confidence, ties in insertion order)."""
        live = [h for h in bb.read("belief") if not h.retired]
        return [h for h in merge_rules._belief_order(live) if h.case_ref][:self.top_k]

    @staticmethod
    def state_text(facts) -> str:
        ranked = sorted(facts, key=lambda f: (compact.SEV_ORDER.get(f.severity, 9), f.id))
        lines = [f"[{f.check}/{f.severity}] {f.detail}" for f in ranked[:compact.MAX_FACT_LINES]]
        return "\n".join(lines) or "(no facts above threshold)"

    @staticmethod
    def fingerprint(bb, offered_ids: list[str]) -> tuple:
        sig = bb.read("signature").get("signature", {}) or {}
        return (tuple(offered_ids),
                frozenset((t, repr(v)) for t, v in sig.items()),
                frozenset((f.signature_key, f.severity) for f in bb.read("findings")
                          if not f.resolved))

    def request(self, facts, offered) -> str:
        return json.dumps({"state": self.state_text(facts),
                           "questions": {QUESTION_ID: {
                               "type": "choice", "instructions": self.question,
                               "criteria": {h.case_ref: h.cause for h in offered}}}},
                          ensure_ascii=False)

    # ------------------------------------------------------------------
    def make_job(self, bb, scheduler, tick: int, submit_s: float):
        """The tick's decider job, or None (fewer than two cases, or the
        evidence is unchanged since the last checked answer)."""
        offered = self.offered(bb)
        if len(offered) < 2:
            return None
        ids = [h.case_ref for h in offered]
        fp = self.fingerprint(bb, ids)
        if bb.read("decider_answer").get("fingerprint") == fp:
            return None
        prompt = self.request(bb.read("facts").facts_of(tick), offered)

        def work():
            with bb.step(NAME):
                self.calls += 1
                env = self._call(prompt, ids, tick)
                self.failed += env.status != "ok"
                return env

        job = scheduler.new_job(NAME, evidence_tick=tick, priority=PRIORITY,
                                max_answer_tokens=0, submit_s=submit_s, work=work)
        job.line_map = {"kind": "decider", "offered": ids, "fingerprint": fp,
                        "evidence_tick": tick, "prompt_tokens_est": est_tokens(prompt)}
        return job

    def _call(self, prompt: str, ids: list[str], tick: int) -> AgentEnvelope:
        reply = self.backend.generate(prompt, role=ROLE, max_tokens=0,
                                      mock_hint={"options": list(ids), "question": QUESTION_ID})
        env = AgentEnvelope(agent=NAME, tick=tick, latency_ms=reply.latency_ms,
                            backend=reply.backend, model=reply.model,
                            tokens={"prefill": reply.prefill_tokens,
                                    "decode": reply.decode_tokens})
        env.retries = getattr(reply, "retries", 0)
        env.calls.append(call_record(reply))
        env.prompt_tokens = reply.prefill_tokens or est_tokens(prompt)
        if self.log_prompts:
            env.prompt = prompt
            env.raw_reply = reply.text
        if reply.status != "ok":
            env.status, env.error = reply.status, getattr(reply, "error", "")
            env.payload = {"error": env.error or reply.status}
            return env
        try:
            env.payload = json.loads(reply.text)["answers"].get(QUESTION_ID)
            if not isinstance(env.payload, dict):
                raise KeyError(QUESTION_ID)
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            env.status, env.error = "invalid_schema", f"no '{QUESTION_ID}' answer ({e!r})"
            env.payload = {"error": env.error}
        return env


def check_answer(payload: dict, offered: list[str]) -> tuple[bool, str, list[str]]:
    """(ok, why, ranking). A choice answer naming exactly the offered cases,
    each with a probability in [0, 1], and `choice` among them; ranking is
    the offered cases by probability, ties in offered (belief's) order."""
    if not isinstance(payload, dict) or payload.get("type") != "choice":
        return False, "not a choice answer", []
    p = payload.get("probabilities")
    if not isinstance(p, dict) or set(p) != set(offered):
        return False, f"probabilities name {sorted(p) if isinstance(p, dict) else p}, " \
                      f"offered {sorted(offered)}", []
    for k, v in p.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0.0 <= v <= 1.0:
            return False, f"probability of {k} is {v!r}", []
    if payload.get("choice") not in offered:
        return False, f"choice {payload.get('choice')!r} was not offered", []
    ranking = sorted(offered, key=lambda k: (-p[k], offered.index(k)))
    return True, "", ranking
