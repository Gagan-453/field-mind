# Handoff: bev-decider on multi-agent v3, on the QIDK (Part C), branch `bev-decider-3`

For Claude Code on the **QIDK laptop**, in the FieldMind repo, branch **`bev-decider-3`**. Everything that can be done
without the board is built, tested and committed. This file is the board part: build, push, prove the port is correct,
then measure whether bev-decider improves multi-agent v3. Follow it in order. Do not skip a check because the next
step looks like it would work.

Read first, in this order: `CLAUDE.md` (project rules: they apply to every step here); `reports/bev_decider.md` (what
was built and verified, what is not, open decisions; section "bev-decider-3: the decider on multi-agent v3" is about
this branch); `reports/multi_v3_results.md` (where v3 stands on the board without the decider).

**What `bev-decider-3` holds:** `main` as of 56e8bcf (multi-agent v3: merge rule `hybrid` with the flat-case guard,
raw notes to the diagnostician, group letters off, the benchmark runner; the v3 board results), plus the bev-decider
integration: weight split, `bev-decide` (C++ server), backend, decider agent with the combined candidates and the
filler guard, its path under `hybrid`, board tooling, conformance tool. **With the decider off, this branch publishes
exactly what `main` publishes** (20 mock dev runs, 3,440 ticks, configs v3 / fast / tiebreak / nudge: 0 differences).

---

## 1. What this is

- **bev-decider-0.4B** (huggingface.co/avbiswas/bev-decider-0.4B, CC-BY-NC) is a "System One" decision model: the
  first 20 layers of Qwen3-0.6B plus a small decision head. Given a state and a few options it returns one
  probability per option in a single forward pass, no text generated, and the option order cannot change the answer.
- In FieldMind it is a **third model agent, the decider**. Whenever its evidence changes it is shown the tick's facts
  and the **combined candidates**: belief's top 3 cases, then the Llama diagnosticians' top 3 of that tick that
  belief's list does not hold (3 to 6 cases). It picks one; the gate checks the answer.
- **How its pick counts under v3's `hybrid`:** a capped offset (+0.35 to its pick, +0.175 to its second; summed with
  the diagnosticians' offsets, the sum capped at 1.2 per case per episode), never pushed to the all-FLAT cases
  RCA-09/10/15 (**filler guard**). `hybrid` decides who leads from belief alone, exactly as in v3: on weak or tied
  ticks the model's picks still lead and **the decider cannot change that top cause** (tested); it changes the order
  on clear ticks and the cases after the model's picks. It never writes belief.
- On the board it runs as **`bev-decide`**, built from the SAME llama.cpp as `llama-server` (b11371, commit 99b95488),
  on **port 8082**, beside the two lanes of v3: NPU 8080 (Llama 3.2 3B, both diagnosticians), CPU 8081 (Gemma 3 1B,
  verifier).
- **No new libraries on the board.** Three new files: the `bev-decide` binary, one GGUF, the head (`bev_head.bin` +
  `bev_head.json`). It reuses `/data/local/tmp/llm/llama.cpp/lib`.
- **Configs:** arm A = `configs/v3.yaml` (v3 as measured on the board). Arm B = `configs/bev3.yaml` = `v3.yaml` + the
  decider + the bev lane, nothing else (test-enforced). The decider is OFF in `configs/base.yaml`.

## 2. Rules for this session

1. Run every command from the repo root, **in bash** (the scripts use bash arrays). `unset PYTHONPATH` first (this
   laptop exports the QAIRT SDK's python folder).
2. **Dev episodes only** (`data/episodes_dev`). The reporting episodes are not run in this work, except once at the
   very end if the pass rule in step 6 passes, and only if the human says so.
3. Never push. Commit locally with "bev-decider-3" in the message.
4. Never delete data. To redo an episode, move its files into an `invalid/` subfolder.
5. Log chip temperature before and after every run; the runner does it. **Start every batch with a cool chip:** the
   runner takes its cooling target from the first reading of the batch (the v3 run lost its cooling after a restart
   on a hot chip, `reports/multi_v3_results.md` 1.1).
6. **Stop and report** (do not work around) when: a sha256 differs between laptop and board; `build_gguf.sh` or
   `build_android.sh` prints `STOP`; the conformance token check fails (exit 3); `bev-decide` will not start or
   crashes; a llama.cpp error mentions sequences, positions, the KV cache or memory; any decider call fails in a
   kept measurement run. Say what you saw, with the log lines.
7. No accuracy claim from anything here until step 6's pass rule is evaluated. Mock-backend numbers are never
   bev-decider results.

---

## 3. Step 0: preconditions (about 5 minutes)

```bash
unset PYTHONPATH
git fetch origin && git checkout bev-decider-3 && git pull --ff-only && git log --oneline -3
export BUILD=${BUILD:-$HOME/fieldmind-build}
git -C "$BUILD/llama.cpp" rev-parse HEAD                                  # must start 99b95488
ls "$BUILD/build-host/bin/llama-quantize" "$BUILD/venv-convert/bin/python"
adb devices                                                               # exactly one device
adb shell "cd /data/local/tmp/llm/llama.cpp && LD_LIBRARY_PATH=/data/local/tmp/llm/llama.cpp/lib ./bin/llama-server --version"
                                                                          # must print commit 99b95488c
ls data/episodes_dev | wc -l                                              # 36; if missing:
#   .venv/bin/python -m data.generator.episode_build --set dev
.venv/bin/python -m pytest -q tests/test_bev_convert.py tests/test_bev_core.py tests/test_bev_backend.py \
    tests/test_decider.py tests/test_bev_conformance.py tests/test_bev_board.py      # 82 passed
BEV_LLAMA_SRC="$BUILD/llama.cpp" .venv/bin/python -m pytest -q tests/test_bev_manifest.py   # 1 passed
```
If the branch is not on `origin`, ask the human for it. If you run the full suite, deselect
`tests/test_campaign.py::test_kill_minus_9_mid_episode_then_resume_is_identical` (timing-flaky, passes about 2 times
in 3).

## 4. Step 1: the weights (about 5 minutes)

```bash
# the model folder lives at the repo root and is gitignored
[ -d bev-decider-0.4B ] || { git lfs install && git clone https://huggingface.co/avbiswas/bev-decider-0.4B; }
(cd bev-decider-0.4B && git lfs pull)
stat -c '%s %n' bev-decider-0.4B/model.safetensors bev-decider-0.4B/tokenizer.json
#   969892808 model.safetensors      11422654 tokenizer.json   (sizes from the lfs pointers)
sha256sum bev-decider-0.4B/model.safetensors
#   e28f9f5ac08bd939b50021bce652e1f87530ff8a187fbeb3c7ec024b6c844282
```

## 5. Step 2: split and build the GGUFs (about 5 minutes)

```bash
device/bev_decide/build_gguf.sh bev-decider-0.4B
```
It splits the checkpoint (`bench/bev_convert.py` refuses an lfs pointer, a different file, or any unexpected tensor),
converts the 20-layer backbone to a 16-bit GGUF (kept for the CPU conformance run), quantizes `--pure Q8_0`, checks
every matrix is Q8_0, and prints size + sha256 of four files in `$BUILD/gguf/bev/`: `backbone-16bit.gguf`,
`bev-decider-0.4B-backbone-Q8_0.gguf`, `bev_head.bin`, `bev_head.json`. Keep that output. Logs:
`logs/bev_split.log`, `logs/bev_convert_gguf.log`, `logs/bev_quantize.log`, `logs/bev_gguf_types.log`. If
`convert_hf_to_gguf.py` fails, stop and report its log: it has not been run on this truncated model before.

## 6. Step 3: the reference (bev-decider itself, fp32 on the laptop CPU; about 5 minutes)

```bash
"$BUILD/venv-convert/bin/python" -c "import torch, transformers; print(torch.__version__, transformers.__version__)"
#   needs torch >= 2.4 and transformers >= 4.56 (bev_decider's requirements). If older, make a separate env
#   instead of upgrading venv-convert:  python3 -m venv ~/bev-ref-venv && ~/bev-ref-venv/bin/pip install bev-decider==0.2.1
#   and use ~/bev-ref-venv/bin/python below. Record which one you used.
"$BUILD/venv-convert/bin/pip" install --no-deps bev-decider==0.2.1          # 15 kB, pure Python
"$BUILD/venv-convert/bin/python" -m bench.bev_conformance reference bev-decider-0.4B \
    --requests reports/data/bev_requests.json --out reports/data/bev_reference.json
```
`reports/data/bev_requests.json` is committed: 24 real decider requests (combined candidates, 3 to 6 options), 3 from
each dev quick-set fault episode. Do not rebuild it on the board laptop: the reference and the board must see the same
requests.

## 7. Step 4: build bev-decide, push, record the sha256 (about 15 minutes)

```bash
# link against the exact package that is on the board
mkdir -p ~/bev-board-pkg && adb pull /data/local/tmp/llm/llama.cpp ~/bev-board-pkg/
ls ~/bev-board-pkg/llama.cpp/include/llama.h ~/bev-board-pkg/llama.cpp/lib/libllama.so \
   ~/bev-board-pkg/llama.cpp/lib/libggml.so ~/bev-board-pkg/llama.cpp/lib/libggml-base.so
#   if include/ is missing on the board, use the installed package the board was pushed from
#   (find "$BUILD" -name llama.h -path '*pkg*'), after checking its lib/libllama.so sha256 equals the board's
device/bev_decide/build_android.sh "$BUILD/llama.cpp" ~/bev-board-pkg/llama.cpp      # podman; ENGINE=docker to switch
file build-bev-android/bev-decide                                                    # ELF 64-bit, ARM aarch64

adb push build-bev-android/bev-decide /data/local/tmp/llm/llama.cpp/bin/
adb shell chmod 755 /data/local/tmp/llm/llama.cpp/bin/bev-decide
for f in bev-decider-0.4B-backbone-Q8_0.gguf backbone-16bit.gguf bev_head.bin bev_head.json; do
    adb push "$BUILD/gguf/bev/$f" /data/local/tmp/llm/
done
sha256sum build-bev-android/bev-decide "$BUILD"/gguf/bev/{bev-decider-0.4B-backbone-Q8_0.gguf,backbone-16bit.gguf,bev_head.bin,bev_head.json}
adb shell "sha256sum /data/local/tmp/llm/llama.cpp/bin/bev-decide /data/local/tmp/llm/bev-decider-0.4B-backbone-Q8_0.gguf \
    /data/local/tmp/llm/backbone-16bit.gguf /data/local/tmp/llm/bev_head.bin /data/local/tmp/llm/bev_head.json"
```
Laptop and board values must be equal, file by file. Then write them into `bench/board.py`: the four entries of
`BEV_FILES` and `BEV_BINARY_SHA256` (they are `None` today, so `start bev` refuses). Then:
```bash
.venv/bin/python -m pytest -q tests/test_bev_board.py      # 5 passed
git add bench/board.py && git commit -m "bev-decider-3: record the board build's sha256 (bev-decide, GGUFs, head)"
```

## 8. Step 5: conformance, before any agent run (about 20 minutes)

First the port on its own (16-bit weights, board CPU): any real difference here is a porting bug, not quantization.
```bash
.venv/bin/python -m bench.board stop                     # Llama lanes off for this part
.venv/bin/python -m bench.board temp
.venv/bin/python -m bench.board start bev backbone-16bit.gguf cpu
.venv/bin/python -m bench.board log bev | tail -60
.venv/bin/python -m bench.bev_conformance compare http://localhost:8082 \
    --reference reports/data/bev_reference.json --label cpu-16bit \
    --out reports/data/bev_conformance_cpu-16bit.json; echo "exit $?"
.venv/bin/python -m bench.board stop bev
```
Then the deployed form (Q8_0 on the NPU):
```bash
.venv/bin/python -m bench.board start bev bev-decider-0.4B-backbone-Q8_0.gguf
.venv/bin/python -m bench.board log bev | grep -E "HTP0|offloaded|bev-decide:"
.venv/bin/python -m bench.bev_conformance compare http://localhost:8082 \
    --reference reports/data/bev_reference.json --label htp0-q8 \
    --out reports/data/bev_conformance_htp0-q8.json; echo "exit $?"
```
Then beside v3's two lanes (Llama 3.2 3B on the NPU, Gemma 3 1B on the CPU), with `bev-decide` still up:
```bash
.venv/bin/python -m bench.board start npu Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf
.venv/bin/python -m bench.board start cpu gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf
.venv/bin/python -m bench.bev_conformance compare http://localhost:8082 \
    --reference reports/data/bev_reference.json --label htp0-q8-with-lanes \
    --out reports/data/bev_conformance_htp0-q8-with-lanes.json; echo "exit $?"
.venv/bin/python -m bench.board speed http://localhost:8080                     # the Llama NPU lane still answers
adb shell cat /proc/meminfo | head -3
adb shell "ps -A -o RSS,NAME | grep -E 'bev-decide|llama-server'"
.venv/bin/python -m bench.board stop                     # the runner starts the lanes itself in step 6
.venv/bin/python -m bench.board temp
```

How to read `compare` (exit code and printed summary):
- **exit 3**: token ids differ from bev_decider's. STOP and report the first differing request. Nothing after this is
  meaningful until it is fixed.
- **exit 4**: tokens fine, but some top choices differ: each is listed with the reference's top-two margin. On
  `cpu-16bit` every one must be a near-tie; otherwise treat it as a porting bug and report.
- **exit 0**: tokens identical, every top choice agrees.
- `max_abs_dp` / `median_abs_dp`: no automatic threshold (see the report for why). bev's README puts bf16 rounding
  noise near 0.001. If `cpu-16bit` is far above that, report it as a likely porting bug with the per-request rows. The
  gap between `cpu-16bit` and `htp0-q8` is the quantization + NPU drift: report it as measured.
- `shuffle_max_abs_dp`: change when only the option order changes; should be at noise level.
- `latency_ms_median`: one decider call on the board (prefill only). Report it next to `usage.prompt_tokens`.

In the startup log confirm, as for the NPU Llama lane: a nonzero `HTP0 model buffer size`, `offloaded N/N layers`
with both numbers equal, and the line `bev-decide: model ..., device HTP0, ngl 99, n_ctx 4096`. bev-decide has no
`-lv`; it is expected to print llama.cpp's loader lines anyway (not yet seen on this build). If they are missing, say
so. **If HTP0 fails** (start error, crash, or tokens fine on CPU but wrong on HTP0): stop and report; running the
decider on the board CPU instead (`start bev ... cpu`) is the planned fallback, but the human decides (v3's Gemma
lane already uses the CPU).

## 9. Before step 6: decisions the human must confirm

Ask the human (Shubham) and write the answers in `reports/bev_decider.md` under "Decisions taken" before measuring.
If nobody answers, the defaults below are what is built; changing 1, 2 or 5 needs a code change: do not make it, ask.

| decision | default (as built) | why it matters |
|---|---|---|
| 1. one cap shared by the diagnosticians' and the decider's offsets | shared | a decider that agrees with belief cancels part of the diagnosticians' push (report, disagreement 1) |
| 2. candidates | combined: belief's top 3 + the diagnosticians' top 3 (`candidates: union`) | human instruction 2026-10-08 |
| 3. the filler cases RCA-09/10/15 | offered, never pushed (`guard_flat: true`) | proven never worse on these episodes; under hybrid on 21 dev episodes: 22 ticks better, 0 worse (mock) |
| 4. run arm A twice (noise) | yes | the pass rule needs the run-to-run difference; v3's replies change in 13-21% of calls between runs |
| 5. the decider on `hybrid`'s weak / tied ticks | it does NOT change the top cause there (the model's pick leads, as in v3) | using it as a tie-breaker could address v3's C-episode losses (the RCA-14 / RCA-18 look-alike tie), but it changes v3's own rule: a decision and new code |
| 6. decider placement | HTP0 if step 5 passed there, else board CPU | latency, and what shares the NPU with the Llama lane |

## 10. Step 6: the measurement (dev quick set; several hours)

Order A1, B, A2, so slow drift (heat, the board) does not favour one arm. `main`'s runner (`scripts/benchmark.sh`,
`BENCHMARK_GUIDE.md`) restarts the two lanes before every episode and waits for the chip to cool; it restarts only
`llama-server`, never `bev-decide`, so start `bev-decide` once (step 5) and leave it up through all three arms (arm A
never calls it). This runner has **no** preflight or keep-checks, so the decider check below is yours to do.
```bash
unset PYTHONPATH
.venv/bin/python -m bench.board start bev bev-decider-0.4B-backbone-Q8_0.gguf     # if not already up
curl -s http://localhost:8082/health                     # {"status":"ok"}
Q=(dev_A01_fcv_seize dev_A02_fcv_seize_fast dev_B01_tube_leak dev_B02_tube_leak_fast dev_C01_wet_coal
   dev_C02_feeder_trip dev_D01_high_cv_coal dev_D03_high_cv_severe dev_N01_normal dev_N02_normal)

scripts/benchmark.sh bev3_armA_run1 "${Q[@]}" --overlay configs/v3.yaml        # arm A, run 1: v3, no decider
scripts/benchmark.sh bev3_armB      "${Q[@]}" --overlay configs/bev3.yaml      # arm B: v3 + the decider
scripts/benchmark.sh bev3_armA_run2 "${Q[@]}" --overlay configs/v3.yaml        # arm A, run 2
```
Results go to `results/benchmarks/<name>/` (`RESULTS.md`, `test.json`, per episode `run.json.gz` / `summary.json` /
`log`). The same command resumes after a stop (an interrupted episode starts over); the runner refuses to mix settings
under one name. If the decider sits on HTP0, `bev-decide` and the Llama NPU lane share the NPU: watch for stalls.
On this branch a dropped board connection (`RemoteDisconnected`) stops the runner instead of failing the call (the fix
is on `multi-agent-fix`, not on `main`): rerun the same command to resume.

Compare the arms (the evaluator `run_demo.py` uses, pooled over the episodes of each folder), and check the decider:
```bash
.venv/bin/python - results/benchmarks/bev3_armA_run1 results/benchmarks/bev3_armB results/benchmarks/bev3_armA_run2 <<'PY'
import glob, gzip, json, sys
from bench.evaluator import aggregate, evaluate
def load(f):                       # a run, a list of runs, or {"runs": [...]}
    d = json.load(gzip.open(f))
    return d if isinstance(d, list) else d.get("runs", [d])
for arm in sys.argv[1:]:
    runs = [r for f in sorted(glob.glob(f"{arm}/*_multi.run.json.gz")) for r in load(f)]
    s = aggregate([evaluate(r) for r in runs])
    print(f"== {arm}  ({len(runs)} episodes)")
    print("  library group top-1", s["Q2_library"]["group_top1"], "| belief alone", s["Q2_library"]["belief_group"],
          "| held-out group top-1", s["Q2_heldout"]["group_top1"])
    for r in runs:
        d = r["multi"].get("decider")
        if d is not None:
            print(f"  {r['episode_id']:28} decider calls {d['calls']:4}  failed {d['failed']}  rejected {d['rejected']}")
PY
```
(Checked on the mock: both arms run through this runner and the snippet reads its files.)
**Arm B is valid only if every episode shows `failed 0`.** A failed call (server down, timeout) silently leaves the
episode without the decider, and this runner does not catch it. If any episode has failed > 0, move its files to an
`invalid/` subfolder, fix the cause, and rerun that episode. `rejected` > 0 is a result (the gate refused bev's
answer), not an error: report it.

Also confirm the replay reproduces every arm B run (the gate's decider records are complete):
```bash
.venv/bin/python - results/benchmarks/bev3_armB <<'PY'
import glob, gzip, json, sys
from bench.replay_multi import published, replay
for f in sorted(glob.glob(f"{sys.argv[1]}/*_multi.run.json.gz")):
    d = json.load(gzip.open(f)); r = d if "assessments" in d else (d.get("runs") or d)[0]
    print(r["episode_id"], "replay ok" if replay(r, "hybrid") == published(r) else "REPLAY DIFFERS")
PY
```

**Pass rule** (fixed before any board run, `reports/bev_decider.md`): arm B's library group top-1 must be above BOTH
arm A runs and above belief alone, each by more than |A1 - A2|. Held-out (family C, RCA-06) and every other metric
are reported, never used to decide. One pass on the quick set is not a claim about the reporting set.

## 11. Step 7: report and hand back

Append a section "Part C results on v3 (board, <date>)" to `reports/bev_decider.md`, in the project's report format
(Status / Verification / Numbers / Disagreements / Blocked / What I could not verify), with:
- step 2's four sizes and sha256s, and which Python ran the reference (venv-convert or a separate env);
- the three conformance summaries side by side (n, tokens identical, rank-1 agreement and every disagreement with its
  margin, max / median |dp|, shuffle drift, latency median, prompt tokens), plus memory and RSS with all three servers up;
- the startup-log lines proving placement (or the CPU fallback and why);
- arm A1, B, A2: library group top-1, belief alone, held-out, per-episode decider calls / failed / rejected, replay
  check, chip temperatures, wall time; the pass rule worked out with the actual numbers;
- for B against A: ticks helped / harmed, and how many of B's changed ticks were `hybrid` clear ticks (the decider
  cannot change a model-led top cause);
- every stop you hit, with log lines, and anything you could not verify.
Then:
```bash
git add reports/bev_decider.md reports/data/bev_reference.json reports/data/bev_conformance_*.json bench/board.py
git commit -m "bev-decider-3 Part C: board build, conformance and v3 quick-set measurement"
```
Do not push. Tell the human the report is committed and what the pass rule gave.

---

## Troubleshooting

| symptom | likely cause | what to do |
|---|---|---|
| `start bev` says "no recorded sha256" | step 4 values not written into `bench/board.py` | record them, rerun `tests/test_bev_board.py` |
| `start bev` says "board sha256 ... !=" | the push differs from the build | push again, compare again; never edit the recorded value to match the board |
| `/health` never answers (start waits 300 s) | `bev-decide` exited | `bench.board log bev`: missing lib (LD_LIBRARY_PATH), wrong head path, "model hidden size != head hidden_dim" (wrong GGUF) |
| `llama_decode (options) returned ...` or an error about sequence positions | llama.cpp rejected the shared-prompt plan | STOP and report the lines: this is the main unproven part |
| conformance exit 3 | tokenizer differs from bev's (Qwen2 pre-tokenizer) | STOP, report the first differing request (compare the two id lists) |
| `build_android.sh`: "lib... not found" | the pulled package has no lib/ or include/ | use the installed package the board was built from (step 4 note) |
| `convert_hf_to_gguf.py` error | the truncated 20-layer folder | STOP, send `logs/bev_convert_gguf.log` |
| the runner stops with `RemoteDisconnected` | board connection dropped (no fix on `main`) | check `adb devices`, rerun the same command (it resumes) |
| decider `failed` > 0 in arm B | bev-decide down or slow (timeout 120 s, `llm.llamaserver.timeout_s`) | move the episode to `invalid/`, check `log bev` and memory, rerun |
| Llama NPU lane slows or stalls with bev-decide up | two processes on HTP0 | report; the human decides between HTP0 sharing and the CPU fallback |

## Files you will touch or read

| path | role |
|---|---|
| `reports/bev_decider.md` | the report; append Part C here |
| `reports/multi_v3_results.md` | v3 on the board without the decider (the baseline story) |
| `device/bev_decide/build_gguf.sh`, `build_android.sh` | step 2, step 4 |
| `device/bev_decide/bev_decide.cpp`, `bev_core.hpp` | the server (read if it misbehaves; do not change without the human) |
| `bench/bev_convert.py` | the split (called by build_gguf.sh) |
| `bench/bev_conformance.py` | step 3 and step 5 |
| `bench/board.py` | `start bev` / `log bev` / `stop bev`; record the sha256 here |
| `configs/v3.yaml`, `configs/bev3.yaml` | arm A, arm B |
| `scripts/benchmark.sh`, `bench/benchmark.py`, `BENCHMARK_GUIDE.md` | the quick-set runs |
| `bench/replay_multi.py` | replays hybrid runs including the decider's offsets |
| `fieldmind/multi/agents/decider.py` (`offered`), `fieldmind/multi/agents/gate.py` (`fold_decider`, `_decider_offsets`, `apply_rule`) | the agent side |
| `fieldmind/multi/merge_rules.py` (`hybrid`, `decider_nudges`, `total_offsets`) | how the pick reaches the ranking |
