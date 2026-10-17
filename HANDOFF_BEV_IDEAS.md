# Handoff: the bev ideas on the QIDK, branch `bev-ideas`

For Claude Code on the **QIDK laptop**, in the FieldMind repo, branch **`bev-ideas`** (from `bev-decider-3`). Everything
that can be done without the board is built, tested and committed. This file is the board part. Follow it in order.

Read first: `CLAUDE.md` (project rules, apply to every step); `reports/bev_ideas.md` (what each switch does, the
questions, the thresholds, the pass rule, the decisions taken, what is not verified); `HANDOFF_BEV_DECIDER_3.md`
(how bev-decide is built, pushed, started and proven correct: **Part C**).

## 0. What this branch adds

Every use of bev-decider-0.4B is a switch, `multi.bev.<idea>: off | shadow | on`, all `off` in `configs/base.yaml`:

| switch | what bev does | on | shadow |
|---|---|---|---|
| `explain` | picks each ranked case's supporting fact, the separating case, the notes used | Llama answers the ranking only (shorter answer); bev's picks are checked by the gate | Llama answers as usual; bev's picks logged with agreement |
| `first` | on a weak / tied tick, chooses among the side prompt's cases first | above `first_threshold`, bev's ranking replaces that side's Llama call | logged with agreement to Llama's top case |
| `actions` | yes/no per approved action that is not protected | drops a "no" (never urgency NOW, ESCALATION, MITIGATION) | logged |
| `unknown` | "none of these causes" among the top 3 | display flag `bev_flags.unknown_fault` in the tick record | logged |
| `verifier` | yes/no per shown claim + strongest contradiction | replaces the Gemma verifier call | Gemma runs; agreement logged |
| `notes` | per raw note: instructs the reader? which side? | routes the note (instructing / "none" notes kept out of prompts) | logged |
| `text_reader` | kind + subject + state of a note (note_source text only) | replaces the Gemma text reader | logged |
| `rt_fallback` | real time only: bev's ranking until Llama's answer arrives | used while Llama is pending, above `first_threshold` | logged |
| `clear_skip` | (code only, no bev) clear tick and the side's last top = belief's leader | no Llama call for that side | would-skips logged |

**With every switch off this branch publishes exactly what `bev-decider-3` publishes** (10 mock dev runs, 1,720 ticks,
v3 and bev3 configs, checked after every commit). Turn switches on per run with `--bev`, e.g.
`--bev "explain=on,actions=shadow"` and, for `first` / `rt_fallback` on, `first_threshold=<value>`.

Config for every bev run: `--overlay configs/bev_ideas.yaml` = `configs/v3.yaml` + the bev lane (port 8082) + its
placement key, every switch off, the decider off (test-enforced).

Every benchmark run now also writes, per episode:
- per-stage time per tick in the run file (`multi.stage_ms`, LAPTOP times: agent code runs on the laptop);
- `<stem>.resources.json` from an on-board sampler: CPU seconds and peak RSS per server process (NPU llama-server,
  CPU llama-server, bev-decide), board CPU load, cluster clocks, temperatures, supply power if the board exposes it,
  and the sampler's own cost.

`python -m bench.bev_report` turns two or more test folders into `COMPARE_<A>.md` / `.html`.

## 1. Prerequisite: bev-decide on the board (Part C)

Nothing here is meaningful until bev-decide runs on the board and matches its reference. Do steps 1 to 5 of
`HANDOFF_BEV_DECIDER_3.md` (build, push with sha256 checks, conformance, placement). If that is already done on this
board, just start it and check it:
```bash
unset PYTHONPATH
git switch bev-ideas && git pull --ff-only   # if the branch was pushed; otherwise copy the repo
.venv/bin/python -m pytest -q tests/test_bev_ideas.py tests/test_bev_report.py tests/test_board_sampler.py
.venv/bin/python -m bench.board start bev bev-decider-0.4B-backbone-Q8_0.gguf
curl -s http://localhost:8082/health                     # {"status":"ok"}
```
The runner refuses a config with a bev lane while bev-decide is down.

## 2. Probe what the board exposes (first, before any claim about CPU / NPU / power)
```bash
.venv/bin/python -m bench.board_sampler probe | tee results/board_probe_$(date +%Y%m%d).json
```
Report the output as it is: `clk_tck` (expect 100), which `power_supply` entries have readable current and voltage
(if none: supply energy stays `null`, which is correct), `devfreq` names (an NPU / cDSP counter would show here; the
report does not use one), thermal zone types, and the pids of the running servers. Do not change the sampler to
"find" a counter; report what is there.

## 3. Shadow run on the dev quick set (about 1 hour)

All ideas asked, nothing used: measures bev on our questions at zero risk to the published result.
```bash
Q=(dev_A01_fcv_seize dev_A02_fcv_seize_fast dev_B01_tube_leak dev_B02_tube_leak_fast dev_C01_wet_coal
   dev_C02_feeder_trip dev_D01_high_cv_coal dev_D03_high_cv_severe dev_N01_normal dev_N02_normal)
scripts/benchmark.sh bevideas_shadow "${Q[@]}" --overlay configs/bev_ideas.yaml \
  --bev "explain=shadow,first=shadow,actions=shadow,unknown=shadow,verifier=shadow,notes=shadow,clear_skip=shadow"
.venv/bin/python -m bench.bev_calibrate bevideas_shadow
```
Check in every episode's run that no bev call failed: the report's "bev ideas" table, column `failed`, must be 0. A
failed call means bev-decide was down or timed out; fix it and rerun that episode before going on.

`bev_calibrate` prints, per candidate `first_threshold`, how often bev would stand in and how often it agrees with
Llama and with the true group. **It does not choose.** Ask the human (Shubham) to choose `first_threshold` from the
table and write the choice and the table into `reports/bev_ideas.md` ("Decisions taken"). Dev episodes only.

Also give the human the sign-off item: every question sentence except `q_root` is PROPOSED
(`configs/base.yaml`, `multi.bev.questions`). They must be signed off before an `on` result is reported.

## 4. The arms (dev quick set; several hours)

Baseline A = every switch off. One idea per B arm, so each change has one cause. Order A1, B arms, A2.
```bash
scripts/benchmark.sh bevideas_A1         "${Q[@]}" --overlay configs/bev_ideas.yaml
scripts/benchmark.sh bevideas_B_explain  "${Q[@]}" --overlay configs/bev_ideas.yaml --bev "explain=on"
scripts/benchmark.sh bevideas_B_first    "${Q[@]}" --overlay configs/bev_ideas.yaml --bev "first=on,first_threshold=<chosen>"
scripts/benchmark.sh bevideas_B_actions  "${Q[@]}" --overlay configs/bev_ideas.yaml --bev "actions=on"
scripts/benchmark.sh bevideas_B_unknown  "${Q[@]}" --overlay configs/bev_ideas.yaml --bev "unknown=on"
scripts/benchmark.sh bevideas_B_verifier "${Q[@]}" --overlay configs/bev_ideas.yaml --bev "verifier=on"
scripts/benchmark.sh bevideas_B_notes    "${Q[@]}" --overlay configs/bev_ideas.yaml --bev "notes=on"
scripts/benchmark.sh bevideas_B_skip     "${Q[@]}" --overlay configs/bev_ideas.yaml --bev "clear_skip=on"
scripts/benchmark.sh bevideas_A2         "${Q[@]}" --overlay configs/bev_ideas.yaml
```
`text_reader` needs the text reader on (`note_source: text`), which v3 is not; it is not in these arms (ask the
human before adding an arm for it). `rt_fallback` is real time only (merge rule `model`), not part of this
measurement.

## 5. The report
```bash
.venv/bin/python -m bench.bev_report bevideas_A1 bevideas_B_explain bevideas_B_first bevideas_B_actions \
  bevideas_B_unknown bevideas_B_verifier bevideas_B_notes bevideas_B_skip --a2 bevideas_A2
```
It writes `results/benchmarks/bevideas_B_skip/COMPARE_bevideas_A1.md` and `.html`: accuracy, per-stage ms (laptop),
calls / read / decode tokens / call time per agent and lane, lane busy share, board CPU s / cores busy / peak RSS per
server process, board load, temperatures, supply energy (or `–`), and what each idea did.

Pass rule per idea (`reports/bev_ideas.md`, fixed before any board run): a decode-saving idea (explain, first,
verifier) is kept only if decode tokens per tick fall AND library group top-1 is not below min(A1, A2) − |A1 − A2|; a
quality idea (actions, unknown, notes) only if its own metric improves by more than |A1 − A2| and group top-1 does
not drop as above. An arm with any failed bev call is invalid.

## 6. Hand back

Append "Board results (<date>)" to `reports/bev_ideas.md` in the project report format, with: the probe output; the
shadow table and the human's threshold choice; the COMPARE tables; the pass rule worked out per idea with the actual
numbers; chip temperatures and wall times; anything that failed or looked wrong, stated plainly. Commit, do not push.
