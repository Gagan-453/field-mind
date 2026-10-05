# Multi-agent Phase 4 (demonstration subset): real time, two models: report

## Status
PARTIAL. Pre-registration only (this section is committed before any code). Branch `multi-agent-p4`, made from
`multi-agent-p3` at `7f73989`.

## HUMAN DECISIONS (2026-10-05)
1. **Speed first for the demonstration.** The human said the goal is a fast system ("we want ai go fast"), not a
   strict paper comparison. The one-change-per-step measurement of Phases 2 and 3 is not required for this build;
   lockstep runs keep reproducing every earlier result, so those comparisons stay available.
2. **The heat diagnostician runs on the NPU, not the CPU** ("it will take too long"). Both side diagnosticians are
   on the NPU lane; on a tick where both sides changed they queue there (23 of 1,982 dev ticks).
3. **Two models, overruling the plan's design rule 3 ("same model on both lanes"):** Llama 3.2 3B
   (`Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`) on the NPU lane for the two diagnosticians; Gemma 3 1B
   (`gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf`) on the CPU lane for the verifier and the text reader, which "run in
   the background in parallel on the CPU, not constrained by ticks". Consequence recorded: a lane now means a model,
   so a job cannot move between lanes without changing model; the Phase 5 placement study has to be designed around
   this.
4. **Build what Phase 4 needs for this to work**: real-time mode, in which ticks fire on the wall clock and model
   calls really run in the background on both lanes at once. Not in this build: the drift watcher, the
   shared-memory slowdown test, moving the agent onto the board.

## Design
- **Per-lane model** (`multi.lanes.<lane>.model_file`): each lane's server is started with its own file; every call
  records the lane's model file. No other code depends on the model.
- **`configs/fast.yaml`**, an overlay on `configs/base.yaml` (`run_demo.py --overlay`): every compact section on,
  split on, call only on change, fixed placement with both diagnosticians on the NPU and the verifier and text
  reader on the CPU, the two model files, verifier `conditional`.
- **Real-time mode** (`run_demo.py --mode realtime [--tick-s S]`, multi only, needs split): one worker thread per
  lane, each running one call at a time from its own queue (newer job replaces a waiting one of the same agent and
  side). The tick loop never waits for a model: each tick runs the hard path, folds whatever answers have arrived
  since the last tick, submits new jobs, and publishes its assessment. Folding rules are the existing ones:
  - side answers go through `fold_sides` with the cache (commit 3): an answer more than one tick older than the
    current tick is dropped as stale and counted (the plan's rule; the board keeps two ticks of facts); an accepted
    answer is cached and re-used while its side's evidence is unchanged; no new job for a side whose evidence is
    unchanged or whose job with the same evidence is already queued or running;
  - a verifier job is submitted when a new side answer was merged and the verifier's trigger fires; its verdict is
    applied to the tick it arrives in through `apply_verdict` (stale after one tick, counted);
  - text-reader jobs are submitted when a note arrives; checked note-facts are written when they come back (they
    reach a diagnosis prompt built after that).
- `--tick-s` sets the wall-clock tick for a run (default the agent's 30 s); a shorter tick is for tests and quick
  demonstrations and is recorded in the run file.
- Model agents own no board section, so their calls run off the main thread; the blackboard audit applies to the
  main thread only (a step taken on a worker thread is not audited, and writes nothing).

## Pass rules (written before any code)
| check | rule |
|---|---|
| lockstep unchanged | full suite green; the Phase 3 identity checks (single, Phase 2 all-on, split, on change) give 0 differences against the commit 5 runs |
| tick never waits for a model | real-time run on the mock with lanes made slow on purpose (each call sleeps longer than a tick): every tick's hard path finishes in < 200 ms and every tick starts on schedule |
| background work | the NPU and CPU lanes run calls at overlapping wall-clock times in that run |
| stale rule | answers older than one tick are dropped and counted, never merged |
| per-lane model | every call in a two-model run records its lane's model file |
| no duplicate work | never two queued or running diagnosis jobs for the same side with the same evidence |
| tests | every new rule tested and mutation-checked (`PYTHONDONTWRITEBYTECODE=1`) |

Real-time decisions are not compared with lockstep: answers arrive later by design, so the published ranking on a
tick can differ. Real timings on the laptop are not board timings; the board run measures them.
