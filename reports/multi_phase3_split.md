# Multi-agent Phase 3: split by plant side: report

## Status
PARTIAL. Commit 0 (this plan, the decisions, predictions and pass rules) only. Branch `multi-agent-p3`, made from
`multi-agent` at `a672af7`.

**Mock only.** The mock backend re-ranks retrieved cases and does no reasoning, so its numbers measure the
deterministic and retrieval layers only; nothing here is an accuracy result. All timings are laptop timings.

## HUMAN DECISION: start Phase 3 before Phase 2 is closed (2026-10-05)
The brief says not to start Phase 3 until Phase 2's mock work and its real-model test are done. The human
overruled it. Reason: board time is the bottleneck; Phase 3 is built on the mock while the QIDK runs Phase 2, on a
separate branch so the board run stays pure Phase 2. Conditions recorded with it:
- Phase 3 is not run on the board until Phase 2's real-model numbers are in and accepted.
- Phase 3 reuses Phase 2's pieces by import (prompt sections, switches, answer format B', note-facts, the compact
  verifier), so a Phase 2 fix flows into Phase 3. Estimated rework if the board forces a Phase 2 change: 1 to 3
  hours in the likely case, about a day if the answer format itself must change.
- Open from Phase 2 and not decided: gate G1a (one count 20 against a predicted 19). It does not block this work.

## HUMAN DECISION: the six design choices
The human said "start" without choosing; by the working rule (CLAUDE.md, "choose the more conservative option"),
the option marked (a) in the plan put to the human is taken for each. The human can change any of them.
1. **Merging the two answers:** the side with the more severe facts first (tie: water first), then the other side's
   cases not already named; a case named by both appears once with both sides' citations. The combined list goes
   through the single agent's `merge`, unchanged.
2. **Steady ticks (commit 3):** while a side's evidence is unchanged, its last checked answer is re-used (the plan's
   "accepted if that side's evidence hasn't changed since"); no new call.
3. **Verifier lane:** fixed on the CPU, as decided for accuracy gates; "whichever lane frees first" only by switch.
4. **Model answers moving belief:** not in Phase 3. Belief stays exactly as in Phase 2 (answers reorder the shown
   claims through `merge`, as today). Open item: the plan's capped belief nudge, as its own change later.
5. **No side has evidence but triage is WATCH or above:** both sides are asked.
6. **Working style:** build through, phase-reviewer after each commit, stop at the end of commit 5; a short status
   (done, left, estimate) after each task.

## Sides (DESIGN, from the plan's agent table, p.5)
| side | tags | pseudo-tags | lane (`multi.fixed_placement`, already in config) |
|---|---|---|---|
| water | `drum_level`, `feed_water_flow`, `steam_flow` | `water_balance` | NPU (`diag_water`) |
| heat | `bed_temp_avg`, `drum_pressure`, `ms_temperature`, `steam_flow` (as load) | `energy_balance` | CPU (`diag_heat`) |

- A fact belongs to every side whose tag set holds one of its tags (`steam_flow` is in both, as the plan's "steam
  flow as load"). A BALANCE fact naming feed and steam flow is water; the other BALANCE facts are heat (the same
  split as `world_model._fact_ids`).
- A case belongs to the sides its MOVING (non-FLAT) signature triples touch: water only RCA-01; heat only RCA-03,
  07, 13, 14, 18; both RCA-04, 05, 11, 16; none (all-FLAT) RCA-09, 10, 15. A both-sides or no-side case is shown to
  both. `family` in the case library is not used (it is for coverage analysis only).
- A side is **active** on a tick at WATCH or above when it has a non-INFO fact or an open finding on its side.
- Retrieval and belief are NOT split: one retrieval on the full signature and one belief update, exactly as Phase 2.

## Each side's prompt (reuses the Phase 2 compact sections)
The Phase 2 all-on prompt, restricted to the side: its facts (at most 8 lines, the plan's budget, most severe
first), its cases from this tick's retrieval (at most 4), its note-facts (a note-fact goes to a side when one of its
subjects is a tag of that side; others go to both; at most 4) and the record-facts (at most 4, to both), belief top 3
as today, plus **one line about the other side**, written by code: that side's most severe fact detail, or "steady".
Answer format B', cap 60, line map per job, expanded by the gate as in Phase 2.

## Commits
| # | what | behaviour change |
|---|---|---|
| 0 | this plan | none |
| 1 | side definitions as pure functions + tests | none (nothing calls them yet) |
| 2 | two side diagnosticians (`multi.split`, default off), merge rule, verifier after the merge | by construction, switch on |
| 3 | call only on change + re-use on steady ticks (`multi.split_on_change`, default off); side-aware stale rule | by construction, switch on |
| 4 | known-wrong-answer verifier tool (forced wrong rank 1; verdicts recorded) | none (a tool) |
| 5 | mock dev run, report | — |

## Predictions and pass rules (dev, 36 episodes, mock, lockstep, fixed placement; written before any code)
| check | rule |
|---|---|
| commit 1 | Phase 2 all-on dev run: 0 differences and byte-identical prompt log against the `a672af7` run |
| switches off (commits 2, 3) | the same, against the `a672af7` all-on run |
| split on: deterministic layer untouched | `state`, `triage`, `facts`, `belief_ranking`, `belief_supports` identical to the Phase 2 all-on run on every tick (belief and retrieval are not split) |
| split on: side prompts | every side prompt holds only its side's facts and cases (checked on every dev call); prompt + 60 < 1,280 on all four tokenizers |
| split on: health | parse failures 0, out-of-range lines 0, invalid verifier answers 0 |
| split on, on change on | the same, plus: no side job on a tick where that side's evidence is unchanged and an answer is cached |
| single agent | unchanged (G4 rule of Phase 2) |
| timing | S7 0; P0 over 200 ms 0 (laptop) |
| tests | suite green; every new test mutation-checked (`PYTHONDONTWRITEBYTECODE=1`) |
| reported, not gated | model calls per tick (mean, max), diagnosis calls per side, simulated diagnosis latency mean / p95 (placeholder lane rates: an expectation, not a result), mock group top-1 overall / family B / one-side families (a retrieval-layer number) |

The plan's real check (group top-1 at least Phase 2's, separately on cross-side faults; diagnosis latency; does the
verifier disagree with a known-wrong answer) needs the board, after Phase 2's real-model numbers.

Any rule that fails: stop that item, record it, adjust nothing; continue only on work that does not depend on it.

---

# Results by commit

## Commit 1: side definitions (`fieldmind/multi/sides.py`). KEPT.
Pure functions; nothing calls them yet. Mock, dev.

| check | rule | measured | result |
|---|---|---|---|
| Phase 2 all-on dev run unchanged | 0 differences, prompt log byte-identical vs the `a672af7` run | 0 differences, summary 0; `cmp` identical | PASS |
| tests | green, mutation-checked | `tests/test_sides.py` 8 passed; full suite 284 (276 before); 13 / 13 mutations caught (one after strengthening the other-side test) | PASS |

#### Deviations from commit 0, recorded
1. **Case-side list (erratum).** Commit 0 listed RCA-14 and RCA-18 as heat-only. Under the rule written in the same
   section (a case belongs to the sides of its MOVING triples; `steam_flow` belongs to both sides) they move
   `steam_flow` and so go to both. The list had been computed by a quick script that left `steam_flow` out of the
   water side. The rule is followed: water only RCA-01; heat only RCA-03, 07, 13; both RCA-04, 05, 11, 14, 16, 18
   and the all-FLAT RCA-09, 10, 15. Nothing had been measured, so no number depends on the old list.
2. **BALANCE rule changed during the build (a bug found by a test, not a tuning choice).** Commit 0 said "a
   BALANCE fact naming feed and steam flow is water; the other BALANCE facts are heat" (the split
   `world_model._fact_ids` uses). L1 also emits "water balance SUSPENDED - untrusted tag(s): drum_level", tagged
   only with the untrusted water tags, which that rule sent to heat. The rule is now: a BALANCE fact (or finding)
   is water when ALL its tags lie in L1's water-balance tags `{feed_water_flow, steam_flow, drum_level}`
   (`l1_checks._balances`, `water_tags`), otherwise heat. **Open item for `main` (look only, not changed):**
   `world_model._fact_ids` maps the same SUSPENDED fact to `energy_balance`, so a case expecting an energy-balance
   triple can be given it as support.

3. **PATTERN rule added after the phase review (a bug, not a tuning choice).** L1's three PATTERN facts list the
   context tags their condition reads, not only the side they describe (`l1_checks._patterns`): "energy
   accumulating in bed" (bed, steam, pressure) and "water side only" (level, bed) were both put on both sides by the
   tag rule. They now take the side they name, from a table cited to `l1_checks._patterns` (heat, water; "heat
   side steady" heat); an unknown pattern falls back to its tags, and a test fails if L1 emits a pattern the table
   does not hold. The same review also led to: the fingerprint counts only the side's own checked note-facts and
   includes each open finding's severity (an escalation is a change); `primary_side` counts open findings; the
   other-side line is cut at the fact's first ':' (as `l1_symbolize.headline` does), so the long water-balance
   detail no longer overruns the plan's ~30-token line; ids order F2 before F10; a FLAT triple in the weighted
   spelling (`"tag|FLAT|-"`) is not movement.

| check (after the review fixes) | measured |
|---|---|
| tests | `tests/test_sides.py` 10 passed; full suite 286 passed |
| mutations | 23 / 23 caught (`PYTHONDONTWRITEBYTECODE=1`, `__pycache__` cleared each time) |
| Phase 2 all-on dev run | unchanged (nothing calls `sides.py`; the run above stands) |

#### Finding: on dev, cross-side ticks are rare, and a tube leak almost never moves the heat side
Non-QUIET dev ticks by active side, from the facts alone (findings are not in the run file), with the corrected rules:

| family | water only | both | heat only |
|---|---|---|---|
| A (water-side control) | 364 | 0 | 1 |
| **B (tube leak)** | **602** | **3** | 0 |
| C (coal) | 6 | 20 | 385 |
| D (primary air / CV) | 0 | 0 | 590 |
| E (fouling drift) | 0 | 0 | 1 |
| N (normal) | 0 | 0 | 10 |
| all | 972 | **23** | 987 |

**Correction of record:** a first version of this table (before the PATTERN fix) gave 291 "both" ticks, mostly in
families A and D, and this report briefly said the cross-side results would be read on those ticks. 268 of the 291
were artefacts of the PATTERN mis-siding (the "water side only" pattern made the heat side active, and "energy
accumulating" made the water side active through `steam_flow`). The phase reviewer found it; the corrected count is
23.

What this means, recorded, not resolved: the plan's case for the split ("when both sides move, as in a tube leak,
both run at the same time", p.6) has 23 dev ticks to show on (20 in family C, 3 in family B). Most ticks need one
side only, which is the plan's "common case" (one short call), so the split's main effect on these episodes is
shorter prompts per call, not parallel calls. The family-B cross-side check that PROMPTS.md asks for would rest on 3
ticks. Whether the simulated tube leak should cool the bed enough for L1 to see it, or L1's heat checks are too
coarse, is a question for the advisor. No data, threshold or check was changed.

#### Phase-reviewer findings (commit 1) and what was done
| finding | done |
|---|---|
| PATTERN facts sided by their context tags; ~268 of 291 "both" ticks were artefacts | **fixed** (deviation 3), tested, mutation-checked; table corrected above |
| the report's first cross-side statement rested on that artefact | **corrected** above |
| `all(fact_sides(f))` on dev facts cannot fail; the "tube leak moves both" test passed on a heat-ACCUMULATING fact, the opposite of a cooling bed | **replaced** by a test that every dev PATTERN tag set is in the table and that "water side only" never activates heat |
| fingerprint's `resolved` filter untested; note-fact ids not filtered by side; escalation not a change | **fixed and tested** |
| `primary_side` ignored findings; other-side line uncapped; ids ordered as text; weighted FLAT counted as moving | **fixed and tested** |
| RCA-14 / RCA-18 (fuel-cap faults where steam falls as a consequence) go to both sides only because `steam_flow` is a water tag | **recorded**: showing them to both is the inclusive reading of "steam flow as load", not a statement of the plan's intent |
| most note-facts name equipment only, so they go to both sides | **recorded**: the side filter on note-facts does little on this vocabulary |
| `world_model._fact_ids` maps the SUSPENDED water fact to `energy_balance` | already an open item for `main` (deviation 2) |
