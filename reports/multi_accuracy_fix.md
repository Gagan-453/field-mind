# Multi-agent accuracy recovery: report

## Status
STEP 0 PARTIAL, STOPPED. Pre-registration committed first (`e1269a1`). Step 0 code is done and two of its three
baselines exist (belief-alone on full dev; the replay of the four saved board runs). The third, the current
multi-agent on the quick set with the real model, is **not run: the QIDK is not attached to this machine**
(`adb devices` empty). Step 1 is also blocked on decision 1 (A or B). The pre-registration below was committed
before any measurement or code in this work. Branch `multi-agent-fix`, made from `demo`
at `e9425c0` (the branch that produced the board runs in `outputs/`). `fieldmind/agent/` and `bench/model_choice.py`
are not edited in this work.

**No accuracy claim is made in this work until the final gate (human decision 6) passes.** Mock numbers measure the
deterministic and retrieval layers only. All plant data is synthetic.

## Why this work exists
On the four board runs in `outputs/` (reporting set, Llama 3.2 3B on the NPU, Gemma 3 1B on the CPU, grammar on,
lockstep) the multi-agent's published first cause is in the true group on 0.59 / 0.12 / 0.79 / 0.03 of scored ticks
(A01 / B01 / C01 / D01), against 0.55 / 0.55 / 0.98 / 0.82 for the deterministic belief alone. Causes found: the
model's order is published above belief (the single agent's `merge`), the answer starts with a group letter that
drives the pick, the prompts' worked examples are echoed, the compact case lines lost their meaning, the true case is
often not shown, stale answers are reused, and the Gemma 1B verifier and text reader add noise.

## Answers before anything (no code)

**a. A01, B01, C01, D01 were REPORTING episodes** (`data/episodes/ep_*`, the 30-episode reporting set), not dev.
The report will record: the reporting set has been looked at for this diagnosis (outputs zips, and the earlier
Phase 4b pre-grammar runs on A01/B01); every decision in this work is made on dev only; the 30 reporting episodes
are not run in this work.

**b. Real-model single-agent results on dev: only 3 episodes, from older code.** The Phase 0b campaign
(`results/board/B/llama32-3b/round{1,2,3}.dev_{A01,B01,C02}.*`, summary in `reports/campaign_watch.md` and
`results/board/C/model_choice.json`): Llama 3.2 3B, NPU lane, single agent, answer cap 256, no grammar. Library
group top-1 0.507 (mock floor 0.501), raw citation faithfulness 0.828. Those run files predate the harness's
`belief_supports` key, so **Q3_rel cannot be computed from them**. There is **no full-dev single-agent real-model
run**. Decision 6 needs one (see "Single-agent reference" below). The reporting-set single runs in
`outputs/single_agent_llama32-3b.zip` are not usable for decisions.

**c. Board time per multi-agent dev episode.** Measured on the reporting set, lockstep, fast.yaml: wall 194 s
(A01, 70 min episode), 234 s (B01, 90 min), 84 s (C01, 90 min), 420 s (D01, 160 min): about 2.5 to 2.8 s per
episode-minute for fault episodes, plus 60 to 180 s chip cooling between episodes. Dev durations are 45 to 200 min,
so a fault dev episode is about 2 to 7 min of board time. Estimates (not measured): quick set about 45 to 60 min;
full dev about 2.5 to 3 h including cooling. E and N episodes make few or no model calls. Every number from here
on is re-measured, not assumed.

## Measurement sets (named before any run)
- **Quick set (10):** first two dev episodes per family A to D that are scored for root cause, by name order —
  `dev_A01_fcv_seize`, `dev_A02_fcv_seize_fast`, `dev_B01_tube_leak`, `dev_B02_tube_leak_fast`,
  `dev_C01_wet_coal` (held-out target RCA-06), `dev_C02_feeder_trip`, `dev_D01_high_cv_coal`,
  `dev_D03_high_cv_severe` (D02 and D04 have no root case) — plus `dev_N01_normal`, `dev_N02_normal`.
- **Full dev set:** all 36 in `data/episodes_dev`. Used only at the three STOP points.
- **Reporting set:** not run.

## Metric definitions (fixed now)
- **Published group top-1** = evaluator `group_top1` over library episodes (headline), held-out reported
  separately; per-tick share of scored ticks whose published rank-1 is in the true group.
- **Belief-alone** = the same metric on belief's own order (`rank_hypotheses`, insertion-order ties, as a
  belief-only publication would show it) = evaluator `belief_group`; `belief_group_tiefair` reported beside it.
  Belief takes no model input, so it is computed from a mock run of the same code, no board needed (verified by
  checking it equals the board run's `belief_ranking`-based value on the quick set at Step 0).
- **Answer quality in place of format failures** (grammar makes those zero): Q3_rel, order echo (share of answers
  whose ranked case lines are 1,2,3… in listed order), share of answers equal to a prompt example, `x`/`n`
  self-contradictions (until removed).

## HUMAN DECISIONS (committed in the report before any measurement)
1. Belief's order is the default; a checked model answer moves a case only by a capped amount and breaks ties among
   belief's leaders. **The plan gives no number** — see "Decision 1: STOP" below.
2. Verifier off until it passes the known-wrong-answer test (`bench/verifier_wrong_answer.py` exists).
3. Model text reader off. Diagnostician gets the relevant raw notes in a data fence, selected and capped as the
   single agent does (`NotesStore.search`, `k_notes`, the single agent's `<<< >>>` block). Note-injection tests must
   pass. Code-only note reader is a later comparison.
4. Two-model setup (Llama 3B NPU, Gemma 1B CPU) is a deliberate change to the plan for the demonstration. Accuracy
   runs use Llama 3B only.
5. Keep rule per step: keep if quick-set published group top-1 does not fall by more than 0.01 against the previous
   kept step, else revert. Every prompt + answer cap < 1,280 tokens on all four tokenizers (`bench/token_count.py`).
6. Final gate (full dev, real model): published group top-1 >= belief-alone − 0.01; and Phase 2 limits against the
   single agent's real-model result: group top-1 drop <= 0.05, Q3_rel drop <= 0.02, above the 0.501 floor.

## Decision 1: STOP — the plan has no number for the cap
Quote, `docs/multi_agent_plan.pdf` p.13 ("Blackboard and messages"): *"Model answers never write to belief
directly. The belief agent takes a checked answer as evidence and moves each case's log-odds by a capped amount.
This keeps the lesson from the old `_merge` bug: a model answer nudges belief, it never replaces it."* p.12 table:
belief is written by "Retriever and belief only"; p.14 failure table: diagnosticians' disagreement "Both go into
belief as separate evidence". No value for the cap is given anywhere in the plan. Per your instruction I do not
pick; two options:

- **Option A — persistent capped evidence (the plan's literal reading).** The retriever-and-belief agent (owner of
  `belief`) adds the gate-checked answer as evidence after the deterministic update: rank-1 case +δ, rank-2 +δ/2,
  others 0; at most one model nudge per case per tick; total per-case model contribution clamped to ±Δ over the
  episode (kept as a separate per-case counter so it can be reported and removed). δ = 0.35 = `STEP_SUPPORT`
  (CITED, `world_model.py`: the model's pick counts as one matched movement triple, no more); Δ = 1.2 = the existing
  per-tick bound in `update_hypotheses` (CITED). Published order = belief order after the nudge.
  Reasons for: it is what p.13 says, it accumulates agreement across ticks, both sides add evidence separately
  (p.14). Against: a persistent model term is the `_merge` lesson in slower form; a model that is consistently wrong
  (D01: B-group 78 of 96 answers) can move a 0.5 case past a 0.98 one over a few ticks unless Δ is small; it writes
  into a `fieldmind/agent` dataclass's log-odds from `fieldmind/multi` (allowed: the multi retriever owns `belief`,
  but it diverges from the single agent's belief).
- **Option B — per-tick tie-break only, nothing written to belief.** Published order = belief order; the model may
  reorder only cases whose log-odds are within ε of belief's leader (belief's "leaders"), and may not lift any case
  from outside that set. ε = 0.35 (`STEP_SUPPORT`: one movement triple of evidence; cases closer than that are not
  separated by the evidence belief has). Recomputed every tick, so a wrong model cannot drift belief.
  Reasons for: cannot make belief-alone worse by more than the ticks where belief's leaders are tied or near-tied
  (bounded and countable in advance); simplest to test; belief stays identical to the single agent's. Against: not
  the plan's "evidence into log-odds"; no cross-tick accumulation; the model has no effect when belief is confidently
  wrong (A01/B01 tie rates 0.15/0.49 on the reporting runs suggest that is where most room is anyway).

Either way the merge happens in a new gate/belief function in `fieldmind/multi` (the single agent's `merge` is kept
for the Phase 1 parity path). **Build stops here until you choose A or B (or give δ/Δ/ε).** Step 0 does not depend
on the choice and can proceed if you allow it.

## Single-agent reference for decision 6 (needs your decision)
Decision 6 compares against the single agent's real-model result on dev, which does not exist (b). Options: run
the single agent, Llama 3B, full dev, current code (with `belief_supports`), once before the final gate. Estimate
(from campaign call times 11.4 s mean, ~2,000 diagnosis + ~200 verifier calls on dev): about 7 to 9 h of board time.
I'll put it in the plan as the run before the final STOP and flag it; tell me if you want it scheduled differently
(e.g. overnight right after Step 0).

## Step 0 — no behaviour change (one commit + runs)
- `scripts/benchmark_multi_lockstep_all.sh`: pass `--log-prompts`; run file then holds every prompt and raw reply
  (envelopes and text-reader records), already gzip-saved. Add `--episodes-dir` and an episode-list argument. Add
  `bench/replay_multi.py` that reads a saved run and re-applies a merge rule offline (from the per-tick
  `multi.compact[].answer`, `case_ids`, `fact_ids`, `belief_ranking` incl. `log_odds`).
- Config for accuracy runs: `configs/accuracy.yaml` overlay = fast.yaml with **both lanes on Llama 3B** (decision 4;
  same GGUF on both lanes, plan rule 3). Decision taken (conservative): the Step 0 baseline already uses Llama on
  both lanes, so the verifier and text reader in Step 0 are Llama 3B, not Gemma 1B; recorded as a difference from
  the outputs runs.
- Belief-alone on the full dev set from a mock multi run with the same overlay (belief has no model input).
- Board: current multi-agent, unchanged code, quick set, Llama 3B. Chip temperature logged before/after each.
- Tests: prompts/replies present in saved runs; replay of an unchanged rule reproduces the run's published ranking
  tick for tick (0 differences) — mutation-checked.
- **STOP: show belief-alone (full dev), current multi (quick set), and the single-agent reference status.**

## Steps (one commit each, quick set on the board after each, keep rule 5)
1. **Merge rule (decision 1, A or B).** First offline replay on the four saved outputs runs (reporting set: shown
   for the diagnosis only, not used to decide) and on the Step 0 quick-set replies; then board. Report: ticks where
   the model's nudge changed rank 1, and how many of those changes were right. Prediction committed before the board
   run (from the replay); a contradiction stops the work.
2. **Remove `g`.** Answer format and grammar (`compact.py` prompt template, `grammar.diagnosis`, `expand_diag_answer`);
   code derives the group from the first ranked case's letter. Token check.
3. **Remove `x` and `n`.** Same files; `unexplained` then comes only from the gate's own rule (ALARM/CRITICAL facts
   not cited), `notes used` dropped from telemetry.
4. **Remove the worked examples** from `diag_compact.txt` (and `ver_compact.txt` is moot while the verifier is off
   until step 8). One extra quick-set run with `case_order: shuffled`: report the share of answers that are just the
   listed order (order echo).
   **STOP: full dev run; table of steps 0–4 beside belief-alone.**
5. **Case lines.** Short name per case (a few words from its title or cause) and a check that can be compared with the
   facts (proposed: the case's expected moving triples in the fact vocabulary, e.g. "expects: bed temperature rising,
   heat accumulating, steam flat"). **Show all 13 new lines and stop before running.** Stored as a reviewed table
   (`data/kb/case_short.json`), not generated at run time, so the case library itself is untouched.
6. **Case slots.** Belief's top cases (top 2) always shown; all-FLAT cases (RCA-09/10/15, group B) take at most one
   slot. Report how often the true case is missing from the prompt, before and after (mock dev count first, then
   board).
7. **Reuse.** Reuse an answer only while the side's evidence fingerprint AND belief's top case are unchanged, and
   never when older than N ticks. Propose N from the data (distribution of reused-answer ages and of ticks between
   belief rank-1 changes on dev) and **stop for your decision before measuring.**
8. **Decisions 2 and 3.** Verifier off (`agent.verifier: never` in the accuracy overlay; known-wrong-answer test run
   and reported first); model text reader off (`compact.text_reader: false`); diagnosis prompt gets raw relevant
   notes in a data fence via the single agent's selection, with record-facts kept. Note-injection tests (existing
   `test_text_reader` injection tests adapted + a new one: injected note text appears only inside the fence and the
   answer cannot cite it as a fact). Token check (raw notes cost more tokens).
   **STOP: full dev run against the final gate (decision 6); every number per episode beside the single agent and
   belief-alone.**

Per step: tests in `tests/` for the new rule, mutation checks with `PYTHONDONTWRITEBYTECODE=1` and `__pycache__`
cleared; every number that moves gets a stated cause or "unexplained"; a contradicted committed prediction stops the
work; `--arch single` on dev still equals `results/baselines/single_v3_summary.json`-era behaviour (mock, 0
differences) as a regression check.


---

# Results

## Step 0: no behaviour change
What was built (one commit):
- `scripts/benchmark_multi_lockstep_all.sh` now passes `--log-prompts` by default (`LOG_PROMPTS=0` turns it off) and
  takes `OVERLAY`, `CPU_MODEL`, `NPU_MODEL`, `EPISODES_DIR` from the environment. Every prompt and raw reply
  (diagnostician, verifier, text reader) is saved in the gzipped run file.
- `configs/accuracy.yaml`: `configs/fast.yaml` with Llama 3.2 3B on BOTH lanes (decision 4). It differs from fast.yaml
  only in the CPU lane's model.
- `bench/harness.py` writes `belief_order` (belief's live hypotheses in insertion order) per assessment, both arches,
  so a replay breaks confidence ties exactly as `rank_hypotheses` does. Nothing in `fieldmind/` reads it.
- `bench/replay_multi.py`: re-applies a merge rule to a saved run's answers offline. Rules: `current` (today's gate)
  and `belief` (belief-alone). The model's answers are not regenerated, so only rules that change what is done
  with an answer can be replayed; a prompt change needs the board.

### Baseline 1: belief-alone, full dev (36 episodes), from a mock run with the accuracy overlay
Belief takes no model input, so this is the number a belief-only publication gives with any backend.

| | library (13 episodes) | held-out (4 episodes) |
|---|---|---|
| **belief_group (belief-alone, decision 6 reference)** | **0.502** | **0.709** |
| belief_group_tiefair | 0.477 | 0.700 |
| belief_top1_tiefair | 0.375 | n/a |

Per episode (belief_group): A01 0.018, A02 0.469, A03 0.237, A05 0.000, A06 0.034, B01 0.469, B02 1.000,
B03 0.375, B05 0.695, C02 0.909, C04 0.600, D01 0.784, D03 0.939; held-out C01 0.725, C03 0.933, C05 0.367,
C06 0.811. The library value equals the Phase 1 dev value (0.502): the belief layer has not changed.

**Recorded, not acted on:** on dev, belief is almost never right on family A (A01 0.018, A05 0.0, A06 0.034), unlike
reporting A01 (0.55). Any merge rule that keeps belief's order as the default cannot fix that; only the model or a
belief fix (open item for `main`) can. Option B of decision 1 in particular can only act inside belief's near-ties.

The same mock run's published group top-1 is 0.572 library / 0.474 held-out. **That is not an agent result**: the
mock re-ranks retrieved cases by retrieval score.

### Baseline 2: the replay is faithful
| run | ticks compared | differences from what was published | of those, on a belief tie the run could not resolve |
|---|---|---|---|
| mock, full dev, accuracy overlay (has `belief_order`) | 5,850 | **0** | 0 |
| outputs A01 (board, reporting set) | 130 | 2 | 2 |
| outputs B01 | 175 | 2 | 2 |
| outputs C01 | 172 | 0 | 0 |
| outputs D01 | 310 | 1 | 1 |

The board runs predate `belief_order`; their 5 differences are all ticks where belief's top 4 holds a confidence tie,
broken by insertion order, which those files did not save. Replayed group top-1 (per tick) of the four outputs runs,
current rule against belief rule: A01 0.594 / 0.547, B01 0.125 / 0.555, C01 0.791 / 0.977, D01 0.031 / 0.816 (the
figures of the diagnosis, reproduced). These are reporting-set runs, shown for the diagnosis only, not used to decide.

### Baseline 3: current multi-agent, quick set, Llama 3.2 3B on the board — NOT RUN
The QIDK is not attached to this machine. Command for the board laptop (results to their own folder):

```
OVERLAY=configs/accuracy.yaml CPU_MODEL=Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf \
EPISODES_DIR=data/episodes_dev OUT=results/accuracy_fix/board_step0 \
scripts/benchmark_multi_lockstep_all.sh dev_A01_fcv_seize dev_A02_fcv_seize_fast dev_B01_tube_leak \
  dev_B02_tube_leak_fast dev_C01_wet_coal dev_C02_feeder_trip dev_D01_high_cv_coal dev_D03_high_cv_severe \
  dev_N01_normal dev_N02_normal
```
`bench/board.py` must list the Llama GGUF as allowed on the CPU lane (it checks the sha256; not verified here).

### Single-agent reference (decision 6): does not exist on full dev
See answer (b). Needs a full-dev single-agent board run with the current harness (estimate 7 to 9 h); not run.

### Verification
| step | result |
|---|---|
| ran the module | mock full dev with the accuracy overlay, 36 episodes, exit 0; replay on that run and on the four outputs runs |
| self-tests | `tests/test_replay_multi.py` 7 passed; full suite 416 passed |
| independent re-derivation | belief-alone two ways: evaluator `belief_group` 0.502 (library, scored window), and the Phase 1 dev report's value 0.502 from a different code version; equal. Replay of the current rule against the run's own published ranking: 0 differences over 5,850 ticks |
| mutation check | 7 mutations, 7 caught (R2 only after the test gained a backend whose verifier fails a claim) |
| regression | `--arch single`, dev, mock: 0 decision differences against the Phase 1 single run (new keys and prompt text excluded) |

| mutation (`PYTHONDONTWRITEBYTECODE=1`, `__pycache__` cleared) | caught by |
|---|---|
| replay ignores insertion order on ties | `test_replay_of_the_current_rule_reproduces_the_published_ranking` |
| replay skips the verifier | same (after adding `FailingVerifierMock`) |
| replay ignores reused answers | same |
| replay uses 0.5 instead of 0.3 for a case belief does not hold | same |
| harness `belief_order` includes retired hypotheses | `test_belief_order_is_live_hypotheses_in_insertion_order` |
| runner drops `--log-prompts` | `test_board_runner_passes_log_prompts_by_default` |
| accuracy overlay keeps Gemma on the CPU lane | `test_accuracy_overlay_runs_one_model_on_both_lanes` |

### Numbers that changed
None. Step 0 changes no behaviour; the run files gain `belief_order`.

### What I could not verify
- The board run (baseline 3) and anything about Llama 3B on the CPU lane (speed, `bench/board.py` allow-list).
- That replayed outputs runs are exact on tied ticks (5 ticks, insertion order not saved).

## Blocked / needs a decision
1. **Decision 1: option A or B** (or your own δ / Δ / ε). See "Decision 1: STOP". Step 1 waits.
2. **Baseline 3 needs the board.** Run the command above on the QIDK laptop and bring back the folder.
3. **Single-agent full-dev reference** for decision 6: when to schedule the 7 to 9 h run.
