"""
=============================================================================
 SCHEDULER  --  priorities, one queued job per (agent, side), lane choice
 (docs/multi_agent_plan.pdf, "Scheduler", "Priorities and deadlines")
=============================================================================

  P0  hard path (code agents)        200 ms   never queued -- not a Job
  P1  urgent diagnosis                10 s    front of the queue
  P2  diagnosis on changed evidence   30 s
  P3  verifier; text reader           60 s
  P4  operator query                  none    idle lanes only, dropped first

Queue order is (priority, submit order). At most one WAITING job per
(agent, side): a newer one replaces the older waiting one, which is marked
`replaced` and logged.

Lane choice: earliest predicted finish over the lanes (SimLane.predict_finish),
ties to the first lane in config order (NPU). Prediction uses the job's
max_answer_tokens, not the eventual answer length.

PHASE 1 (plumbing only): lockstep. `run_lockstep` drains the queue, running
each job to completion before the next; the harness then moves to the next
tick. Not built yet, on purpose (they would change behaviour or need real
time): P1's "verifier skipped" and "shortest prompt" rules, rate adaptation
from measured timings, the degradation ladder, and real-time mode (Session 6).
=============================================================================
"""

from __future__ import annotations

import heapq

from ..agent.l4_diagnose import est_tokens
from .jobs import Job, Result


class Scheduler:
    def __init__(self, lanes: list, cfg: dict):
        if not lanes:
            raise ValueError("scheduler needs at least one lane")
        self.lanes = lanes
        self.cfg = cfg
        self.mode = cfg.get("mode", "lockstep")
        if self.mode != "lockstep":
            raise NotImplementedError("real-time mode is Session 6")
        if cfg.get("adapt_rates"):
            raise NotImplementedError("rate adaptation from measured timings "
                                      "is not built in Phase 1")
        dl = cfg.get("deadlines_s", {})
        self.deadlines = {int(k[1:]): v for k, v in dl.items()}
        self._heap: list = []
        self._seq = 0
        self._waiting: dict[tuple, Job] = {}
        self.current: Job | None = None
        self.replaced: list[Job] = []
        self.dispatched: list[Job] = []

    # ------------------------------------------------------------------
    def new_job(self, agent: str, evidence_tick: int, priority: int,
                max_answer_tokens: int, submit_s: float, work=None,
                side: str = "all") -> Job:
        if not 1 <= priority <= 4:
            raise ValueError("model jobs are P1..P4; P0 is the hard path")
        self._seq += 1
        return Job(job_id=f"j-{self._seq:04d}", agent=agent,
                   evidence_tick=evidence_tick, priority=priority,
                   deadline_s=self.deadlines.get(priority),
                   max_answer_tokens=max_answer_tokens, submit_s=submit_s,
                   side=side, work=work)

    def submit(self, job: Job) -> None:
        key = (job.agent, job.side)
        old = self._waiting.get(key)
        if old is not None:
            old.replaced = True                 # newer evidence wins
            self.replaced.append(old)
        self._waiting[key] = job
        heapq.heappush(self._heap, (job.priority, self._seq_of(job), job.job_id, job))

    @staticmethod
    def _seq_of(job: Job) -> int:
        return int(job.job_id.split("-")[1])

    def next_job(self) -> Job | None:
        while self._heap:
            _, _, _, job = heapq.heappop(self._heap)
            if job.replaced:
                continue
            if self._waiting.get((job.agent, job.side)) is job:
                del self._waiting[(job.agent, job.side)]
            return job
        return None

    def pending(self) -> int:
        return sum(1 for *_, j in self._heap if not j.replaced)

    # ------------------------------------------------------------------
    def choose_lane(self, job: Job, prompt_tokens: int):
        """Earliest predicted finish; ties to the earlier lane in config order."""
        best, best_t = None, None
        for lane in self.lanes:
            t = lane.predict_finish(job.submit_s, prompt_tokens,
                                    job.max_answer_tokens)
            if best_t is None or t < best_t:
                best, best_t = lane, t
        job.prompt_tokens = prompt_tokens
        job.predicted_finish_s = round(best_t, 6)
        job.lane = best.name
        return best

    def lane_for_current(self, prompt: str):
        """Called by LaneBackend on every model call. The first call of a job
        picks its lane (the prompt exists only now) and starts it there."""
        job = self.current
        if job is None:
            raise RuntimeError("model call outside a scheduled job")
        if job.lane is None:
            lane = self.choose_lane(job, est_tokens(prompt))
            lane.begin(job)
            return lane
        return self._lane(job.lane)

    def _lane(self, name: str):
        return next(l for l in self.lanes if l.name == name)

    # ------------------------------------------------------------------
    def run_lockstep(self, tick_epoch_s: float) -> list[Result]:
        """Drain the queue in priority order; each job runs to completion."""
        out = []
        while (job := self.next_job()) is not None:
            self.current = job
            try:
                env = job.work()
            finally:
                self.current = None
                if job.lane is not None:        # the job made a model call;
                    self._lane(job.lane).end(job)   # free the lane even if it raised
            self.dispatched.append(job)
            wait_ms = ((job.start_s - job.submit_s) * 1000
                       if job.start_s is not None else 0.0)
            out.append(Result(job=job, envelope=env,
                              evidence_tick=job.evidence_tick, lane=job.lane,
                              queue_wait_ms=wait_ms, start_s=job.start_s,
                              finish_s=job.finish_s, tick_epoch_s=tick_epoch_s))
        return out
