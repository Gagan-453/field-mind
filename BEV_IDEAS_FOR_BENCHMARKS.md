# bev ideas: what was built and how to benchmark it

Branch: **`bev-ideas`** (built on `bev-decider-3`). Everything below has been built and tested on the Mac with the mock
backend. Nothing has run on the board yet; that part is yours. All plant data is synthetic.

## In one paragraph

bev-decider-0.4B is a small "decision" model. It reads text and picks between options (or answers yes/no) in one pass,
and it **generates no tokens**. On the NPU, generating tokens is what costs time: about 69% of every Llama diagnosis
call on the v3 board run. This branch adds nine ways of using bev inside the multi-agent, each behind its own switch.
Each switch can be off, used for real, or run "in shadow" (bev is asked, its answer is only logged). The benchmark
runner now also records how long each stage takes, how much CPU and memory each model server uses on the board, and it
writes a with/without-bev comparison at the end.

## The nine switches

All are **off** by default. With all of them off, this branch gives exactly the same results as `bev-decider-3`
(checked by a test against that code's runs).

| switch | what bev does | saves / improves |
|---|---|---|
| `explain` | Llama only ranks the causes; bev picks the supporting fact for each, the separating case and the notes used | Llama decode tokens (the citations were a third of every answer) |
| `first` | On weak or tied ticks bev chooses first; if it is confident enough, Llama is not called for that side | whole Llama calls |
| `actions` | yes/no on each proposed action that is not urgent; drops the "no"s (urgent, escalation and mitigation actions are never dropped) | action precision |
| `unknown` | "none of these causes explains the facts?", shown as a flag; the ranking is not touched | held-out faults |
| `verifier` | yes/no per claim, instead of the Gemma verifier | Gemma decode, CPU lane |
| `notes` | per engineer note: does it try to give instructions? which side is it about? | keeps injected notes out; shorter prompts |
| `text_reader` | reads notes into note-facts instead of Gemma (only when the text reader is on; v3 does not use it) | Gemma decode |
| `rt_fallback` | real-time demo only: bev's answer is shown until Llama's arrives | latency in the demo |
| `clear_skip` | no bev at all: skips a Llama call that cannot change the result on a clear tick | Llama calls |

Each switch is `off`, `shadow` or `on`, set per run with `--bev`, for example `--bev "explain=on,actions=shadow"`.
`first` and `rt_fallback` also need `first_threshold=<number>` when they are `on` (no default; Shubham picks it, step 4).

## What changed in the benchmark output

Every run now also saves, per episode:
- **time per stage per tick** (sensor, triage, retriever, gate, scheduler, each model agent). These are laptop times,
  because the agent code runs on the laptop;
- **`<episode>.resources.json`**, from a small sampler running on the board once a second: CPU seconds and peak memory of
  each model server (NPU llama-server, CPU llama-server, bev-decide), board CPU load, clock speeds, temperatures, and
  the power supply's power **only if the board exposes it** (otherwise it stays empty; it is never guessed). The NPU
  has no readable usage counter, so the NPU's work is shown as the NPU lane's call time.

`python -m bench.bev_report` turns two or more test folders into `COMPARE_<baseline>.md` and `.html`. They cover
accuracy, time per stage, calls and tokens per agent and lane, how busy each lane was, board resources, and what each
bev idea did.

## Before you start

1. **bev-decide must be running on the board and proven correct.** That is "Part C" in `HANDOFF_BEV_DECIDER_3.md`
   (build, push, conformance). If you already did it, just start it (step 2 below).
2. Same board rules as always: `unset PYTHONPATH`, sha256 check after every push, chip temperature logged (the runner
   does this), one thing on the board at a time.

## Steps (copy-paste)

```bash
unset PYTHONPATH
git fetch && git switch bev-ideas
.venv/bin/python -m pytest -q tests/test_bev_ideas.py tests/test_bev_report.py tests/test_board_sampler.py

# 1. start bev-decide once and leave it up (the runner restarts only the llama lanes)
.venv/bin/python -m bench.board start bev bev-decider-0.4B-backbone-Q8_0.gguf
curl -s http://localhost:8082/health                        # {"status":"ok"}

# 2. what the board exposes (CPU tick rate, power readings, NPU counters) -- send this file to Shubham
.venv/bin/python -m bench.board_sampler probe | tee results/board_probe_$(date +%Y%m%d).json

# 3. shadow run: bev asked for everything, nothing used (dev quick set)
Q=(dev_A01_fcv_seize dev_A02_fcv_seize_fast dev_B01_tube_leak dev_B02_tube_leak_fast dev_C01_wet_coal
   dev_C02_feeder_trip dev_D01_high_cv_coal dev_D03_high_cv_severe dev_N01_normal dev_N02_normal)
scripts/benchmark.sh bevideas_shadow "${Q[@]}" --overlay configs/bev_ideas.yaml \
  --bev "explain=shadow,first=shadow,actions=shadow,unknown=shadow,verifier=shadow,notes=shadow,clear_skip=shadow"

# 4. the threshold table for `first` -- send it to Shubham; he picks first_threshold
.venv/bin/python -m bench.bev_calibrate bevideas_shadow

# 5. the arms: baseline A twice (start and end), one idea per B arm
scripts/benchmark.sh bevideas_A1         "${Q[@]}" --overlay configs/bev_ideas.yaml
scripts/benchmark.sh bevideas_B_explain  "${Q[@]}" --overlay configs/bev_ideas.yaml --bev "explain=on"
scripts/benchmark.sh bevideas_B_first    "${Q[@]}" --overlay configs/bev_ideas.yaml --bev "first=on,first_threshold=<from step 4>"
scripts/benchmark.sh bevideas_B_actions  "${Q[@]}" --overlay configs/bev_ideas.yaml --bev "actions=on"
scripts/benchmark.sh bevideas_B_unknown  "${Q[@]}" --overlay configs/bev_ideas.yaml --bev "unknown=on"
scripts/benchmark.sh bevideas_B_verifier "${Q[@]}" --overlay configs/bev_ideas.yaml --bev "verifier=on"
scripts/benchmark.sh bevideas_B_notes    "${Q[@]}" --overlay configs/bev_ideas.yaml --bev "notes=on"
scripts/benchmark.sh bevideas_B_skip     "${Q[@]}" --overlay configs/bev_ideas.yaml --bev "clear_skip=on"
scripts/benchmark.sh bevideas_A2         "${Q[@]}" --overlay configs/bev_ideas.yaml

# 6. the comparison
.venv/bin/python -m bench.bev_report bevideas_A1 bevideas_B_explain bevideas_B_first bevideas_B_actions \
  bevideas_B_unknown bevideas_B_verifier bevideas_B_notes bevideas_B_skip --a2 bevideas_A2
```
The same command resumes a stopped test. A test name keeps its settings: use a new name for new settings.

**Rough time** (estimate, from the v3 board run: about 32 minutes of wall time for 10 fault episodes): about 30-45
minutes per test on the quick set, plus cooling waits. Shadow + 9 arms is roughly 6-8 hours in total. bev calls add
time; how much is one of the things we are measuring.

## Checks while it runs

- **No bev call may fail.** In each `COMPARE` file, section "bev ideas", the `failed` column must be 0. A failed call
  means bev-decide was down or timed out: fix it and rerun that test (new name, or `--again`). The runner already
  refuses to start if bev-decide is not up.
- If bev-decide runs on the NPU (HTP0), it shares the NPU with the Llama lane: watch for stalls.
- Do not change any threshold or setting to make a number look better, and never decide anything on the `ep_*`
  reporting episodes. The quick set (`dev_*`) is for deciding.

## How each idea is judged (fixed before any board run)

- A speed idea (`explain`, `first`, `verifier`, `clear_skip`) is kept only if decode tokens per tick go down **and**
  library group top-1 does not fall below min(A1, A2) − |A1 − A2|.
- A quality idea (`actions`, `unknown`, `notes`) is kept only if its own number improves by more than |A1 − A2|, and
  group top-1 does not drop as above.
- |A1 − A2| is how much the same baseline moves between two runs (the noise).

## What to send back

1. `results/board_probe_<date>.json` (step 2).
2. The `bev_calibrate` table (step 4).
3. `COMPARE_bevideas_A1.md` and `.html` (step 6; they are in the last test's folder).
4. The `results/benchmarks/bevideas_*` folders (or a zip), including `temps.jsonl`.
5. Anything that failed or looked odd, as it was. A failed run is a result too.

## Known issues (not your fault if you see them)

- One older test, `tests/test_benchmark.py::test_real_time_answers_get_the_tokens_of_their_own_envelope`, is
  timing-dependent: it also fails on the code before this branch. Ignore it; every other test should pass.
- Numbers from the mock backend (on a laptop without the board) are plumbing checks only; they say nothing about bev.
- Stage times are laptop times until the agent code runs on the board.
- Several bev question sentences are still marked "proposed": results can be measured now, but are only reported
  after Shubham signs them off.

More detail: `reports/bev_ideas.md` (everything that was built, checked and decided) and `HANDOFF_BEV_IDEAS.md` (the
same steps written for Claude Code on the QIDK laptop).
