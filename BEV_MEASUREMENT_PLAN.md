# bev: next tests, and how to measure memory, NPU and power on the board

Branch: **`bev-ideas`** (same as before). This follows `BEV_IDEAS_FOR_BENCHMARKS.md`; the same board rules apply:
`unset PYTHONPATH`, sha256 check after every push, chip temperature logged, one thing on the board at a time, and
the dev episodes only (`dev_*`) for anything we decide on. All plant data is synthetic.

## Why this exists

The first bev-ideas runs answered "does each idea save time, and does accuracy hold". Three things are still missing:

1. **Memory.** The sampler records RSS per server, but NPU weights and the KV cache live in shared DMA buffers that RSS
   may not count fully. We have not checked this.
2. **NPU use.** We only have the NPU lane's call time, not how busy the NPU actually was.
3. **Power and energy.** The board gave no power readings, so energy per correct diagnosis (the project's headline
   metric) is still empty. It stays empty until something actually measures it. Never estimate it.

Part 1 finds out which measuring tools this board has (about 5 minutes). Part 2 explains each tool. Part 3 is the list
of new bev tests, in priority order.

---

## Part 1. The 5-minute probe (do this first, send me everything it prints)

The board's servers do not need to be running for this.

```bash
unset PYTHONPATH
mkdir -p results/probe_$(date +%Y%m%d) && cd results/probe_$(date +%Y%m%d)

adb shell id                                              > id.txt              # root or not
adb shell getprop ro.build.fingerprint                    > build.txt
adb shell 'ls -la /vendor/qprof /vendor/bin/qprof /vendor/qprof/libs 2>&1' > qprof_files.txt
adb shell 'export LD_LIBRARY_PATH=/vendor/qprof/libs; qprof --capabilities 2>&1' > qprof_caps.txt
adb shell 'dumpsys android.hardware.power.stats.IPowerStats/default 2>&1 | head -80' > powerstats.txt
adb shell 'ls /sys/class/power_supply/; for p in /sys/class/power_supply/*; do echo == $p; cat $p/type $p/current_now $p/voltage_now 2>&1; done' > power_supply.txt
adb shell 'which dmabuf_dump simpleperf perfetto procrank showmap 2>&1' > tools.txt
adb shell getenforce                                      > selinux.txt
cd ../..
.venv/bin/python -m bench.board_sampler probe | tee results/board_probe_$(date +%Y%m%d).json
```

Zip the `results/probe_<date>/` folder and `results/board_probe_<date>.json` and send them. What each file decides:

| file | if it shows... | then |
|---|---|---|
| `qprof_files.txt`, `qprof_caps.txt` | `qprof` exists and lists `nsp-dsp-metrics` | we can measure NPU load (Part 2B) |
| `qprof_caps.txt` | lists `apps-proc-battery-metrics` | possible device power reading (Part 2C) |
| `powerstats.txt` | a list of power rails / channels | Perfetto power rails work (Part 2C) |
| `power_supply.txt` | real numbers for `current_now` | battery or USB current is readable |
| `tools.txt` | `dmabuf_dump` found | per-process NPU buffer memory (Part 2A) |
| `id.txt`, `selinux.txt` | `uid=0`, `Permissive` | root-only tools may work |

If none of the power options work, the only way left is an external power meter (Part 2C, option 4).

---

## Part 2. The measuring tools

### 2A. Memory per process

Run these for each of the three servers (NPU llama-server :8080, CPU llama-server :8081, bev-decide :8082), at three
moments: **right after the model has loaded**, **while idle**, and **during a benchmark run** (take one or two
snapshots in the middle).

```bash
adb shell 'ps -A -o PID,RSS,NAME | grep -E "llama-server|bev-decide"'      # find the pids
PID=<pid>
adb shell dumpsys meminfo $PID          > meminfo_$PID.txt      # PSS: shared memory split fairly between processes
adb shell cat /proc/$PID/smaps_rollup   > smaps_$PID.txt        # the same breakdown, kernel view
adb shell dmabuf_dump $PID              > dmabuf_$PID.txt       # DMA buffers held, where NPU memory lives
adb shell dmabuf_dump                   > dmabuf_all.txt        # all processes (can be long)
```

Name each file with the moment (for example `after_load_`, `idle_`, `during_`) and the laptop time. Never use board
time: the board's clock is wrong. **The question is whether RSS (what the sampler records) misses the DMA buffers.**
Send all the files; I will compare them.

### 2B. NPU use: Qualcomm Profiler (`qprof`)

Qualcomm Profiler replaces the old sysMonApp. Its HTP usage guide lists **Android SM8650** (our chip) as supported. It
can record NPU load, NPU clocks, HMX/HVX use, memory per process, DDR bandwidth, thermal and battery data.

**If `qprof_files.txt` shows it is on the board:**

```bash
adb shell
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/vendor/qprof/libs
export QMONITOR_BACKEND_LIB_PATH=/vendor/qprof/backends
export QMONITOR_FRONTEND_LIB_PATH=/vendor/qprof/libs
qprof --capabilities                              # what this board can record
qprof -sm getstate --q6 npu0                      # one snapshot: NPU clock, HMX clock, power state
# a 60 s capture, run while a benchmark episode is going:
qprof --profile --profile-type async \
      --capabilities-list profiler:nsp-dsp-metrics profiler:apps-proc-process-mem-metrics \
      --profile-time 60 --sampling-rate 100 --result-format csv --summary
```

Results land in `/data/shared/QualcommProfiler/profilingresults/` on the board: `adb pull` that folder. If a
capability name differs on our board, use the name `qprof --capabilities` prints.

**If it is not on the board:** for SM8750 and older chips, Qualcomm installs the board-side files from a **Windows**
PC with Qualcomm Package Manager (`qpm-cli --install Qualcomm_Profiler`, then run `InstallerLA.exe` from
`C:\Program Files (x86)\Qualcomm\Shared\QualcommProfiler\API\target-la\`). This needs a Qualcomm account and a Windows
machine. A Mac cannot do it. Tell me if you have access to Windows before trying.

**Note:** every example in Qualcomm's guide runs from a root shell. It may not work without root; `id.txt` tells us.

**Also available, for short diagnostic runs only** (it slows things down, so never use it in a timed arm): llama.cpp's
own NPU counters. Add these to the NPU lane's start command for one short run:
- `GGML_HEXAGON_PROFILE=1`: time and cycles of each operation on the NPU;
- `GGML_HEXAGON_VERBOSE=1`: which operations run on the NPU.

Ask me first, because the lane start command is in `bench/board.py`.

### 2C. Power

**Nothing gives power per process.** What exists is power for the whole device or per power rail. Per-call energy is
then worked out by subtracting an idle baseline. So every power run needs **two recordings**: 2 minutes with all servers
loaded but idle, then the benchmark itself.

Options, best first. Which ones work depends on Part 1.

1. **Qualcomm Profiler**, if `qprof --capabilities` lists battery or power metrics: same command as 2B, with that
   capability added.
2. **Perfetto power rails**, if `powerstats.txt` lists rails. Save this as `power.pbtx`:
   ```
   duration_ms: 120000
   buffers: { size_kb: 65536 }
   data_sources: { config { name: "android.power"
     android_power_config { battery_poll_ms: 250 collect_power_rails: true
       battery_counters: BATTERY_COUNTER_CURRENT battery_counters: BATTERY_COUNTER_VOLTAGE } } }
   ```
   ```bash
   adb push power.pbtx /data/local/tmp/power.pbtx
   adb shell 'cat /data/local/tmp/power.pbtx | perfetto --txt -c - -o /data/misc/perfetto-traces/power.pftrace'
   adb pull /data/misc/perfetto-traces/power.pftrace
   ```
   Open the file at ui.perfetto.dev to check that rails show up. Then send it to me.
3. **Snapdragon Profiler "Power Profiling"** (QIDK tools page). Qualcomm documents it for the Snapdragon 8 Elite Gen 5
   (rooted, SELinux off), not our chip. Try it only if 1 and 2 fail.
4. **An external USB-C or DC power meter** between the supply and the board. This always works. Record the meter's
   readings with laptop timestamps (a meter that logs to a file is best), and note the meter model.

Whatever is used, the energy numbers stay `null` in our reports until a real reading exists.

---

## Part 3. New bev tests (in this order)

Use the same quick set as before:
```bash
Q=(dev_A01_fcv_seize dev_A02_fcv_seize_fast dev_B01_tube_leak dev_B02_tube_leak_fast dev_C01_wet_coal
   dev_C02_feeder_trip dev_D01_high_cv_coal dev_D03_high_cv_severe dev_N01_normal dev_N02_normal)
```
Every test needs a new name; never reuse a name with different settings.

### Ready to run now

**T1. Explain + clear_skip + verifier together, three times.** Do the savings add up? Three runs show how much the
result moves between runs, instead of trusting one run.
```bash
for r in 1 2 3; do
  scripts/benchmark.sh bevideas_C_combo_r$r "${Q[@]}" --overlay configs/bev_ideas.yaml \
    --bev "explain=on,clear_skip=on,verifier=on"
done
scripts/benchmark.sh bevideas_A3 "${Q[@]}" --overlay configs/bev_ideas.yaml       # one more baseline
.venv/bin/python -m bench.bev_report bevideas_A1 bevideas_C_combo_r1 bevideas_C_combo_r2 bevideas_C_combo_r3 --a2 bevideas_A3
```

**T2. bev on the CPU instead of the NPU.** Does bev slow the Llama lane down when they share the NPU? bev-decide starts
on the NPU by default.
```bash
.venv/bin/python -m bench.board stop bev
.venv/bin/python -m bench.board start bev bev-decider-0.4B-backbone-Q8_0.gguf cpu
curl -s http://localhost:8082/health
scripts/benchmark.sh bevideas_B_explain_bevcpu "${Q[@]}" --overlay configs/bev_ideas.yaml --bev "explain=on"
.venv/bin/python -m bench.board stop bev
.venv/bin/python -m bench.board start bev bev-decider-0.4B-backbone-Q8_0.gguf      # back to the NPU
.venv/bin/python -m bench.bev_report bevideas_B_explain bevideas_B_explain_bevcpu
```

**T3. Option order and repeat consistency of bev on the board.** `bench/bev_conformance.py` sends real dev requests to
bev-decide twice: as they are, and with the options reversed. Llama gives a different reply to the same prompt 16% of
the time. If bev never changes its answer, that is a result in itself. If you already have
`reports/data/bev_reference.json` from the Part C conformance check, skip the first command.
```bash
# only if bev_reference.json is missing (needs torch; see the top of bench/bev_conformance.py)
<venv-convert>/bin/python -m bench.bev_conformance reference <bev-decider-0.4B dir> \
    --requests reports/data/bev_requests.json --out reports/data/bev_reference.json
for r in 1 2 3 4 5; do
  .venv/bin/python -m bench.bev_conformance compare http://localhost:8082 \
    --reference reports/data/bev_reference.json --label npu-q8-rep$r \
    --out reports/data/bev_conformance_npu-q8-rep$r.json
done
```
Exit code 4 means some answers disagree with the reference. That is a finding to report, not a failure to fix.

**T4. Thermal soak.** Does the chip at about 97 °C slow the later episodes? Run the baseline once with no cooling
waits.
```bash
scripts/benchmark.sh bevideas_A_soak "${Q[@]}" --overlay configs/bev_ideas.yaml --cool-max 0
```
Leave at least 15 minutes of cooling before the next test.

**T5. The measurement runs from Part 2.** Repeat one baseline arm and the `explain` arm with memory snapshots (2A),
a qprof capture (2B) and power (2C), using whatever the probe shows works. Name them `bevideas_A_meas` and
`bevideas_B_explain_meas`. Keep these separate from the timed arms, because the measuring tools themselves use CPU.

### Needs a small change first (tell me when you get here, I will add it)

- **T6. Cost of a bev request by size.** Vary 1/2/4/8 questions and 2/4/8 options and read bev's own timing. This
  decides whether to put several questions in one request. Needs a small script.
- **T7. Sampler cost.** Sample every 1 s, every 5 s, and not at all. The sampler uses about 0.76 of a core. Needs a
  period option in the sampler.
- **T8. Verifier against the true answer.** bev and Gemma agree only 47% of the time, but we do not know which is
  right. Needs about 100 claims labelled by hand from the dev logs. I will prepare the sheet.
- **T9. Reworded questions for `notes` and `actions`.** These two ideas failed; was it the wording or the idea?
  New wordings need Shubham's sign-off first; then shadow runs only.

---

## What to send back

1. The probe folder and `board_probe_<date>.json` (Part 1). **Send these first, before running anything else**, so
   we know which tools work.
2. For each test in Part 3: the `results/benchmarks/bevideas_*` folder (including `temps.jsonl`) and the `COMPARE_*`
   files.
3. T3: the five `bev_conformance_npu-q8-rep*.json` files.
4. Any memory, qprof, Perfetto or power-meter files, with the laptop time each started.
5. Anything that failed or looked odd, as it was. A tool that does not work on our board is a result too: write down
   the exact error.

## Rules (same as always)

- Do not change any threshold or setting to make a number look better.
- Decide nothing on the `ep_*` reporting episodes.
- No energy number without a real reading.
- Stage times are laptop times. Only model calls run on the board.
- If bev-decide fails any call (the `failed` column in the COMPARE file is not 0), rerun that test under a new name.

## Sources

- QIDK power profiling page: https://qualcomm.github.io/qidk/release-notes/tools.html
- QIDK overview: https://qualcomm.github.io/qidk/release-notes/overview.html
- Qualcomm Profiler CLI: https://docs.qualcomm.com/doc/80-54323-2/topic/command-line-interface.html
- Qualcomm Profiler DSP profiling: https://docs.qualcomm.com/doc/80-54323-2/topic/dsp-profiling.html
- Qualcomm Profiler for HTP usage (lists SM8650): https://docs.qualcomm.com/doc/KBA-260416042116/KBA-260416042116_REV_2_CDSPKBA_Qualcomm_Profiler_for_HTP_Usage.pdf
- NPU monitoring with libqcperf (Qualcomm Linux only, not Android): https://dragonwingdocs.qualcomm.com/tutorials/npu-monitoring
- Perfetto power rails and battery counters: https://perfetto.dev/docs/data-sources/battery-counters
- llama.cpp Snapdragon/Hexagon backend options: https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/snapdragon/README.md
