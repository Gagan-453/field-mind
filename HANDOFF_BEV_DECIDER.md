# Handoff: put bev-decider on the QIDK (Part C)

For Claude Code on the **QIDK laptop**, in the FieldMind repo, branch `bev-decider`. Everything that can be done
without the board is built, tested and committed (Part A). This file is the board part: build, push, prove the port
is correct, then measure. Follow it in order. Do not skip a check because the next step looks like it would work.

Read first, in this order: `CLAUDE.md` (project rules: they apply to every step here), `reports/bev_decider.md`
(what was built, what is verified, what is not, open decisions).

---

## 1. What this is, in five lines

- **bev-decider-0.4B** (huggingface.co/avbiswas/bev-decider-0.4B, CC-BY-NC) is a "System One" decision model: the
  first 20 layers of Qwen3-0.6B plus a small decision head. Given a state and a few options it returns one
  probability per option in a single forward pass, no text generated, and the option order cannot change the answer.
- In FieldMind it is a **third model agent, the decider**: whenever its evidence changes, it is shown the tick's facts
  and the combined candidates (belief's top 3 + the Llama diagnosticians' top 3 of that tick, each once: 3 to 6
  cases), and picks one. Its push never goes to the all-FLAT filler cases RCA-09/10/15 (`guard_flat`). Its pick enters the published ranking only through `nudge`, as a capped
  offset (+0.35 / +0.175, the diagnosticians' and the decider's offsets summed and capped at 1.2 per case per episode).
  It never writes belief and never has the last word (the gate checks every answer).
- On the board it runs as **`bev-decide`**, a small C++ server built from the SAME llama.cpp as `llama-server`
  (b11371, commit 99b95488), on **port 8082**, beside the two Llama lanes (8080 NPU, 8081 CPU).
- **No new libraries go on the board.** Three new files only: the `bev-decide` binary, one GGUF, the head
  (`bev_head.bin` + `bev_head.json`). It reuses `/data/local/tmp/llm/llama.cpp/lib`.
- Config: `configs/bev.yaml` (= `configs/accuracy.yaml` + `merge_rule: nudge` + the decider + the bev lane). The
  decider is OFF in `configs/base.yaml`; with it off, everything is byte-identical to before.

## 2. Rules for this session

1. Run every command from the repo root, **in bash** (the scripts use bash arrays; zsh does not split words the same
   way). `unset PYTHONPATH` first (this laptop exports the QAIRT SDK's python folder).
2. **Dev episodes only** (`data/episodes_dev`). The 30 reporting episodes are not run in this work, except once at
   the very end if the pass rule in step 6 passes, and only if the human says so.
3. Never push. Commit locally with "bev-decider" in the message.
4. Never delete data. To redo an episode, move its files into an `invalid/` subfolder.
5. Log chip temperature before and after every run; the batch scripts do it for you.
6. **Stop and report** (do not work around) when: a sha256 differs between laptop and board; `build_gguf.sh` or
   `build_android.sh` prints `STOP`; the conformance token check fails (exit 3); `bev-decide` will not start or
   crashes; a llama.cpp error mentions sequences, positions, the KV cache or memory; any decider call fails during a
   measurement run. Say what you saw, with the log lines.
7. No accuracy claim from anything here until step 6's pass rule is evaluated. Mock-backend numbers are never
   bev-decider results.

---

## 3. Step 0: preconditions (about 5 minutes)

```bash
unset PYTHONPATH
git fetch origin && git checkout bev-decider && git log --oneline -1      # bev-decider commits on top of 8acbc13
export BUILD=${BUILD:-$HOME/fieldmind-build}
git -C "$BUILD/llama.cpp" rev-parse HEAD                                  # must start 99b95488
ls "$BUILD/build-host/bin/llama-quantize" "$BUILD/venv-convert/bin/python"
adb devices                                                               # exactly one device
adb shell "cd /data/local/tmp/llm/llama.cpp && LD_LIBRARY_PATH=/data/local/tmp/llm/llama.cpp/lib ./bin/llama-server --version"
                                                                          # must print commit 99b95488c
ls data/episodes_dev | wc -l                                              # 36; if missing:
#   .venv/bin/python -m data.generator.episode_build --set dev
.venv/bin/python -m pytest -q tests/test_bev_convert.py tests/test_bev_core.py tests/test_bev_backend.py \
    tests/test_decider.py tests/test_bev_conformance.py tests/test_bev_board.py      # 77 passed
BEV_LLAMA_SRC="$BUILD/llama.cpp" .venv/bin/python -m pytest -q tests/test_bev_manifest.py   # 1 passed
```

If the branch is not on `origin`, ask the human for it (it was committed locally on another machine).

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
every matrix is Q8_0, and prints size + sha256 of four files in `$BUILD/gguf/bev/`:
`backbone-16bit.gguf`, `bev-decider-0.4B-backbone-Q8_0.gguf`, `bev_head.bin`, `bev_head.json`. Keep that output.
Logs: `logs/bev_split.log`, `logs/bev_convert_gguf.log`, `logs/bev_quantize.log`, `logs/bev_gguf_types.log`.
If `convert_hf_to_gguf.py` fails, stop and report its log: it has not been run on this truncated model before.

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
`reports/data/bev_requests.json` is committed: 24 real decider requests, 3 from each dev quick-set fault episode.

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
git add bench/board.py && git commit -m "bev-decider: record the board build's sha256 (bev-decide, GGUFs, head)"
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
Then beside the Llama lanes (both lanes Llama 3.2 3B, as in `configs/accuracy.yaml`), with `bev-decide` still up:
```bash
# /board-up Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf   (or bench.board start npu / start cpu)
.venv/bin/python -m bench.bev_conformance compare http://localhost:8082 \
    --reference reports/data/bev_reference.json --label htp0-q8-with-lanes \
    --out reports/data/bev_conformance_htp0-q8-with-lanes.json; echo "exit $?"
.venv/bin/python -m bench.board speed http://localhost:8080                     # the Llama NPU lane still answers
adb shell cat /proc/meminfo | head -3
adb shell "ps -A -o RSS,NAME | grep -E 'bev-decide|llama-server'"
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
decider on the board CPU instead (`start bev ... cpu`) is the planned fallback, but the human decides.

## 9. Before step 6: decisions the human must confirm

Ask the human (Shubham) and write the answers in `reports/bev_decider.md` under "Decisions taken" before measuring.
If nobody answers, the defaults below are what is built; changing 1 or 2 needs a code change: do not make it, ask.

| decision | default (as built) | why it matters |
|---|---|---|
| 1. one cap shared by the diagnosticians' and the decider's offsets | shared | on the mock a decider agreeing with belief cancelled the diagnosticians' corrections (report, disagreement 1) |
| 2. offer the all-FLAT filler cases (RCA-09/10/15) | offer, but never push (`guard_flat: true`) | they drew Llama on 7 Oct; the guard is proven never worse on these episodes (report) |
| 3. run arm A twice (noise) | yes, about 1 h of board time each (estimate) | the pass rule needs the run-to-run difference |
| 4. decider placement | HTP0 if step 5 passed there, else board CPU | changes latency and what shares the NPU |

## 10. Step 6: the measurement (dev quick set; several hours)

Order A1, B, A2, so slow drift (heat, the board) does not favour one arm. `bev-decide` can stay up through all three
(arm A never calls it; the batch script restarts only `llama-server` between episodes).
```bash
unset PYTHONPATH
L=Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf
Q=(dev_A01_fcv_seize dev_A02_fcv_seize_fast dev_B01_tube_leak dev_B02_tube_leak_fast dev_C01_wet_coal
   dev_C02_feeder_trip dev_D01_high_cv_coal dev_D03_high_cv_severe dev_N01_normal dev_N02_normal)

# arm A, run 1: accuracy.yaml + nudge, no decider
OVERLAY=configs/accuracy.yaml MERGE_RULE=nudge NPU_MODEL=$L CPU_MODEL=$L EPISODES_DIR=data/episodes_dev \
    OUT=results/bev/armA_run1 LOG_PROMPTS=1 scripts/benchmark_multi_lockstep_all.sh "${Q[@]}"

# arm B: bev.yaml (the decider on). bev-decide must answer for the whole batch
curl -s http://localhost:8082/health                     # {"status":"ok"}
OVERLAY=configs/bev.yaml NPU_MODEL=$L CPU_MODEL=$L EPISODES_DIR=data/episodes_dev \
    OUT=results/bev/armB LOG_PROMPTS=1 scripts/benchmark_multi_lockstep_all.sh "${Q[@]}"

# arm A, run 2
OVERLAY=configs/accuracy.yaml MERGE_RULE=nudge NPU_MODEL=$L CPU_MODEL=$L EPISODES_DIR=data/episodes_dev \
    OUT=results/bev/armA_run2 LOG_PROMPTS=1 scripts/benchmark_multi_lockstep_all.sh "${Q[@]}"
```
Each command resumes where it stopped if run again. Live view in a second terminal:
`.venv/bin/python bench/stage_monitor_multi.py`. If the decider sits on HTP0, `bev-decide` and the Llama NPU lane
share the NPU: watch for stalls and report them.

Compare the arms (the evaluator `run_demo.py` uses, pooled over the episodes of each folder):
```bash
.venv/bin/python - results/bev/armA_run1 results/bev/armB results/bev/armA_run2 <<'EOF'
import glob, gzip, json, sys
from bench.evaluator import aggregate, evaluate
for arm in sys.argv[1:]:
    runs = [r for f in sorted(glob.glob(f"{arm}/*_multi.run.json.gz")) for r in json.load(gzip.open(f))]
    s = aggregate([evaluate(r) for r in runs])
    print(f"== {arm}  ({len(runs)} episodes)")
    print("  library group top-1", s["Q2_library"]["group_top1"], "| belief alone", s["Q2_library"]["belief_group"],
          "| held-out group top-1", s["Q2_heldout"]["group_top1"])
    for r in runs:
        d = r["multi"].get("decider")
        if d is not None:
            print(f"  {r['episode_id']:28} decider calls {d['calls']:4}  failed {d['failed']}  rejected {d['rejected']}")
EOF
```
**Arm B is valid only if every episode shows `failed 0`.** A failed call (server down, timeout) silently leaves the
episode without the decider. If any episode has failed > 0, move its files to `results/bev/armB/invalid/`, fix the
cause, and rerun that episode. `rejected` > 0 is a result (the gate refused bev's answer), not an error: report it.

Pass rule (written before the run, `reports/bev_decider.md`): arm B's library group top-1 must be above BOTH arm A
runs and above belief alone, each by more than |A1 - A2|. Held-out (family C, RCA-06) is reported, never used to
decide. One pass on the quick set is not a claim about the reporting set.

## 11. Step 7: report and hand back

Append a section "Part C results (board, <date>)" to `reports/bev_decider.md`, in the project's report format
(Status / Verification / Numbers / Disagreements / Blocked / What I could not verify), with:
- step 2's four sizes and sha256s, and which Python ran the reference (venv-convert or a separate env);
- the three conformance summaries side by side (n, tokens identical, rank-1 agreement and every disagreement with its
  margin, max / median |dp|, shuffle drift, latency median, prompt tokens), plus memory and RSS with all three servers up;
- the startup-log lines proving placement (or the CPU fallback and why);
- arm A1, B, A2: library group top-1, belief alone, held-out, per-episode decider calls / failed / rejected, chip
  temperatures, wall time; the pass rule worked out with the actual numbers;
- every stop you hit, with log lines, and anything you could not verify.
Then:
```bash
git add reports/bev_decider.md reports/data/bev_reference.json reports/data/bev_conformance_*.json bench/board.py
git commit -m "bev-decider Part C: board build, conformance and quick-set measurement"
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
| decider `failed` > 0 in arm B | bev-decide down or slow (timeout 120 s, `llm.llamaserver.timeout_s`) | move the episode to `invalid/`, check `log bev` and memory, rerun |
| Llama NPU lane slows or stalls with bev-decide up | two processes on HTP0 | report; the human decides between HTP0 sharing and the CPU fallback |

## Files you will touch or read

| path | role |
|---|---|
| `reports/bev_decider.md` | Part A report; append Part C here |
| `device/bev_decide/build_gguf.sh`, `build_android.sh` | step 2, step 4 |
| `device/bev_decide/bev_decide.cpp`, `bev_core.hpp` | the server (read if it misbehaves; do not change without the human) |
| `bench/bev_convert.py` | the split (called by build_gguf.sh) |
| `bench/bev_conformance.py` | step 3 and step 5 |
| `bench/board.py` | `start bev` / `log bev` / `stop bev`; record the sha256 here |
| `configs/bev.yaml`, `configs/accuracy.yaml` | arm B, arm A |
| `scripts/benchmark_multi_lockstep_all.sh` | the quick-set runs |
| `fieldmind/multi/agents/decider.py`, `fieldmind/multi/agents/gate.py` (`fold_decider`, `apply_rule`) | the agent side |
