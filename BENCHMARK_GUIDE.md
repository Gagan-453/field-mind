# FieldMind benchmark command: guide

`scripts/benchmark.sh` runs one or more episodes on the QIDK board, shows the live stage monitor in the same
terminal, and saves every result under `results/benchmarks/<test name>/`. It runs three architectures:

| `--arch` | what runs | board servers |
|---|---|---|
| `multi` (default) | the multi-agent system | NPU lane :8080, CPU lane :8081 |
| `single` | the single agent (the baseline) | NPU lane :8080 |
| `bev` | the multi-agent system **plus the bev-decider System One model** (a decision model that returns a probability per candidate cause, no generated text) | NPU lane :8080, CPU lane :8081, **bev-decide :8082** (on the NPU by default) |

---

## 1. Before you start

- Run from the repo root (`~/fieldmind`) in a normal terminal window, in **bash**. tmux is fine and protects the run if
  the window closes.
- Exactly one board on adb: `adb devices`.
- Nothing else on the board. The command refuses to start if another board run is going (the campaign,
  `bench/board_session.sh`, `benchmark_multi_lockstep_all.sh`, or another benchmark).
- If the VPN blocks the board or GitHub, that is a network problem, not this command.
- You do **not** need to start the model servers yourself. The command starts them before every episode and stops
  them afterwards. With `--arch bev` it also starts `bev-decide` if it is not already running.
- `--arch bev` only: the bev-decider files must be on the board and their sha256 recorded in `bench/board.py`
  (`BEV_FILES`, `BEV_BINARY_SHA256`). That was done once when bev-decider was built and pushed (8 October 2026).
  It needs a branch that has the decider: `bev-decider-3` (v3 + decider) or `bev-decider-2`.

---

## 2. The command

```
scripts/benchmark.sh <test name> <episode> [<episode> ...] [options]
```

The test name is the results folder name. Use letters, digits, `.`, `_` and `-` only.

| episode prefix | where it comes from |
|---|---|
| `ep_*` | the reporting episodes (`data/episodes`) |
| `dev_*` | the dev episodes (`data/episodes_dev`) |

Example, the six presentation episodes:

```
scripts/benchmark.sh six_episodes ep_N01_normal ep_A01_fcv_seize ep_B01_tube_leak \
    ep_C01_wet_coal ep_D01_high_cv_coal ep_E01_fouling_drift
```

Every option is listed by `scripts/benchmark.sh --help`.

---

## 3. Options

| option | meaning |
|---|---|
| `--arch multi\|single\|bev` | `multi` (default): the multi-agent system. `single`: the single agent, for comparison. `bev`: multi-agent plus the bev-decider (see section 6). |
| `--overlay FILE` | Config overlay. Defaults: `configs/fast.yaml` for multi (Llama 3.2 3B on the NPU, Gemma 3 1B on the CPU, answer grammars on); `configs/bev3.yaml` for bev (v3 plus the decider); no overlay for single. Others: `configs/v3.yaml` (v3: hybrid merge rule, no group letters, raw notes), `configs/accuracy.yaml` (Llama 3B on both lanes), `configs/bev.yaml` (bev-decider-2: accuracy.yaml + nudge + the decider). An overlay that turns the decider on needs `--arch bev`, and `--arch bev` needs one that does. |
| `--bev "idea=mode,..."` | **bev ideas** (branch `bev-ideas`, with `--overlay configs/bev_ideas.yaml`): turn bev-decider uses on per run, each `off`, `shadow` (asked, only logged) or `on`. Ideas: `explain`, `first` (needs `first_threshold=<n>` when on), `actions`, `unknown`, `verifier`, `notes`, `text_reader`, `rt_fallback`, `clear_skip`. Part of the test's settings. Details: `BEV_IDEAS_FOR_BENCHMARKS.md`. |
| `--max-reconnects N` | How many times one episode may be started again after the board drops off USB (default 20). |
| `--bev-device npu\|cpu` | bev only: where `bev-decide` runs. `npu` (default) shares the Hexagon NPU (HTP0) with the Llama lane; `cpu` is the fallback on the board CPU. |
| `--mode lockstep\|realtime` | `lockstep` (default): ticks run back to back, and each tick waits for its model answers. This is how the single-agent results were made, so use it for comparisons. `realtime`: one tick every `--tick-s` seconds, and a tick never waits for a model (multi only, merge rule `model` only). |
| `--tick-s N` | Realtime only: seconds per tick (default 30). |
| `--merge-rule R` | multi and bev: `model`, `belief_only`, `tiebreak`, `nudge` or `hybrid`. Overrides the overlay's rule. The decider's pick reaches the ranking only under `nudge` and `hybrid`. |
| `--again` | Run episodes this test already has once more. The new run is saved as `_r2`, `_r3`, ... |
| `--backend mock` | Laptop only, no board. Results go to `results/benchmarks_mock/`. This checks the plumbing and is **never** an agent result. |
| `--no-prompts` | Do not save prompts and raw model replies. They are saved by default and are needed by `bench/replay_multi.py`. |
| `--cool-margin C` | Before each episode, wait until the chip is within C degrees of the reading at the start (default 5) ... |
| `--cool-max S` | ... but wait at most S seconds (default 900). |
| `--plain` | Print one line per tick instead of the full-screen monitor (for logs or pipes). |

---

## 4. More examples

v3 (the best multi-agent version) on the six episodes:

```
scripts/benchmark.sh v3_six ep_N01_normal ep_A01_fcv_seize ep_B01_tube_leak \
    ep_C01_wet_coal ep_D01_high_cv_coal ep_E01_fouling_drift --overlay configs/v3.yaml
```

v3 plus the bev-decider on the same six (default overlay `configs/bev3.yaml`):

```
scripts/benchmark.sh bev3_six ep_N01_normal ep_A01_fcv_seize ep_B01_tube_leak \
    ep_C01_wet_coal ep_D01_high_cv_coal ep_E01_fouling_drift --arch bev
```

The bev-decider on the board CPU instead of the NPU:

```
scripts/benchmark.sh bev3_cpu ep_A01_fcv_seize --arch bev --bev-device cpu
```

Single agent on the same episodes, under its own name:

```
scripts/benchmark.sh six_single ep_A01_fcv_seize ep_B01_tube_leak --arch single
```

Real time, a tick every 30 s (the demonstration):

```
scripts/benchmark.sh rt_demo ep_A01_fcv_seize --mode realtime --tick-s 30
```

Teammate's accuracy setup on dev episodes:

```
scripts/benchmark.sh tiebreak_quick dev_A01_fcv_seize dev_B01_tube_leak \
    --overlay configs/accuracy.yaml --merge-rule tiebreak
```

Repeat an episode a test already has:

```
scripts/benchmark.sh six_episodes ep_A01_fcv_seize --again
```

Try the command on the laptop without the board (works for `--arch bev` too: the mock decider backs belief's leader
and reads nothing, so it only checks the plumbing):

```
scripts/benchmark.sh try1 dev_C01_wet_coal --backend mock
scripts/benchmark.sh try_bev dev_A01_fcv_seize --arch bev --backend mock
```

---

## 5. What happens when you run it

1. Checks the name, the episodes and the options, the board, and that nothing else is using the board.
2. Stops any running `llama-server` lanes and reads the chip temperature. That reading is the cooling target for the
   whole batch.
3. `--arch bev` only:
   - If `bev-decide` is not answering, it checks the sha256 of its binary, GGUF and head on the board and starts it.
     If it is already answering, it checks those files and that it serves the configured model.
   - Confirms from its startup log that it is fully on the NPU: device HTP0, a nonzero HTP0 model buffer, every layer
     offloaded. With `--bev-device cpu` it confirms it is not on the NPU. If either check fails, it stops.
   - `bev-decide` then stays up for the whole batch.
4. For each episode:
   1. Waits for the chip to cool, if needed.
   2. Starts the `llama-server` lanes fresh with the fixed flags and checks the model file checksums.
   3. Confirms from the startup logs that the NPU lane is fully on the NPU and that the CPU lane is not. For bev, it
      checks again that `bev-decide` answers, restarting it if it went away. If a check fails, it stops.
   4. Runs the episode while the monitor shows it live.
   5. Logs the chip temperature, stops the `llama-server` lanes, and saves the results.
   6. bev only: if **any decider call failed** (bev-decide gave no answer), the episode is **not kept**. A failed call
      silently leaves that tick without the decider, so the run would not measure the configuration. Its run file is
      saved as `<stem>.rejected-<time>.*` and the batch stops. Fix the cause and run the same command again. A
      decider answer **refused by the gate** is a result, not an error, and is kept.
5. When all episodes are done, it leaves the monitor and prints the results table. If the runner started
   `bev-decide`, it stops it; if it was already running, it is left running.

---

## 6. Reading the monitor

### Top lines (cyan)
The test name, the results folder, episode *i* of *n*, what the runner is doing (cooling, starting a lane, starting
bev-decide, running, saving), and one line per episode already saved in this session (for bev, with the decider's
calls, failures and rejections).

### Header
- Episode, architecture, elapsed time, mode, and the tick number of the last tick.
- Model calls answered, and tokens in / out so far (decider calls included; they write 0 answer tokens).
- Per agent: number of calls, median call time, median input tokens, and how many answers could not be used.
- The green score line (see section 7).

### Units
- **CODE:** the agent's non-model work on the laptop: how long the last tick took, the worst so far, and the 200 ms
  limit. These are laptop times, not board times.
- **NPU / CPU:** what each board lane is doing now (live from the server), plus its last answer: run time, tokens
  in and out, and whether it was used.
- **BEV** (bev only): `bev-decide`. It reports its health (`up (health ok)`, or `NOT ANSWERING /health`), but not
  whether it is busy. The tick table shows its calls.

### Tick table (one row per tick)

For bev, a row reads in the order the tick runs: code → diagnosis → decider → merge rule → verifier → published
answer.

| column | meaning |
|---|---|
| `tick`, `plant` | tick number and simulated plant time |
| `state`, `triage` | worked out by code (models are called at WATCH or above) |
| `code` | the tick's non-model time |
| job columns | multi: `water·NPU`, `heat·NPU`, `verify·CPU`, `notes·CPU`. single: `diagnose·NPU`, `verify·NPU`. bev: `water·NPU`, `heat·NPU`, **`decide·bev`**, `verify·CPU`, `notes·CPU` |
| `rule` (bev) | the merge rule's regime this tick, under `hybrid`: `clear` (belief has a clear leader: belief plus the bonuses decide), `tie` or `weak` (the diagnosticians' picks lead). `+` = the diagnosticians' picks did lead. The decider can't change the top cause on a `tie+` or `weak+` tick. |
| `pub`, `bel`, `dec`, `conf` | see section 7 (`dec`: bev only) |
| `top cause` | the published top cause |

### Job cells

| cell | meaning |
|---|---|
| `2.8s 712t✓` | the call took 2.8 s and read 712 input tokens (repair call included); the answer was used |
| `0.4s 398t✓` in `decide·bev` | one bev-decider decision: one forward pass over 398 prompt tokens, no answer tokens; the gate accepted it |
| `✓` | answer used (for the decider: accepted by the gate, which checks every offered case got a probability) |
| `∅` | well-formed, but it ranked no case it was shown |
| `✗` | wrong format, failed call, rejected note reading, or (decider) failed or refused by the gate |
| `~` | arrived too late, dropped (realtime only) |
| `▶3s` | running for 3 s (realtime only) |
| `answered` | done; it is used at the next tick (realtime only) |
| `reuse` | no new call; the earlier answer was kept because the evidence had not changed |
| `·` | not asked this tick. The decider is asked only when its evidence (the offered causes, signature or open findings) changed, and only when there are at least two causes to offer |
| `—` | quiet tick, no models involved |

Row colours: yellow means a job is still running, grey means a quiet tick. Red is never used.

- **`•` right after the tick number** (dim): one of that tick's calls had an answer that wasn't used (a `✗` or `~` in
  its cell). The tick still published; it fell back on the other answers and belief.
- **Teal** (bev only) marks everything that belongs to the bev-decider: the `decide·bev` column and cells, the `dec`
  marks, the `BEV` unit line and the decider legend line.
- **Bold `CODE` line** with "OVER the limit on some tick": a tick's code path took more than 200 ms.

In lockstep, a row appears only when its whole tick is finished. While a tick runs, the lanes show busy or idle, but
the job is named only once the tick is written.

---

## 7. The metrics explained

### Two rankings exist on every tick

- **Belief, the code-only ranking.** The code turns the sensor facts into a score for each candidate cause from the
  case library and keeps updating those scores tick after tick. No model is involved.
- **The published ranking,** what the system actually shows the engineer. The model answers reach it through the
  **merge rule** (`multi.merge_rule`): `model` (the model's order wins), `tiebreak`, `nudge` (each answer gives a small
  capped bonus), or `hybrid` (v3: the model leads when belief is weak or tied, else nudge). In bev, the decider's pick
  is one more capped bonus; it is summed with the diagnosticians' bonus, and the sum is capped at 1.2 per case per
  episode. It never pushes the three "filler" cases.

The model is only worth running if the published ranking is right more often than belief alone. These metrics
compare the two.

### Per-tick columns: `pub`, `bel`, `dec`, `conf`

**`pub`**: is the published top cause right?
**`bel`**: would belief's own top cause have been right?
**`dec`** (bev only): was the **decider's own pick** right, on ticks where it answered? Blank when it wasn't called or
the tick isn't scored.

| mark | meaning |
|---|---|
| `✓` | it is the true cause (the exact case from the library) |
| `≈` | not the exact case, but one in the same look-alike group: cases the sensors cannot tell apart, e.g. a seized feed valve and a feed-pump problem both show as "feed water short". The groups are fixed in `data/kb/case_groups.json`. |
| `✗` | wrong group |
| `pre` | the fault has not started yet, so the tick is not scored |
| blank | quiet tick, or a no-fault episode (nothing to be right about) |

How to read the pair:

| `pub` | `bel` | meaning |
|---|---|---|
| ✓ or ≈ | ✗ | the model fixed belief's mistake |
| ✗ | ✓ or ≈ | the model made it worse |
| same | same | the model changed nothing that matters |

For bev, compare `dec` with `pub`: a wrong `dec` on a `clear` tick is where the decider can pull the published answer
wrong.

**`conf`**: the confidence shown for the published top cause, from 0 to 1. It is capped by how far that cause is
ahead of its nearest rival, so two tied causes show 0.50 even if each looks likely on its own. It is display only;
nothing in the agent decides on it.

### The score line (green, in the header)

This is computed by the same scoring code that writes the final summary (`bench/evaluator.py`), so the live numbers
become the final ones.

| metric | meaning |
|---|---|
| true cause | the episode's real cause, e.g. `RCA-01` |
| scored ticks | ticks counted so far: from fault onset onward, with a ranking published |
| published group top-1 | share of scored ticks where `pub` was ✓ or ≈. **The headline accuracy.** |
| belief alone | the same share for `bel`; the bar the model has to beat |
| exact top-1 | share of scored ticks where `pub` was ✓ only (the exact case) |
| mean shown confidence | average `conf` over scored ticks |
| decider's pick right *k*/*n* (bev) | scored ticks with a decider answer whose pick was ✓ or ≈ |

Some episodes are scored differently:
- **Held-out cause** (e.g. C01, wet coal, RCA-06): the true case was deliberately left out of the library to test
  generalisation. The system can never name it exactly, so exact top-1 is not shown and only group credit counts.
- **No-fault episode** (N01): there is no cause to find. The line shows the false alarms instead: ticks where the
  state was not NORMAL, per hour, with a target of 2 per hour or fewer.

### Token and call metrics

| where | metric | meaning |
|---|---|---|
| job cell | `2.8s 712t✓` | the call took 2.8 s and the model read 712 input tokens (prompt tokens as the server counted them, repair call included) |
| header | tokens in / out | total prompt tokens read and answer tokens written so far |
| per-agent line | median call time, median tokens in | the typical call for that agent |
| per-agent line | not usable | answers that could not be used: wrong format, failed call, rejected note reading, too late, or (decider) failed or refused |
| lane line | last answer: … tokens in / out | the most recent call on that lane |

Input tokens matter for speed. On the NPU, reading the prompt runs at roughly 650–900 tokens/s for Llama 3.2 3B and
writing the answer at about 14–20 tokens/s, so prompt size drives part of every call's time. The decider only reads
(about 1,600 tokens/s on HTP0 for bev-decider 0.4B); it writes nothing.

### Metrics in RESULTS.md

The same numbers per finished episode (group top-1, belief group top-1, exact top-1, tokens in, unusable answers),
next to the older evaluator metrics:

| metric | meaning |
|---|---|
| bev idea calls / failed / rejected (bev ideas) | all bev-decide calls the ideas made; failed must be 0 (a failed call makes the run invalid: it is saved as `*.rejected-*` and the batch stops) |
| bev used / shadow (bev ideas) | answers that changed what the agent did / answers only logged (shadow) |
| decode tokens per tick | answer tokens written by every model, per tick (bev writes none): the number the speed ideas try to cut |
| server CPU s npu / cpu / bev, peak RSS MB npu / cpu / bev | from the on-board sampler, per episode: CPU seconds and peak memory of each model server. The NPU has no readable usage counter |
| decider calls / failed / rejected (bev) | decider calls; calls with no answer from bev-decide (must be 0 for a kept run); answers refused by the gate's check |
| replay ok (bev) | `bench/replay_multi.py` rebuilds every published ranking from the saved answers, decider included: `yes` means the run is fully explained by its saved answers |
| faithfulness | share of cited fact IDs that really exist |
| actions precision / recall | suggested actions against the correct ones |
| lead time | minutes between the first correct call and the trip |
| false alarms /h | no-fault episodes only: ticks not NORMAL, per hour |
| tick p95 | the slowest 5% of tick times (laptop time) |

For bev, "model calls" includes the decider's calls.

---

## 8. The results folder

`results/benchmarks/<test name>/`

| file | contents |
|---|---|
| `test.json` | the test's settings and every run: start and finish time, git commit and whether there were uncommitted changes, chip temperature before and after, cooling wait, wall time, exit code, status (done / failed / interrupted / rejected) |
| `RESULTS.md` | one row per finished episode run (see section 7) |
| `temps.jsonl` | chip temperature before and after every episode |
| `<ep>_<arch>.summary.json` | evaluation, run facts (calls, tokens, unusable answers per agent; for bev the decider's calls / failed / rejected and the replay check) and settings |
| `<ep>_<arch>.run.json.gz` | every tick, every prompt and raw reply (the decider's request and probabilities too) |
| `<ep>_<arch>.log` | the run's own output |
| `<ep>_<arch>.lanes.txt` | the startup lines that prove NPU / CPU placement (for bev, bev-decide's too) |
| `<ep>_<arch>_r2.*` | a repeat made with `--again` |
| `<ep>_bev.rejected-<time>.*` | bev: an episode with a failed decider call, kept aside, not counted |

`<arch>` is `multi`, `single` or `bev`.

While an episode runs there is also `<ep>_<arch>.ticks.jsonl`, written every tick. It is deleted once the run file is
saved, because the run file holds the same ticks.

Git: `test.json`, `RESULTS.md`, temps, summaries, run files, logs and lane files are tracked. Live tick files,
stopped attempts and mock results are not.

The earlier bev folders `bev_armB` and `bev3_armB` were made before `--arch bev` existed (as multi runs with the bev
overlays). Their files are named `*_multi.*`, and the runner won't add to them: it refuses `--arch multi` with a
decider overlay. Use a new test name.

---

## 9. Unplugging the board, resuming, and the run log

**You can pull the USB cable at any time.**
- While an episode runs, the runner sees the lost connection and shows `BOARD DISCONNECTED ... plug it back in`. It
  waits; when the board is back it re-forwards the ports and starts **that episode again from its first tick**. The
  cut attempt is kept as `<stem>.interrupted-<time>.*`.
- If you'd rather stop, press Ctrl-C and run the **same command** later. It skips every episode already saved and
  continues with the first unfinished one.
- With `--again`, the same command continues the same round: episodes already repeated in that round are skipped
  ("already repeated in round 1"), so nothing is run twice. A new round starts only after the previous one finished.
- An episode cut mid-way always restarts from its first tick: the agent's state at the cut is not saved, so a
  half-episode is never mixed into a result.
- bev-decide keeps running on the board through an unplug. The runner re-forwards port 8082 and only restarts
  bev-decide if it really stopped.

**Run log.** Every command and every event is appended to `results/benchmarks/RUN_LOG.md` (a table) and
`RUN_LOG.jsonl`, never rewritten:
- the batch start, with the exact command, git commit and settings;
- each episode's start, finish, skip, failure or rejection;
- the board being lost or back;
- the round being resumed;
- the batch end, with its status.

## 9b. Same name again, resuming, repeats

- **Same test name, new episodes:** they are added to the same folder.
- **Same test name, an episode it already has:** skipped, with a message. This is how a stopped test resumes; run the
  same command again.
- **`--again`:** the episode is run once more and saved as `_r2`, `_r3`, ... Nothing is ever overwritten.
- **Same test name with different settings** (architecture, mode, tick, overlay or its contents, merge rule, models,
  backend, prompt saving, bev device): refused, with the differences listed. Use a new name for a new setup.

---

## 10. Stopping

Press **Ctrl-C** once:
- the episode run is stopped and the `llama-server` lanes are shut down (and `bev-decide`, if this run started it);
- the stopped episode's ticks, log and lane file are kept as `<stem>.interrupted-<time>.*` and marked
  "interrupted" in `test.json`;
- episodes already saved are kept;
- run the same command again to continue. The stopped episode starts over.

A second Ctrl-C leaves at once.

If an episode fails on its own (not Ctrl-C), the batch stops and the end of that episode's log is printed.

---

## 11. Troubleshooting

| message or symptom | what to do |
|---|---|
| "another board run is going" | Something else uses the board. Wait for it or stop it. |
| "need exactly one board on adb" | Check the cable and run `adb devices`. |
| "the NPU lane is not fully on the NPU" | The NPU server did not load on the NPU. Read `<stem>.lanes.txt`. Do not work around it. |
| "already exists with other settings" | You reused a test name with different options. Pick a new name. |
| "unknown episode(s)" | Check the spelling. Dev episodes start with `dev_`, reporting episodes with `ep_`. |
| "... turns the bev-decider on: use --arch bev" | The overlay (e.g. `configs/bev3.yaml`) has the decider on. Add `--arch bev`. |
| "--arch bev needs an overlay with the decider on" | Use `configs/bev3.yaml` (the default) or `configs/bev.yaml`. |
| "no recorded sha256" / "board sha256 ... !=" | The bev-decider files on the board aren't the recorded build. Don't edit the recorded value: push the right files (see `HANDOFF_BEV_DECIDER_3.md`). |
| "bev-decide did not come up" / "is not fully on the NPU" | Read `.venv/bin/python -m bench.board log bev`. If HTP0 fails, `--bev-device cpu` is the fallback (a different configuration: use a new test name). |
| "bev-decide is not serving ..." | Another bev model is loaded (e.g. the 16-bit one from the conformance check). Run `.venv/bin/python -m bench.board stop bev` and run again. |
| "not kept: N decider call(s) failed" | bev-decide stopped answering or was too slow (timeout 120 s). Check `adb devices`, `bench.board log bev`, then run the same command again. The bad run is kept as `*.rejected-*`. |
| the run stops with `RemoteDisconnected` | The board connection dropped (`bev-decider-3` lacks the drop fix). Check `adb devices` and run the same command again; it resumes. |
| the monitor looks frozen | In lockstep, a tick's row appears only when its model calls finish. If the NPU / CPU lines show "working", it is running. |
| screen garbled after a crash | Type `reset` and press Enter. |

---

## 12. What to keep in mind when reporting

- Mock results are plumbing only, never agent results. The mock decider doesn't read the plant.
- Tick and code times are laptop times. Only model calls run on the board.
- Energy is not measured; it is left empty, never estimated.
- All plant data is synthetic.
- The answer grammar (on in `configs/fast.yaml` and the overlays built on it) makes wrong-format answers impossible,
  so a zero wrong-format rate says nothing about the model.
- Decisions about thresholds or prompts are made on `dev_` episodes, not on the `ep_` reporting episodes.
- bev: the board version of bev-decider hasn't been checked against the original model (the conformance check in
  `HANDOFF_BEV_DECIDER_3.md`). Say it runs; don't say its answers equal the original's.

---

## 13. Status of this command (19 October 2026)

- 19 October:
  - merged with `bev-ideas` (bev-idea switches, on-board resource sampler, `bench/bev_report.py`);
  - **fixed: `--arch bev` now starts both Llama lanes.** It started only the NPU lane before, so `bev3_six` A01's
    verifier calls all failed; that run is moved to `results/benchmarks/bev3_six/invalid/`;
  - bev-decide is managed for any config with a bev lane;
  - unplug-and-resume, `--again` rounds and the run log added;
  - all tested on the mock backend; not yet on the board.

- `multi` and `single`: tested on the laptop with the mock backend (folders and files, resume, `--again`, refusal of
  other settings, token counts, per-tick marks that match the evaluator's score). Used on the board for every
  benchmark since 7 October.
- `bev`: added 8 October.
  - Tested on the laptop with the mock backend: files, settings, decider counts that match the run file, the replay
    check, the monitor's decider cells, `rule` and `dec` columns, and the refusals.
  - The rule that rejects a failed decider call is tested directly.
  - **Not yet run on the board through `--arch bev`:** the bev-decide start, sha256 and placement checks, and its
    health line in the monitor. bev-decider itself has run on the board (the `bev3_armB` runs). Watch the first
    minute of the first board run.

Files:
- `scripts/benchmark.sh`: the entry point
- `bench/benchmark.py`: the runner
- `bench/stage_monitor_multi.py`: the monitor. It can also view a run on its own:
  `.venv/bin/python bench/stage_monitor_multi.py` (picks `configs/bev3.yaml` for a `*_bev` run)
- `bench/board.py`: the board servers (`start bev`, `log bev`, `stop bev` for bev-decide)
- `tests/test_benchmark.py`, `tests/test_stage_monitor_multi.py`: the tests
