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

import copy
import time

from ..agent.orchestrator import top_confidence
from ..schemas import TAGS
from . import compact
from ..runtime.llm_backend import make_backend
from .agents import bev as bevmod
from .agents.bev import BevAgent
from .agents.decider import DeciderAgent
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
        if self.diag.raw_notes and (mcfg.get("compact") or {}).get("text_reader"):
            raise ValueError("multi.compact.note_source raw needs the model text reader "
                             "off (multi.compact.text_reader: false)")
        self.ver = VerifierAgent(ver, acfg, mcfg)
        self.gate = GateMemoryAgent(gate, ver, acfg)
        self.gate.raw_notes = self.diag.raw_notes
        self.compact = mcfg.get("compact") or {}
        from .merge_rules import RULES, flat_case_ids as merge_rules_flat
        self.gate.merge_rule = mcfg.get("merge_rule", "model")
        # hybrid: the cases the model may never lead with or nudge (no moving signature)
        self.gate.flat_ids = merge_rules_flat(retriever.cases.cases)
        if self.gate.merge_rule not in RULES:
            raise ValueError(f"multi.merge_rule must be one of {RULES}")
        if self.gate.merge_rule != "model" and not mcfg.get("split"):
            raise ValueError("merge_rule other than 'model' needs multi.split "
                             "(it is applied to the combined side answers)")
        # bev-decider (reports/bev_decider.md): off = the earlier behaviour
        # exactly (no job, no section written, no telemetry key).
        self.decider = None
        dcfg = mcfg.get("decider") or {}
        if dcfg.get("enabled"):
            if self.gate.merge_rule not in ("nudge", "hybrid"):
                raise ValueError("multi.decider needs merge_rule 'nudge' or 'hybrid' (its "
                                 "pick enters as a capped offset, never as the ranking)")
            if not any(getattr(l, "kind", "llm") == "decider" for l in scheduler.lanes):
                raise ValueError("multi.decider needs a lane of kind 'decider' "
                                 "(multi.lanes.<lane>.kind: decider)")
            self.decider = DeciderAgent(diag.backend, dcfg,
                                        log_prompts=bool(acfg.get("log_prompts")),
                                        library={c["case_id"]: c for c in retriever.cases.cases})
            self.gate.publish_model_ranking = self.decider.candidates == "union"
            self.gate.decider_guard_flat = bool(dcfg.get("guard_flat", True))
        self.text = None
        if self.compact.get("text_reader"):
            vocab = compact.NoteVocab(TAGS, retriever.asset.equipment,
                                      mcfg["text_reader"])
            self.text = TextReaderAgent(diag.backend, retriever.notes, vocab, mcfg,
                                        log_prompts=bool(acfg.get("log_prompts")))
        # bev ideas (reports/bev_ideas.md): every switch off = the earlier
        # behaviour exactly (no job, no section written, no telemetry key).
        self.bev = BevAgent(diag.backend, mcfg, log_prompts=bool(acfg.get("log_prompts")))
        if self.bev.active("verifier") and not self.ver.sw["ver_schema"]:
            raise ValueError("multi.bev.verifier needs multi.compact.ver_schema on (its verdict "
                             "is the compact verifier's answer format)")
        if bevmod.any_bev_call(self.bev.sw):
            if not any(getattr(l, "kind", "llm") == "decider" for l in scheduler.lanes):
                raise ValueError("multi.bev needs a lane of kind 'decider' "
                                 "(multi.lanes.<lane>.kind: decider) for bev-decide")
            if scheduler.placement == "fixed" and "bev" not in scheduler.fixed_placement:
                raise ValueError("multi.bev with fixed placement needs "
                                 "multi.fixed_placement.bev (the bev lane)")
        self.operator_query = ""
        self.rung = 0                       # ladder not built (Session 6)
        self.bb: Blackboard | None = None
        self.last_telemetry: dict = {}
        self.p0_ms: list[float] = []
        self._t_tick = None
        self._stage_hist: dict[str, list] = {}   # agent -> per-tick ms (ticks it ran)
        self._tick_ms: list[float] = []
        self._audit_ms = 0.0

    def bind(self, wm) -> None:
        self.bb = Blackboard(wm, audit=bool(self.mcfg.get("audit_writes", True)))

    # ===================================================================
    def tick(self, wm, window, tick_no: int, timestamp: str, now_s: float):
        bb = self.bb
        if bb is None or bb.wm is not wm:
            raise RuntimeError("bind(wm) the blackboard before ticking")
        t_tick = self._t_tick = time.perf_counter()

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
            pre = []
            if self.bev.active("first"):
                jobs, pre, bev_res = self._first(bb, asmt, jobs, tick_no, now_s)
                results += bev_res
            with bb.step("scheduler"):
                for job in jobs:
                    self.scheduler.submit(job)
                bb.write("jobs", [j.to_dict() for j in jobs], "scheduler")
                got = self.scheduler.run_lockstep(now_s)
            if self.bev.active("first"):
                self._first_agreement(got)
            got = pre + got
            # Phase 3 with split_on_change: a tick whose sides are all unchanged
            # makes no diagnosis call; llm_invoked is then set by the verifier
            llm_used = bool(jobs) or bool(pre)
            self._take_skips()
            results += got
            if self.bev.active("explain"):
                results += self._explain(bb, asmt, got, tick_no, now_s)
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

        # bev-decider: belief's leaders to bev-decide on its own lane, submitted
        # with the tick (it reads belief, not the diagnosis); checked by the
        # gate, then counted by apply_rule's nudge
        if self.decider is not None and self.rung < 5 and level in MODEL_LEVELS:
            with bb.step("scheduler"):
                job = self.decider.make_job(bb, self.scheduler, tick_no, now_s)
                got = []
                if job is not None:
                    self.scheduler.submit(job)
                    bb.write("jobs", [job.to_dict()], "scheduler")
                    got = self.scheduler.run_lockstep(now_s)
            for r in got:
                with bb.step("gate"):
                    self.gate.fold_decider(bb, asmt, r, tick_no)
            results += got
            llm_used = llm_used or bool(got)

        if self.gate.merge_rule != "model":
            with bb.step("gate"):
                claims = self.gate.apply_rule(bb, claims, tick_no)

        top_conf = top_confidence(claims)
        if self.ver.should_run(level, top_conf, self.rung):
            asked = claims
            if self.bev.used("verifier"):
                got, bev_res = self._bev_verify(bb, asmt, claims, tick_no, now_s)
                results += bev_res
                llm_used = llm_used or bool(bev_res)
            else:
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
            if self.bev.mode("verifier") == "shadow":
                results += self._bev_verify(bb, asmt, asked, tick_no, now_s, shadow_of=got)[1]

        drop = frozenset()
        if self.bev.active("actions") or self.bev.active("unknown"):
            drop, bev_res = self._actions_unknown(bb, asmt, claims, facts, retrieved,
                                                  state, tick_no, now_s)
            results += bev_res
            llm_used = llm_used or bool(bev_res)

        # ---------------- gate + memory -----------------------------------
        with bb.step("gate"):
            hard_ms = self.gate.finalize(bb, asmt, claims, facts, retrieved,
                                         state, tick_no, check_ms, llm_used,
                                         t_tick, drop_actions=drop)
        self._record(tick_no, p0, results, p0_asmt, hard_ms, text=text)
        return asmt

    # ===================================================================
    #  REAL-TIME MODE (Phase 4 demonstration subset): the tick never waits.
    #  `self.rt` is a fieldmind.multi.realtime.RealtimeRunner, set by the
    #  harness. Lockstep (`tick`) is untouched.
    # ===================================================================
    def start_realtime(self, runner) -> None:
        if self.gate.merge_rule != "model":
            raise NotImplementedError("merge_rule other than 'model' is lockstep "
                                      "only (accuracy-fix work)")
        if not (self.diag.split and self.diag.on_change):
            raise ValueError("real-time mode needs multi.split and multi.split_on_change "
                             "(answers are cached per side and re-used until they "
                             "arrive again)")
        lock = [k for k, m in self.bev.sw.items() if m != "off" and k not in bevmod.REALTIME_OK]
        if lock:
            raise NotImplementedError(f"multi.bev {lock}: lockstep only (reports/bev_ideas.md, "
                                      f"decision 1); in real time only {bevmod.REALTIME_OK}")
        self.rt = runner
        self._held: list = []           # side answers / verdicts that arrived on a QUIET tick
        self._inflight: dict = {}       # side -> fingerprint of its queued or running job
        self._text_inflight: set = set()

    def tick_realtime(self, wm, window, tick_no: int, timestamp: str,
                      now_s: float, tick_wall_s: float | None = None):
        bb, rt = self.bb, self.rt
        if bb is None or bb.wm is not wm:
            raise RuntimeError("bind(wm) the blackboard before ticking")
        # a late answer is accepted while its side's evidence is unchanged; its
        # citations need the facts of its evidence tick, so keep more of them
        bb.keep_fact_ticks(int(self.mcfg.get("realtime_fact_ticks", 40)))
        t_tick = self._t_tick = time.perf_counter()
        with bb.step("gate"):
            self.gate.begin_tick(bb, self.rung)
        with bb.step("sensor"):
            facts, check_ms = self.sensor.run(bb, window, tick_no)
        with bb.step("triage"):
            level, _reason, state = self.triage.run(bb, facts)
        with bb.step("gate"):
            asmt = self.gate.open_assessment(bb, tick_no, timestamp, state, facts, level)

        # ---- whatever the lanes finished since the last tick (no waiting)
        arrived = rt.drain()
        text = self._accept_text(bb, [r for r in arrived if r.job.agent == "text_reader"])
        for r in arrived:
            side = r.job.side
            if r.job.agent.startswith("diag_") and self._inflight.get(side) is not None \
                    and not rt.in_flight(r.job.agent, side):
                self._inflight.pop(side, None)
        model = self._held + [r for r in arrived if r.job.agent != "text_reader"]
        submitted = []

        if level == "QUIET" or self.rung >= 5:
            self._held = model                   # folded on the next model tick (or stale)
            with bb.step("gate"):
                self.gate.publish_quiet(bb, asmt, tick_no, state, check_ms, t_tick)
            submitted += self._submit_notes(bb, tick_no, now_s, facts, tick_wall_s)
            p0 = (time.perf_counter() - t_tick) * 1000
            self._record(tick_no, p0, arrived, None, text=text)
            self.last_telemetry["submitted"] = submitted
            return asmt
        self._held = []

        with bb.step("sensor"):
            signature = self.sensor.signature(bb, window, facts)
        with bb.step("retriever"):
            retrieved, ranked, ranking = self.retriever.run(
                bb, facts, signature, now_s, level, tick_no, self.operator_query)
        with bb.step("gate"):
            claims, p0_asmt = self.gate.deterministic(
                bb, asmt, ranked, ranking, facts, retrieved, state)

        # ---- fold: side answers (cache, stale rule), then verdicts
        sides_in = [r for r in model if r.job.agent.startswith("diag_")]
        verdicts = [r for r in model if r.job.agent == "verifier"]
        with bb.step("gate"):
            claims = self.gate.fold_sides(bb, asmt, claims, sides_in, tick_no, reuse=True)
        fresh = any(not r.stale and r.envelope.status == "ok" for r in sides_in)
        for r in verdicts:
            with bb.step("gate"):
                claims = self.gate.apply_verdict(bb, asmt, claims, r, tick_no)

        # ---- submit: changed sides (not already queued with the same evidence)
        if self.rung < 5 and level in MODEL_LEVELS:
            with bb.step("scheduler"):
                jobs = [j for j in self.diag.make_jobs(bb, self.scheduler, tick_no, level,
                                                       self.rung, now_s)
                        if self._inflight.get(j.side) != j.line_map["fingerprint"]]
                for j in jobs:
                    rt.submit(j, tick_wall_s)
                    self._inflight[j.side] = j.line_map["fingerprint"]
                if jobs:
                    bb.write("jobs", [j.to_dict() for j in jobs], "scheduler")
            self._take_skips()
            submitted += [{"job": j.job_id, "agent": j.agent, "side": j.side,
                           "fp": hash(j.line_map["fingerprint"]) & 0xFFFFFFFF,
                           "wall_s": round(j.wall_submit, 4)} for j in jobs]
            if fresh and self.ver.should_run(level, top_confidence(claims), self.rung):
                with bb.step("scheduler"):
                    vj = self.ver.make_job(bb, self.scheduler, tick_no,
                                           copy.deepcopy(claims), now_s)
                    rt.submit(vj, tick_wall_s)
                    bb.write("jobs", [vj.to_dict()], "scheduler")
                submitted.append({"job": vj.job_id, "agent": vj.agent, "side": vj.side,
                                  "wall_s": round(vj.wall_submit, 4)})
        submitted += self._submit_notes(bb, tick_no, now_s, facts, tick_wall_s)

        llm_used = bool(submitted) or bool(model)
        with bb.step("gate"):
            hard_ms = self.gate.finalize(bb, asmt, claims, facts, retrieved,
                                         state, tick_no, check_ms, llm_used, t_tick)
        p0 = (time.perf_counter() - t_tick) * 1000      # the whole tick: nothing waits
        self._record(tick_no, p0, arrived, p0_asmt, hard_ms, text=text)
        self.last_telemetry["submitted"] = submitted
        return asmt

    def _explain(self, bb, asmt, got, tick_no: int, now_s: float) -> list:
        """Idea 1 (reports/bev_ideas.md): for every successful side answer, ask
        bev for each ranked case's citation, the separating case and the notes
        used (one request per side). on: the answer is rebuilt from Llama's
        ranking and bev's checked picks BEFORE the gate expands and checks it
        as usual. shadow: logged with its agreement with Llama's citations;
        the answer is untouched. Returns the bev results (telemetry)."""
        import dataclasses
        jobs, pairs = [], []
        for r in got:
            env, lm = r.envelope, r.job.line_map
            if env.status != "ok" or not isinstance(env.payload, dict):
                continue
            ranked = bevmod.ranked_lines(env.payload, len(lm["cases"]))
            qs = bevmod.explain_questions(self.bev, lm, ranked) if ranked else {}
            if not qs:
                if self.bev.used("explain"):    # nothing to ask: the ranking alone
                    r.envelope = dataclasses.replace(env, payload=bevmod.compose_explain(
                        lm, ranked, {}, self.bev.noul_threshold))
                continue
            jobs.append(self.bev.make_job(bb, self.scheduler, "explain", lm["evidence_tick"],
                                          bevmod.lines_state(lm), qs, now_s,
                                          meta={"side": lm["side"], "ranked": ranked},
                                          side=lm["side"] or "all"))
            pairs.append((r, ranked))
        done = {x.job.job_id: x for x in self.bev.run_lockstep(bb, self.scheduler, jobs, now_s)}
        for job, (r, ranked) in zip(jobs, pairs):
            with bb.step("gate"):
                answers = self.gate.fold_bev(bb, asmt, done[job.job_id], tick_no, self.bev)
            rec = self.gate.compact_log[-1]
            if self.bev.used("explain"):
                r.envelope = dataclasses.replace(r.envelope, payload=bevmod.compose_explain(
                    r.job.line_map, ranked, answers, self.bev.noul_threshold))
                rec["composed"] = r.envelope.payload
                self.bev.stats["explain"]["used"] += 1
            else:
                rec["cite_agreement"] = bevmod.cite_agreement(r.envelope.payload, answers)
                self.bev.stats["explain"]["shadow"] += 1
        return list(done.values())

    def _first(self, bb, asmt, jobs, tick_no: int, now_s: float):
        """Idea 2 (reports/bev_ideas.md): on a weak or tied tick (belief alone,
        merge_rules.regime) ask bev to choose among each side prompt's cases.
        on: when its top probability >= first_threshold, its ranking is that
        side's answer (no citations; explain adds them) and the side's Llama
        job is not submitted. shadow: logged; Llama runs as usual and its top
        case is compared afterwards. Returns (jobs to submit, stand-in
        results, bev results)."""
        from . import merge_rules
        from .jobs import Result
        live = [h for h in bb.read("belief") if not h.retired]
        reg = merge_rules.regime(live)
        if reg not in ("weak", "tie"):
            return jobs, [], []
        asks = []
        for j in jobs:
            qs = bevmod.first_questions(self.bev, j.line_map)
            if qs:
                asks.append((j, self.bev.make_job(
                    bb, self.scheduler, "first", tick_no, bevmod.lines_state(j.line_map), qs,
                    now_s, meta={"side": j.line_map["side"], "regime": reg},
                    side=j.line_map["side"] or "all")))
        done = {x.job.job_id: x for x in
                self.bev.run_lockstep(bb, self.scheduler, [b for _, b in asks], now_s)}
        keep, pre = list(jobs), []
        self._first_pending = {}
        for j, b in asks:
            with bb.step("gate"):
                answers = self.gate.fold_bev(bb, asmt, done[b.job_id], tick_no, self.bev)
            rec = self.gate.compact_log[-1]
            if not answers:
                continue
            ranking, p = answers["root"]["ranking"], answers["root"]["p"]
            rec["p_top"] = p[ranking[0]]
            if self.bev.used("first") and p[ranking[0]] >= self.bev.first_threshold:
                keep.remove(j)
                env = bevmod.first_envelope(tick_no, bevmod.compose_first(j.line_map, ranking),
                                            done[b.job_id].envelope)
                pre.append(Result(job=j, envelope=env, evidence_tick=j.evidence_tick, lane=None,
                                  queue_wait_ms=0.0, start_s=None, finish_s=None,
                                  tick_epoch_s=now_s))
                rec["replaced_llama"] = True
                self.bev.stats["first"]["used"] += 1
            else:
                rec["replaced_llama"] = False
                self.bev.stats["first"]["shadow" if not self.bev.used("first") else "below_threshold"] += 1
                self._first_pending[j.job_id] = (rec, ranking[0])
        return keep, pre, list(done.values())

    def _first_agreement(self, got) -> None:
        """first, Llama called anyway: does Llama's top case equal bev's?"""
        pend = getattr(self, "_first_pending", {})
        for r in got:
            if r.job.job_id in pend and r.envelope.status == "ok":
                rec, bev_top = pend[r.job.job_id]
                lines = bevmod.ranked_lines(r.envelope.payload, len(r.job.line_map["cases"]))
                llama_top = r.job.line_map["cases"][lines[0] - 1]["case_id"] if lines else None
                rec["llama_top"], rec["agree_top"] = llama_top, llama_top == bev_top
        self._first_pending = {}

    def _actions_unknown(self, bb, asmt, claims, facts, retrieved, state,
                         tick_no: int, now_s: float):
        """Ideas 3 and 4 (reports/bev_ideas.md), on the claims about to be
        published. actions: yes/no per approved, unprotected action (L6's own
        approve, previewed; it is pure); on: those under noul_threshold are
        dropped in finalize. unknown: Q_ROOT over the top 3 causes + NONE; on:
        the display flag `unknown_fault` (P(NONE) >= noul_threshold) in
        `bev_flags`. Neither touches belief, the ranking or plant state.
        Returns (action ids to drop, bev results)."""
        from .compact import first_sentence
        hyps = claims["hypotheses"]
        state_txt = bevmod.state_text(facts)
        jobs = []
        if self.bev.active("actions"):
            acts, _, _ = self.gate.gate.approve(hyps, facts, retrieved, state)
            top = first_sentence(hyps[0].get("cause") or "") if hyps else "unknown"
            qs = bevmod.action_questions(self.bev, acts, self.gate.gate.cat, top)
            if qs:
                jobs.append(self.bev.make_job(bb, self.scheduler, "actions", tick_no, state_txt,
                                              qs, now_s, meta={"about": sorted(qs)}))
        if self.bev.active("unknown"):
            qs = bevmod.unknown_questions(self.bev, hyps)
            if qs:
                jobs.append(self.bev.make_job(bb, self.scheduler, "unknown", tick_no, state_txt,
                                              qs, now_s))
        done = self.bev.run_lockstep(bb, self.scheduler, jobs, now_s)
        drop, flags = set(), {}
        for res in done:
            idea = res.job.line_map["idea"]
            with bb.step("gate"):
                answers = self.gate.fold_bev(bb, asmt, res, tick_no, self.bev)
            rec = self.gate.compact_log[-1]
            if not answers:
                continue
            if idea == "actions":
                say_no = sorted(q[4:] for q, v in answers.items()
                                if v["p"] < self.bev.noul_threshold)
                rec["would_drop"] = say_no
                if self.bev.used("actions"):
                    drop |= set(say_no)
            else:
                p_none = answers["root"]["p"][bevmod.NONE_KEY]
                rec["p_none"] = p_none
                rec["unknown_fault"] = p_none >= self.bev.noul_threshold
                if self.bev.used("unknown"):
                    flags = {"tick": tick_no, "unknown_fault": rec["unknown_fault"],
                             "p_none": p_none}
            self.bev.stats[idea]["used" if self.bev.used(idea) else "shadow"] += 1
        if flags:
            with bb.step("gate"):
                bb.write("bev_flags", flags, "gate")
            self._bev_flags = flags
        return frozenset(drop), done

    def _bev_verify(self, bb, asmt, claims, tick_no: int, now_s: float, shadow_of=None):
        """Idea 5 (reports/bev_ideas.md): one yes/no per claim the compact
        verifier would show (Q_SUPPORTS); if any fails, a second request picks
        the strongest contradiction (Q_CONTRA). on: the verdict, in the compact
        verifier's answer format, stands in for Gemma's and goes through the
        gate's expansion and Verifier.apply unchanged. shadow (`shadow_of` =
        Gemma's results, already applied): logged with the per-claim agreement.
        Returns (stand-in results, bev results)."""
        from .compact import build_verification, first_sentence
        from .jobs import Result
        from ..schemas import AgentEnvelope
        facts = bb.read("facts").facts_of(tick_no)
        _, lm, _ = build_verification(self.ver.sw, self.ver.templates, facts=facts,
                                      claims=claims, evidence_tick=tick_no)
        if not lm["claims"]:
            return [], []
        state, contra_opts = bevmod.ver_state(lm, facts)
        t = self.bev.noul_threshold
        job = self.bev.make_job(bb, self.scheduler, "verifier", tick_no, state,
                                bevmod.ver_questions(self.bev, lm), now_s)
        bres = self.bev.run_lockstep(bb, self.scheduler, [job], now_s)
        with bb.step("gate"):
            answers = self.gate.fold_bev(bb, asmt, bres[0], tick_no, self.bev)
        rec = self.gate.compact_log[-1]
        if not answers:
            return [], bres
        contra = None
        failing = sorted((int(k[5:]) for k, a in answers.items() if a["p"] < t))
        if failing and len(contra_opts) >= 2:
            claim = first_sentence(lm["claims"][failing[0] - 1] or "")
            job2 = self.bev.make_job(bb, self.scheduler, "verifier", tick_no, state,
                                     {"contra": bevmod.choice(self.bev.q("q_contra", claim=claim),
                                                              contra_opts)}, now_s)
            more = self.bev.run_lockstep(bb, self.scheduler, [job2], now_s)
            bres += more
            with bb.step("gate"):
                a2 = self.gate.fold_bev(bb, asmt, more[0], tick_no, self.bev)
            if a2:
                contra = int(a2["contra"]["ranking"][0])
        verdict = bevmod.compose_verdict(answers, t, contra)
        rec["verdict"] = verdict
        if shadow_of is not None:
            gem = {}
            for r in shadow_of:
                for c in (r.envelope.payload or {}).get("checks", []) if r.envelope.status == "ok" else []:
                    gem[c["claim"]] = c["verdict"][0]            # "p" | "f"
            pairs = [(v, gem.get(lm["claims"][line - 1])) for line, v in verdict["v"]]
            pairs = [(a, b) for a, b in pairs if b is not None]
            rec["agree"] = round(sum(a == b for a, b in pairs) / len(pairs), 3) if pairs else None
            self.bev.stats["verifier"]["shadow"] += 1
            return [], bres
        self.bev.stats["verifier"]["used"] += 1
        self.ver.ver.calls += 1        # verdicts, so verifier_disagreement_rate keeps its denominator
        stand = self.scheduler.new_job("verifier", evidence_tick=tick_no, priority=3,
                                       max_answer_tokens=0, submit_s=now_s)
        stand.line_map = lm
        env = AgentEnvelope(agent="verifier", tick=tick_no, status="ok", payload=verdict,
                            backend="bev", model=bres[0].envelope.model,
                            tokens={"prefill": 0, "decode": 0})
        return [Result(job=stand, envelope=env, evidence_tick=tick_no, lane=None,
                       queue_wait_ms=0.0, start_s=None, finish_s=None, tick_epoch_s=now_s)], bres

    def _take_skips(self) -> None:
        """clear_skip records of this tick into the gate's log and the bev stats."""
        for rec in self.diag.skip_log:
            self.gate.compact_log.append(rec)
            self.bev.stats["clear_skip"]["used" if rec["mode"] == "on" else "shadow"] += 1
        self.diag.skip_log.clear()

    def _submit_notes(self, bb, tick, now_s, facts, tick_wall_s) -> list:
        """Real time: one text-reader job per arrived, unread note not already
        queued; read in the background on its lane."""
        if self.text is None:
            return []
        notes = [n for n in self.text.arrivals(bb, now_s)
                 if n.get("id") not in self._text_inflight]
        if not notes:
            return []
        active = {t for f in facts for t in f.tags if f.severity != "INFO"}
        with bb.step("scheduler"):
            jobs = [self.text.make_job(bb, self.scheduler, tick, n, active, now_s)
                    for n in notes]
            for j, n in zip(jobs, notes):
                self.rt.submit(j, tick_wall_s)
                self._text_inflight.add(n.get("id"))
            bb.write("jobs", [j.to_dict() for j in jobs], "scheduler")
        return [{"job": j.job_id, "agent": j.agent, "side": j.side,
                 "wall_s": round(j.wall_submit, 4)} for j in jobs]

    def _accept_text(self, bb, results) -> list[dict]:
        out = []
        for r in results:
            checked = self.gate.check_notefact(r, self.text.vocab)
            with bb.step("text_reader"):
                entry = self.text.accept(bb, r, checked)
            self._text_inflight.discard(r.job.line_map["note"].get("id"))
            out.append({"notefact": entry, "envelope": r.envelope.to_dict(),
                        "result": r.telemetry()})
        return out

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
        stage, audit = self.bb.take_stage_ms() if self.bb else ({}, 0.0)
        tick_ms = ((time.perf_counter() - self._t_tick) * 1000
                   if self._t_tick is not None else None)
        for k, v in stage.items():
            self._stage_hist.setdefault(k, []).append(v)
        if tick_ms is not None:
            self._tick_ms.append(tick_ms)
        self._audit_ms += audit
        self.last_telemetry = {
            "p0_ms": round(p0_ms, 4),
            "p0_deadline_miss": p0_ms > self.cfg.get("hard_stage_deadline_ms", 200),
            "hard_ms": None if hard_ms is None else round(hard_ms, 4),
            "deterministic": p0_asmt,
            "results": [r.telemetry() for r in results],
            "text": text or [],
            "compact": list(self.gate.compact_log),
            # commit 3 (reports/bev_ideas.md): per-agent step ms on the tick
            # thread, nested steps subtracted; audit snapshots apart; the whole
            # tick. Laptop times until the agent code runs on the board.
            "stage_ms": stage, "audit_ms": audit,
            **({"bev_flags": self.__dict__.pop("_bev_flags")} if "_bev_flags" in self.__dict__ else {}),
            "tick_ms": None if tick_ms is None else round(tick_ms, 4),
        }
        self.gate.compact_log.clear()

    def run_telemetry(self) -> dict:
        p = sorted(self.p0_ms)
        pct = (lambda q: round(p[min(len(p) - 1, int(q * len(p)))], 4)) if p else (lambda q: None)
        extra = {} if self.decider is None else {"decider": {
            "calls": self.decider.calls, "failed": self.decider.failed,
            "rejected": self.gate.decider_rejected, "top_k": self.decider.top_k,
            "candidates": self.decider.candidates, "guard_flat": self.gate.decider_guard_flat}}
        if any(m != "off" for m in self.bev.sw.values()):
            extra["bev"] = self.bev.telemetry()
        return {**extra, "placement": self.scheduler.placement,
                "compact_switches": dict(self.diag.sw),
                "split": self.diag.split,
                "split_on_change": self.diag.on_change,
                "grammar": self.diag.grammar,
                "ver_incomplete_verdicts": self.gate.ver_incomplete,
                "accepted_late_unchanged_evidence": self.gate.accepted_late,
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
                "stage_ms": {k: _summ(v) for k, v in sorted(self._stage_hist.items())},
                "tick_ms": _summ(self._tick_ms),
                "audit_ms_total": round(self._audit_ms, 3),
                "realtime": self.rt.telemetry() if getattr(self, "rt", None) else None,
                "audit_writes": self.bb.audit if self.bb else None,
                "section_writes": dict(self.bb.writes) if self.bb else {}}


def _summ(xs: list) -> dict:
    """n, total, p50, p95, max of per-tick ms (telemetry)."""
    if not xs:
        return {"n": 0}
    s = sorted(xs)
    q = lambda f: round(s[min(len(s) - 1, int(f * len(s)))], 4)   # noqa: E731
    return {"n": len(s), "total": round(sum(s), 3), "p50": q(0.5), "p95": q(0.95),
            "max": round(s[-1], 4)}


# =======================================================================
def make_lanes(cfg: dict, shared_backend) -> list[SimLane]:
    """One SimLane per multi.lanes entry, in config order (ties go to the
    first). On llamaserver each lane gets its own server URL and, when the lane
    names one (`multi.lanes.<lane>.model_file`, Phase 4 human decision 3: Llama
    3B on the NPU, Gemma 1B on the CPU), its own model file, recorded on every
    call; on any other backend the lanes share one backend."""
    lanes = []
    for name, lc in cfg["multi"]["lanes"].items():
        kind = lc.get("kind", "llm")
        if kind == "decider" and cfg["llm"]["backend"] == "llamaserver":
            # bev-decider: bev-decide on the board, its own server and model
            backend = make_backend({"backend": "bevdecider", "bevdecider": {
                "url": lc["url"], "lane": name,
                "model_file": lc.get("model_file", "unknown"),
                "timeout_s": cfg["llm"].get("llamaserver", {}).get("timeout_s", 60.0)}})
        elif cfg["llm"]["backend"] == "llamaserver":
            llm = dict(cfg["llm"])
            llm["llamaserver"] = {**cfg["llm"].get("llamaserver", {}),
                                  "url": lc["url"], "lane": name}
            if lc.get("model_file"):
                llm["llamaserver"]["model_file"] = lc["model_file"]
            backend = make_backend(llm)
        else:
            backend = shared_backend
        lanes.append(SimLane(name, backend, lc["prefill_tok_s"], lc["decode_tok_s"],
                             kind=kind))
    return lanes

