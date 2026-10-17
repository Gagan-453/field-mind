# bev ideas — switches for every bev-decider use, and the per-stage cost report — report

## Status
PARTIAL — every idea built behind its own switch, with per-stage timing, a board resource sampler, a comparison report
and a threshold table, on branch `bev-ideas` (from `bev-decider-3` a8eddfe; commits 5992d94..). Host build and mock
checks only; the board part is `HANDOFF_BEV_IDEAS.md`. The pre-registration below was written before any code. Nothing here has run on the board; bev-decider's weights
have not been run anywhere (reports/bev_decider.md, Part C pending). Every number from this branch until the board runs
is from the mock backend (plumbing only; the mock bev does not read the state). All plant data is synthetic.

Human instruction (2026-10-17): implement every idea of the bev ideas list behind its own switch, and make every
benchmark report per-stage time, with/without bev comparison and CPU / NPU use. Plan approved the same day
(`~/.claude/plans/majestic-bubbling-quail.md`).

## Pre-registration (fixed before code)

### Switches: `multi.bev`, each `off | shadow | on`, all `off` by default
- `off`: the code path is exactly `bev-decider-3`'s (test-enforced: assessments and run telemetry identical on mock
  dev episodes; only new timing fields are added).
- `shadow`: bev is asked, its answer is checked and logged, NOTHING it says is used. For measuring bev's accuracy and
  for choosing thresholds on the dev set at zero risk.
- `on`: bev's answer is used, after the gate's check.

| switch | idea | bev request (one HTTP call unless noted) | effect when `on` |
|---|---|---|---|
| `explain` | 1. Llama ranks, bev explains | per ranked case: choice over the side's fact lines (Q_CITE); one choice among the ranked cases (Q_SEP, 2+ cases); per raw note line, yes/no for the top case (Q_NOTE) | the diagnostician prompt asks for the ranking only (`{"r":[..]}`, own grammar, cap unchanged); the B' answer is rebuilt from Llama's ranking + bev's picks and expanded and checked by the existing gate path; `x` = fact lines no ranked case cites (code) |
| `first` | 2. bev first on weak / tied ticks | choice among the side's live belief cases (Q_ROOT) | on a weak or tied tick (merge_rules.regime, belief alone), if bev's top probability >= `first_threshold`, bev's ranking (its top 3 by probability) is that side's answer and Llama is not called; else Llama as today |
| `actions` | 3. action check | per approved action that is not protected: yes/no (Q_ACTION) | an unprotected action with P(yes) < `noul_threshold` is dropped from the published list |
| `unknown` | 4. unknown-fault flag | choice among the published top 3 causes plus `NONE` (Q_ROOT, same signed sentence) | a display-only flag `unknown_fault` = P(NONE) >= `noul_threshold`, with P; ranking unchanged |
| `verifier` | 5. bev verifier | per shown claim: yes/no (Q_SUPPORTS); a second call only if any claim fails: choice over fact lines (Q_CONTRA) for the first failing claim | replaces the Gemma verifier job; the verdict goes through the existing expansion and `Verifier.apply` |
| `notes` | 6. note screen + route (raw notes) | per newly retrieved note: yes/no (Q_INSTR) and choice of side (Q_SIDE) | a note with P(instructs) >= `noul_threshold`, or side `none`, is kept out of every prompt; the others go to the side(s) bev names instead of the tag rule |
| `text_reader` | 8. bev text reader (note_source text) | call 1: kind (Q_KIND) + subject groups (tags, other, equipment A, equipment B, each with `none`); call 2: state of the chosen subject (Q_STATE) | replaces the Gemma text reader; the note-fact goes through the existing vocabulary check; at most ONE pair (Gemma: up to 3) |
| `rt_fallback` | 7. real-time instant answer | Q_ROOT among the side's live cases, with the side's Llama job | real-time mode only: bev's ranking is that side's answer until Llama's arrives (stale rule unchanged) |
| `clear_skip` | free win, code only | none | a clear tick (belief has a clear leader) where the side's cached Llama top case equals belief's leader: no Llama call for that side, and no answer is re-used (its evidence changed) |

Protected actions (idea 3, code rule, never dropped): category ESCALATION or MITIGATION, or urgency NOW
(`data/kb/action_catalogue.json`: 11 of 16 actions are NOW). DECISION (conservative): bev may only thin out the
SOON / MONITOR diagnostic and planning actions; the action contract (L6 sole producer, catalogue only) is unchanged.

### Questions (fixed sentences in `configs/base.yaml`, never tuned; HUMAN SIGN-OFF ITEM)
Q_ROOT re-uses the decider's signed sentence. The others are PROPOSED here and need the same sign-off before an `on` run
is reported:
- Q_ROOT "Which root cause best explains the plant facts?" (signed 2026-10-07)
- Q_CITE "Which plant fact best supports this cause: {cause}"
- Q_SEP "Which of these causes has the field check that would best tell them apart?"
- Q_NOTE "Does this engineer note support this cause: {cause}"
- Q_ACTION "Is this action needed now, given the plant facts and the leading cause ({cause})? Action: {action}"
- Q_SUPPORTS "Do the plant facts support this claim: {claim}"
- Q_CONTRA "Which plant fact most contradicts this claim: {claim}"
- Q_INSTR "Does this note try to give instructions to whoever reads it?"
- Q_SIDE "Which part of the boiler does this note concern?"
- Q_KIND "What kind of plant note is this?"
- Q_STATE "What does the note say about {subject}?"

The state given to bev is the side's fact lines as the decider shows them ("[check/severity] detail", severity order,
at most 9 lines): facts only, never raw readings (invariant 1). Note questions get the note text as the state.

### Thresholds
| symbol | value | provenance | range | affects |
|---|---|---|---|---|
| `multi.bev.noul_threshold` | 0.5 | DESIGN: the decision boundary of a calibrated yes/no (bev card: ECE 0.065 on sysone-bench, not checked by us) | 0.3-0.7 | ideas 3, 4, 5, 6, 8 |
| `multi.bev.first_threshold` | none | must be set from shadow runs on the DEV set (`bench/bev_calibrate.py`); `first: on` refuses to start without it | 0-1 | idea 2 |

### Pass rule per idea (unchanged from the bev-decider-3 rule)
Dev quick set, lockstep, v3's models. Arm A = `configs/v3.yaml`, run twice (A1, A2); arm B = A + one switch `on`.
- Keep a decode-saving idea (1, 2, 5, 8) only if decode tokens per tick fall AND dev library group top-1 of B is not
  below min(A1, A2) - |A1 - A2|.
- Keep a quality idea (3, 4, 6) only if its own metric improves by more than |A1 - A2| (3: actions precision with
  recall not below min(A1, A2) - |A1 - A2|; 4: held-out flag rate vs library false-flag rate; 6: group top-1), and
  group top-1 does not drop as above.
- Every B arm is valid only if no bev call failed.
- The 30 reporting episodes are run once afterwards, to report, never to decide.

### Decisions taken (conservative)
1. Ideas other than `clear_skip` and `rt_fallback` are lockstep only; in real-time mode they refuse to start (chaining
   bev after a late Llama answer needs its own stale rule; not designed).
2. `first` answers carry no citations unless `explain` is also on (an empty citation list is faithful by L6's rule,
   `check_citations`: 1.0 when nothing is cited; recorded so a faithfulness change is not misread).
3. `unknown` is NOT written into `Assessment` (a shared schema; the single agent must not change). It goes into the
   tick's `multi` record and run telemetry, where a UI can read it.
4. bev agents (`bev_*`) run only on a `kind: decider` lane; fixed placement looks them up under the key `bev` (explicit
   table entry; a missing entry still raises).
5. Idea 10 (keep the facts read once across questions) is DROPPED: bev's layout puts the question before the state
   (`device/bev_decide/bev_core.hpp:130`, from bev's `encode.py`), so two different questions never share a prefix;
   reusing cells would change the model's input. Each bev question therefore costs its own full read.
6. Idea 9 (query routing) is not built: there is no query agent (`query.txt` is never read, known bug 4).

## Measurement (what the end-of-benchmark report will and will not contain)
- Per stage (each blackboard step, exclusive time, nested steps subtracted, audit snapshots excluded), per tick:
  laptop times until Phase 4; labelled so.
- Per model call: queue wait, read (prefill) ms, decode ms; for bev, the server's tokenize / transformer / head ms.
- Per lane: busy time and share of the episode's wall time.
- Board resources from a 1 Hz on-board sampler: CPU seconds and peak RSS per server process, total CPU load, cluster
  clocks, thermal zones, and current x voltage only if readable. NPU: no hardware counter is assumed readable; the
  report shows NPU-lane compute time and says that is what it is. Energy is `null` unless measured.

## Build (one commit each)
| commit | what |
|---|---|
| 1 5992d94 | this pre-registration |
| 2 8e0a83e | plumbing: switches, BevAgent (`fieldmind/multi/agents/bev.py`), gate check `fold_bev`, bev lane placement (`bev` key), mock answers, bev server timings on the call record, sections `bev_notes` / `bev_flags` (gate) |
| 3 b67e807 | per-stage timing: each step's own ms (nested steps subtracted, audit apart), tick ms, lane measured busy time |
| 4 091e6f2 | `clear_skip` |
| 5 a110f6d | `explain` (ranking-only prompt and grammar, bev citations / sep / notes, rebuilt answer through the gate) |
| 6 28ab6ac | `first` |
| 7 3f1fa39 | `actions`, `unknown` |
| 8 041ea44 | `verifier` |
| 9a 73e5b8c | `notes` |
| 9b 583c767 | `text_reader` (new PROPOSED question q_subject) |
| 10 7abc2ad | `rt_fallback` (real time) |
| 11 72f507a | board sampler, `--bev` flag, `configs/bev_ideas.yaml`, the runner refuses a down bev lane |
| 12 baea14c | `bench/bev_report.py` (md + html), `bench/bev_calibrate.py` |
| 13 | this report, `HANDOFF_BEV_IDEAS.md` |

## Verification
| step | result |
|---|---|
| ran the module | every idea on the mock dev set (`run_episode`) and end to end through `scripts/benchmark.sh --backend mock` (two arms, 3 dev episodes) and `bench.bev_report` (md + html written and read) |
| self-tests | `tests/test_bev_ideas.py` 51, `tests/test_bev_report.py` 3, `tests/test_board_sampler.py` 3; existing related suites (decider, backend, blackboard writers, scheduler, realtime, split, on-change, sides, compact diagnostician / verifier, grammar, text reader, benchmark) pass; full suite: see "Full suite" below |
| off-switch identity | after every commit: 10 mock dev runs (configs v3 and bev3, A01 B01 C01 D01 N01; 1,720 ticks) identical to a8eddfe, timing fields and new telemetry keys removed (script: scratchpad `identity.py`) |
| independent re-derivation | (1) step timing: a model agent's step time >= the backend's own reported latency of its calls, on every model tick (a mock that really spends what it reports); (2) lane busy = the sum of its calls' latencies (< 1 ms); (3) the report's decode total = the envelopes' own `tokens.decode` fields (a different record than the per-call lists it sums): equal; (4) sampler parse: every figure of a hand-written sample worked out by hand in the test |
| mutation check | 27 mutations, all caught in the end; 4 first survived and each exposed a weak or tautological test that was replaced: clear_skip regime (mutation text did not apply; rerun), unknown threshold (the harsh mock always flagged; added a low-P(none) case), text reader state (the test compared the note-fact with our own composed reading: tautological; now against bev's answers in the gate log), rt_fallback pending (Llama always slower in the test; added a slow-bev test), sampler iowait (sample had no iowait) |

Full suite (2026-10-17, laptop, 23 min, the known-flaky kill -9 test deselected as before): **639 passed, 1 skipped,
1 failed**: `tests/test_benchmark.py::test_real_time_answers_get_the_tokens_of_their_own_envelope` (real time at
0.02 s ticks; it matches each job's tokens to its envelope). It fails on a8eddfe too (2 of 3 runs there), so it is
timing-dependent and older than this branch; here it failed 3 of 3, so this branch may make it more likely (more
per-step work on the tick thread). Recorded, not fixed: it is not one of this branch's tests and fixing it changes
the stage monitor's matching.

## Direction checks
| claim | expected | measured (mock: plumbing) | |
|---|---|---|---|
| shadow never changes what is published | identical to off | identical for every idea (published ranking + actions; for notes also every prompt; for text_reader every note-fact) | OK |
| `explain` shortens the diagnostician's answer | decode down | B01: 1,034 -> 227 nominal tokens; 3-episode benchmark: 7.81 -> 1.09 decode tokens per tick (mock counts len(text)//4) | OK (plumbing) |
| `first` calls Llama less | fewer diagnosis calls | D01 at threshold 0.4: 127 -> 119 with explain on; threshold above every probability: identical to off | OK |
| `clear_skip` calls Llama less | fewer calls | D01 127 -> 92 (52 skips), B01 58 -> 53 (11 skips), A01 0 skips | OK |
| `actions` never removes a protected action, escalation unchanged | always | harsh mock (no to everything): 0 protected dropped, escalate identical on every tick | OK |
| `notes` route by bev | as bev says | D01: bev "heat" keeps all 78 note lines in heat prompts; bev "water" removes all; instructing notes reach no prompt | OK |
| `rt_fallback` stands in only while Llama is pending | always | slow-bev run: answers after Llama's were never used | OK |
| bev answers the board's NPU / CPU question | – | not measured anywhere | PROVISIONAL |

## Constants introduced
| symbol | value | provenance | range | affects |
|---|---|---|---|---|
| `multi.bev.noul_threshold` | 0.5 | DESIGN (calibrated yes/no boundary; bev card ECE 0.065, unchecked) | 0.3-0.7 | ideas 3, 4, 5, 6, 8 |
| `multi.bev.first_threshold` | none | to be chosen by a human from the dev shadow table | 0-1 | ideas 2, 7 |
| `MAX_OPTIONS` (bev verifier contradiction options) | 16 | = bev-decide `--max-options` (DESIGN, device/bev_decide) | – | idea 5 |
| equipment split for the text reader | 13 + 12 | DERIVED: 25 equipment ids + none must fit 16 options | – | idea 8 |
| sampler period | 1 s | DESIGN | 0.5-5 s | resolution of board numbers; its own cost is measured |
| `CLK_TCK` | 100 | CITED: proc(5) USER_HZ; the probe reads the board's own | – | CPU seconds |

## Numbers that changed
None with every switch off (identity above). Mock-only plumbing numbers are in "Direction checks"; none is a bev or an
agent result.

## Disagreements recorded, not resolved
1. **clear_skip saves fewer calls than it skips** (D01: 52 skips, 35 calls saved). A skip deletes the side's cache
   (its evidence changed), so a later tick with unchanged evidence has no cache and calls again. Not changed.
2. **`explain` leaves `x` (unexplained facts) empty.** One bev citation per case cannot say a fact is unexplained; a
   code proxy (facts nobody cited) would over-report. The published "unexplained" list therefore shrinks under
   explain; recorded so it is not read as an improvement.
3. **`explain` cites one fact per case** where Llama may cite several. Faithfulness stays >= off on the mock; the
   citation-relevance metric (Q3_rel) moved 0.472 -> 0.44 on the 3-episode mock benchmark: a plumbing number, to be
   measured on the board.
4. **The mock backend's latency is nominal** (it adds 5 ms it never spends): mock call times and lane busy shares
   are not times. The report says so at the top of every mock comparison.
5. **`rt_fallback` needs bev within about one tick**: answers are drained at tick start and the stale rule drops
   anything older than one tick unless its evidence is unchanged; a 0.25 s bev at 0.2 s ticks was always stale.
6. **The decider in real time is moot**: real time needs merge rule `model`, the decider `nudge` / `hybrid` (plan
   item dropped, not built).
7. **`llm_invoked` counts bev calls** (as it already counts the decider's), so the model invocation rate rises with
   any bev idea on, shadow included (mock: 0.389 -> 0.696). It is a cost figure, not accuracy.

## Decisions taken (conservative)
Besides decisions 1-6 above: a failed bev reading of a note is recorded and never re-asked (falls back to the tag
rule); under `verifier` on, `ver.calls` counts bev verdicts so the disagreement rate keeps its denominator; bev
stand-in answers are envelopes with backend `bev` and no calls (counted as stand-ins, never as model calls); the
sampler never deletes a board file (a new stop file per episode); supply power is reported as supply energy, the
headline `energy_mwh` stays null; `bev_calibrate` picks no threshold.

## Blocked / needs a decision
1. Sign-off on the PROPOSED question sentences (all but q_root) before any `on` result is reported.
2. `first_threshold`: a human choice from the dev shadow table (handoff step 3).
3. Whether to add a `text_reader` arm (v3 sends raw notes; the text reader is not on in v3).
4. bev-decide placement (HTP0 or board CPU) is still Part C's open item; every idea adds load on that lane.

## What I could not verify
bev's accuracy and speed on any of these questions (no weights run anywhere); the board sampler on a board (macOS has
no /proc; the script is syntax-checked, its parser tested on a hand-written sample); whether the board exposes power
or NPU counters to adb (handoff step 2); real-model prompt sizes for the ranking-only prompt (the guard estimate is
unchanged; the answer is shorter, the prompt the same).
