# bev ideas — switches for every bev-decider use, and the per-stage cost report — report

## Status
PARTIAL — pre-registration (written before any code on branch `bev-ideas`, from `bev-decider-3` a8eddfe). Sections
below "Pre-registration" are filled in as the commits land. Nothing here has run on the board; bev-decider's weights
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

## Verification
(filled per commit)

## Direction checks
(filled per commit)

## Constants introduced
See Thresholds above. Others: none yet.

## Numbers that changed
(filled per commit)

## Disagreements recorded, not resolved
(filled per commit)

## Blocked / needs a decision
1. Sign-off on the PROPOSED question sentences (all but Q_ROOT) before any `on` result is reported.
2. `first_threshold` needs a dev shadow run on the board.

## What I could not verify
bev's accuracy and speed on any of these questions (no weights run anywhere); whether the board exposes power or NPU
counters to adb (probed by the handoff's first step).
