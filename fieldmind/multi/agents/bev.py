"""
bev agent (model agent, Jobs on the bev lane, P3): every use of bev-decider
other than the decider (reports/bev_ideas.md; HUMAN INSTRUCTION 2026-10-17).

One switch per idea, `multi.bev.<idea>`: off | shadow | on.
  off     the earlier code path exactly (no job is made)
  shadow  bev is asked; the gate checks and logs its answer; NOTHING it says
          is used -- for measuring bev and choosing thresholds on the dev set
  on      the checked answer is used by the idea's own rule

A request is bev-decide's /v1/systemone body: {"state", "questions"}. Every
question is a fixed sentence from `multi.bev.questions` (q_root is the
decider's signed sentence; the rest are PROPOSED, report "Questions"). The
state is facts (the decider's lines) or one note's text, never raw readings
(invariant 1). bev generates nothing, so every bev call has decode 0.

This agent builds jobs and parses replies. It writes nothing to the board:
the gate checks each answer (`check_answers`) and only the gate writes.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict

from ...agent.l4_diagnose import est_tokens
from ...runtime.llm_backend import call_record
from ...schemas import AgentEnvelope
from .decider import DeciderAgent

NAME = "bev"            # the blackboard step every bev job runs in
ROLE = "decider"        # the backend role: bev-decide (the mock answers it as bev)
PRIORITY = 3
MODES = ("off", "shadow", "on")
IDEAS = ("explain", "first", "actions", "unknown", "verifier", "notes",
         "text_reader", "rt_fallback", "clear_skip")
CODE_ONLY = ("clear_skip",)                       # no bev call
REALTIME_OK = ("rt_fallback", "clear_skip")       # decision 1: the rest are lockstep only
NEED_FIRST_THRESHOLD = ("first", "rt_fallback")


def switches(mcfg: dict) -> dict[str, str]:
    """`multi.bev` -> {idea: mode}. YAML reads a bare `off` / `on` as a bool."""
    b = (mcfg or {}).get("bev") or {}
    unknown = set(b) - set(IDEAS) - {"noul_threshold", "first_threshold", "questions"}
    if unknown:
        raise ValueError(f"multi.bev: unknown key(s) {sorted(unknown)}")
    out = {}
    for k in IDEAS:
        v = b.get(k, "off")
        v = {False: "off", None: "off", True: "on"}.get(v, v) if not isinstance(v, str) else v
        if v not in MODES:
            raise ValueError(f"multi.bev.{k} must be one of {MODES}, got {v!r}")
        out[k] = v
    return out


def any_bev_call(sw: dict) -> bool:
    return any(m != "off" for k, m in sw.items() if k not in CODE_ONLY)


def state_text(facts) -> str:
    """The facts as the decider shows them (severity order, at most 9 lines)."""
    return DeciderAgent.state_text(facts)


def fact_lines(facts) -> list:
    """The facts behind state_text, in the same order (the options of a
    choice over facts are these, keyed F-id)."""
    from .. import compact
    ranked = sorted(facts, key=lambda f: (compact.SEV_ORDER.get(f.severity, 9), f.id))
    return ranked[:compact.MAX_FACT_LINES]


def choice(instructions: str, criteria: dict) -> dict:
    return {"type": "choice", "instructions": instructions, "criteria": dict(criteria)}


def noul(instructions: str) -> dict:
    return {"type": "noul", "instructions": instructions}


class BevAgent:
    def __init__(self, backend, mcfg: dict, log_prompts: bool = False):
        self.backend = backend
        self.sw = switches(mcfg)
        b = (mcfg or {}).get("bev") or {}
        self.noul_threshold = float(b.get("noul_threshold", 0.5))
        if not 0.0 <= self.noul_threshold <= 1.0:
            raise ValueError("multi.bev.noul_threshold must be in [0, 1]")
        ft = b.get("first_threshold")
        self.first_threshold = None if ft is None else float(ft)
        for k in NEED_FIRST_THRESHOLD:
            if self.sw[k] == "on" and self.first_threshold is None:
                raise ValueError(f"multi.bev.{k}: on needs multi.bev.first_threshold, set from "
                                 f"dev-set shadow runs (bench/bev_calibrate.py); it has no default")
        self.questions = dict(b.get("questions") or {})
        self.log_prompts = log_prompts
        # run-level, per idea: calls, failed, rejected, used (on), shadow (logged only)
        self.stats: dict[str, Counter] = defaultdict(Counter)

    # ------------------------------------------------------------------
    def mode(self, idea: str) -> str:
        return self.sw[idea]

    def active(self, idea: str) -> bool:
        return self.sw[idea] != "off"

    def used(self, idea: str) -> bool:
        return self.sw[idea] == "on"

    def q(self, key: str, **kw) -> str:
        if key not in self.questions:
            raise KeyError(f"multi.bev.questions.{key} is not set")
        return self.questions[key].format(**kw)

    # ------------------------------------------------------------------
    def make_job(self, bb, scheduler, idea: str, tick: int, state: str,
                 questions: dict, submit_s: float, meta: dict | None = None,
                 side: str = "all"):
        """One bev-decide request as a job on the bev lane (`bev_<idea>`)."""
        if idea not in IDEAS or idea in CODE_ONLY:
            raise ValueError(f"no bev call for idea {idea!r}")
        prompt = json.dumps({"state": state, "questions": questions}, ensure_ascii=False)
        spec = {qid: {"type": q["type"], "options": list((q.get("criteria") or {}).keys())}
                for qid, q in questions.items()}
        hint = {"bev": {qid: {**spec[qid], "instructions": q["instructions"]}
                        for qid, q in questions.items()}}

        def work():
            with bb.step(NAME):
                self.stats[idea]["calls"] += 1
                env = self._call(prompt, hint, idea, tick)
                self.stats[idea]["failed"] += env.status != "ok"
                return env

        job = scheduler.new_job(f"bev_{idea}", evidence_tick=tick, priority=PRIORITY,
                                max_answer_tokens=0, submit_s=submit_s, work=work, side=side)
        job.line_map = {"kind": "bev", "idea": idea, "mode": self.sw[idea],
                        "questions": spec, "evidence_tick": tick,
                        "prompt_tokens_est": est_tokens(prompt), **(meta or {})}
        return job

    def _call(self, prompt: str, hint: dict, idea: str, tick: int) -> AgentEnvelope:
        reply = self.backend.generate(prompt, role=ROLE, max_tokens=0, mock_hint=hint)
        env = AgentEnvelope(agent=f"bev_{idea}", tick=tick, latency_ms=reply.latency_ms,
                            backend=reply.backend, model=reply.model,
                            tokens={"prefill": reply.prefill_tokens, "decode": reply.decode_tokens})
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
            answers = json.loads(reply.text)["answers"]
            if not isinstance(answers, dict):
                raise TypeError("answers is not an object")
            env.payload = answers
        except (ValueError, KeyError, TypeError) as e:
            env.status, env.error = "invalid_schema", f"no answers ({e!r})"
            env.payload = {"error": env.error}
        return env

    def run_lockstep(self, bb, scheduler, jobs: list, now_s: float) -> list:
        """Submit and drain (lockstep). bev jobs are the only ones queued here."""
        if not jobs:
            return []
        with bb.step("scheduler"):
            for j in jobs:
                scheduler.submit(j)
            bb.write("jobs", [j.to_dict() for j in jobs], "scheduler")
            return scheduler.run_lockstep(now_s)

    def telemetry(self) -> dict:
        return {"switches": dict(self.sw), "noul_threshold": self.noul_threshold,
                "first_threshold": self.first_threshold,
                "per_idea": {k: dict(v) for k, v in sorted(self.stats.items())}}


# ----------------------------------------------------------------------
def check_answers(payload, spec: dict) -> tuple[bool, str, dict]:
    """(ok, why, answers). Every asked question answered, and nothing else:
    a choice names exactly the offered keys, each probability in [0, 1], its
    `choice` among them (ranking by probability, ties in offered order); a
    yes/no is a number in [0, 1]. One bad question rejects the whole reply."""
    if not isinstance(payload, dict):
        return False, "answers is not an object", {}
    if set(payload) != set(spec):
        return False, f"answered {sorted(payload)}, asked {sorted(spec)}", {}
    out = {}
    for qid, s in spec.items():
        a = payload[qid]
        if not isinstance(a, dict) or a.get("type") != s["type"]:
            return False, f"{qid}: not a {s['type']} answer", {}
        if s["type"] == "noul":
            p = a.get("noul")
            if isinstance(p, bool) or not isinstance(p, (int, float)) or not 0.0 <= p <= 1.0:
                return False, f"{qid}: P(yes) is {p!r}", {}
            out[qid] = {"type": "noul", "p": float(p)}
            continue
        offered = s["options"]
        probs = a.get("probabilities")
        if not isinstance(probs, dict) or set(probs) != set(offered):
            return False, f"{qid}: probabilities name {sorted(probs) if isinstance(probs, dict) else probs}", {}
        for k, v in probs.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0.0 <= v <= 1.0:
                return False, f"{qid}: probability of {k} is {v!r}", {}
        if a.get("choice") not in offered:
            return False, f"{qid}: choice {a.get('choice')!r} was not offered", {}
        ranking = sorted(offered, key=lambda k: (-probs[k], offered.index(k)))
        out[qid] = {"type": "choice", "ranking": ranking,
                    "p": {k: float(v) for k, v in probs.items()}}
    return True, "", out


# ----------------------------------------------------------------------
#  Idea 1, explain: Llama ranks the cases; bev picks each case's citation,
#  the separating case and the notes used. The B' answer is rebuilt from
#  both and then goes through the gate's existing expansion and checks.
# ----------------------------------------------------------------------
def ranked_lines(payload: dict, n_cases: int) -> list[int]:
    """The ranked case lines of a diagnosis answer (rank-only ints or B'
    [line, [facts]] entries): in range, distinct, at most 3, answer order."""
    out = []
    for e in (payload or {}).get("r") or []:
        c = e[0] if isinstance(e, list) and e else e
        if isinstance(c, int) and not isinstance(c, bool) and 1 <= c <= n_cases and c not in out:
            out.append(c)
    return out[:3]


def explain_questions(agent: "BevAgent", lm: dict, ranked: list[int]) -> dict:
    """Q_CITE per ranked case (a choice over the shown fact lines), Q_SEP among
    the ranked cases (2 or more), Q_NOTE per shown raw note line for the top
    case. Option keys are the prompt's own line numbers."""
    from ..compact import first_sentence
    facts = {str(i): t for i, t in enumerate(lm.get("fact_text") or [], 1)}
    cause = {c: first_sentence(lm["cases"][c - 1].get("root_cause") or "") for c in ranked}
    qs = {}
    if len(facts) >= 2:
        for c in ranked:
            qs[f"cite{c}"] = choice(agent.q("q_cite", cause=cause[c]), facts)
    if len(ranked) >= 2:
        qs["sep"] = choice(agent.q("q_sep"), {str(c): cause[c] for c in ranked})
    if ranked:
        for i, (kind, text) in enumerate(zip(lm.get("context_kind") or [],
                                             lm.get("context_text") or []), 1):
            if kind == "note":
                qs[f"note{i}"] = noul(agent.q("q_note", cause=cause[ranked[0]]) + " Note: " + text)
    return qs


def compose_explain(lm: dict, ranked: list[int], answers: dict | None,
                    noul_threshold: float) -> dict:
    """The B' answer from Llama's ranking and bev's checked answers. With one
    fact line, it is the citation (nothing to choose). Without bev's answers
    (failed / rejected): the ranking with no citations, sep null, no notes.
    `x` is always empty: one citation per case cannot say a fact is
    unexplained (decision recorded in reports/bev_ideas.md)."""
    n_facts = len(lm.get("fact_text") or [])
    a = answers or {}
    r = []
    for c in ranked:
        if f"cite{c}" in a:
            r.append([c, [int(a[f"cite{c}"]["ranking"][0])]])
        elif answers is not None and n_facts == 1:
            r.append([c, [1]])
        else:
            r.append([c, []])
    sep = int(a["sep"]["ranking"][0]) if "sep" in a else None
    notes = sorted(int(k[4:]) for k, v in a.items()
                   if k.startswith("note") and v["p"] >= noul_threshold)
    return {"r": r, "sep": sep, "n": notes, "x": []}


def cite_agreement(payload: dict, answers: dict | None) -> float | None:
    """shadow: share of Llama's ranked cases whose bev-picked fact is among
    the facts Llama cited for that case (None when nothing to compare)."""
    if not answers:
        return None
    hits = n = 0
    for e in (payload or {}).get("r") or []:
        if isinstance(e, list) and len(e) == 2 and f"cite{e[0]}" in answers and e[1]:
            n += 1
            hits += int(answers[f"cite{e[0]}"]["ranking"][0]) in e[1]
    return round(hits / n, 3) if n else None


def lines_state(lm: dict) -> str:
    """bev's state for explain: the side's fact lines exactly as shown."""
    return "\n".join(lm.get("fact_text") or []) or "(no facts above threshold)"


# ----------------------------------------------------------------------
#  Idea 2, first (and 7, rt_fallback): on a weak or tied tick bev chooses
#  among the cases the side's prompt shows; with enough probability its
#  ranking is the side's answer and Llama is not called.
# ----------------------------------------------------------------------
def first_questions(agent: "BevAgent", lm: dict) -> dict:
    """Q_ROOT (the decider's signed sentence) over the side prompt's case
    lines, keyed by case id. Fewer than two cases: nothing to ask."""
    from ..compact import first_sentence
    opts = {c["case_id"]: first_sentence(c.get("root_cause") or "")
            for c in lm["cases"] if c.get("case_id")}
    return {"root": choice(agent.q("q_root"), opts)} if len(opts) >= 2 else {}


def compose_first(lm: dict, ranking: list[str]) -> dict:
    """bev's ranking (top 3) as a B' answer over the prompt's case lines, no
    citations (decision 2: with `explain` on, explain adds them)."""
    line = {c["case_id"]: i for i, c in enumerate(lm["cases"], 1)}
    return {"r": [[line[c], []] for c in ranking[:3] if c in line],
            "sep": None, "n": [], "x": []}


def first_envelope(tick: int, payload: dict, bev_env) -> AgentEnvelope:
    """The side answer bev stands in for. It makes no Llama call: no calls,
    no tokens (bev's own call is in its bev_first envelope)."""
    return AgentEnvelope(agent="diagnostician", tick=tick, status="ok", payload=payload,
                         backend="bev", model=bev_env.model,
                         tokens={"prefill": 0, "decode": 0})
