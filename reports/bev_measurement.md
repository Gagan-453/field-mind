# bev measurement plan (BEV_MEASUREMENT_PLAN.md) on the QIDK — report

## Status
PARTIAL — Part 1 (probe), Part 2A (memory), T1–T5 run on the board on 2026-10-20/21 (laptop time, 23:59–08:01). Part 2B (qprof) and
every Part 2C power route except the external meter are **not available on this board** (exact errors below). T6–T9
not started: the plan says they need Shubham's change or sign-off first. All plant data is synthetic. Energy stays
`null`: nothing on this board measures power.

Board `ab8f6592` (SM8650, build `qti/pineapple/pineapple:14/UKQ1.230917.001/eng.lnxbui.20230920.075750:userdebug/test-keys`).
Branch `bev-ideas` at the merge of `bebed22` (the plan). Raw files: `results/probe_20261020/`,
`results/board_probe_20261020.json`, `results/benchmarks/bevideas_*`, `reports/data/bev_reference.json`,
`reports/data/bev_conformance_*.json`.

## Headline findings

1. **bev-decide on the board does not compute what bev_decider computes (T3).** With identical token ids on all 24
   requests, the board's top choice equals the fp32 PyTorch reference on **8 of 24**; max |p_board − p_ref| 0.74,
   median 0.11. The same 8/24 with the 16-bit backbone on the board CPU, and NPU-Q8 vs CPU-16bit agree 24/24 with each
   other. So it is not NPU or Q8 drift: the port and the reference differ before quantization matters. Five NPU reps
   are bit-identical; option-order drift is ≤ 0.0035. Cause not located (see Blocked). Every board bev accuracy number
   (here and in the earlier bevideas runs) is a number for *this port*, not for bev-decider.
2. **No on-board power measurement exists** (Part 1/2C). No qprof, no power rails, `/sys/class/power_supply` denied,
   and the battery current that Perfetto can read does not respond to load: 5.45 mA idle, **5.25 mA with all 8 cores
   at 99%**, 5.26 mA idle after. Only an external meter is left.
3. **RSS misses most NPU memory (2A).** NPU llama-server: RSS 489 MB, DMA buffers 2,468 MB (RSS misses 83%).
   bev-decide on NPU: RSS 763 MB, DMA 1,140 MB. CPU lane: no DMA buffers, RSS is the whole footprint. The DMA sizes match
   the servers' own startup logs exactly (HTP0 model buffer 1911.90 MiB = 1020.5 + 891.4; KV 448.00 MiB = 448.0).
4. **T1: the three speed ideas together save more than their sum.** explain + clear_skip + verifier: wall
   1,350 s → 725–744 s over three reps (−45%), decode tokens per tick 10.68 → 2.07. Alone: explain −437 s, clear_skip
   −101 s, verifier **+55 s**; the sum −483 s, the combo −606 s. Library group top-1 0.759 → 0.775 (all 3 reps), but
   library top-1 0.646 → 0.609–0.611 (see Disagreements).
5. **T2: bev on the NPU does not slow Llama.** With bev moved to the CPU, the Llama diagnostician call got slower
   (1,224 → 1,338 ms mean), bev calls 694 → 2,103 ms, and the run took 65% longer. bev on the CPU keeps ~3 cores busy.
6. **T4: no thermal slowdown separable from noise.** Soak without cooling waits 1,503 s vs cooled baselines A2
   1,498 s and A3 1,372 s; peaks ~97 °C with or without the waits.

## Verification
| step | result |
|---|---|
| ran the module | probe, 5 conformance reps + 1 CPU rep, 9 benchmark tests of 10 episodes each, all `batch_end status=all episodes done`; `failed` = 0 for every bev idea call in every test |
| self-tests | `pytest tests/test_bev_ideas.py tests/test_bev_report.py tests/test_board_sampler.py`: 61 passed (383 s) before any board use |
| independent re-derivation | DMA buffer sizes (dmabuf_dump, kernel view) vs the servers' own allocation log lines: NPU model 1911.9 vs 1911.90 MiB, KV 448.0 vs 448.00 MiB, bev model 476.6 vs 476.58 MiB; relative difference < 0.01% |
| independent re-derivation | battery current as a power reading: if it measured board draw, an 8-core spin would raise it; measured 5.45 → 5.25 mA (no rise), CPU busy 0.99 checked from /proc/stat |
| mutation check | not applicable: no code in the repo was changed. The one tool I wrote that could be wrong in a silent way (the queue runner) was checked by a dummy 3-line `adb` queue (old runner ran 1 line, fixed runner ran 3) |

## Part 1 — probe (what this board has)
| check | result | meaning |
|---|---|---|
| `id` | `uid=2000(shell)` | not root |
| `getenforce` | Enforcing | |
| `ro.build.type`, `ro.debuggable` | userdebug, 1 | `adb root` would probably work; **not tried** (it changes the board's state; root adds no power sensor) |
| qprof | `/vendor/qprof: No such file or directory`; `qprof: inaccessible or not found` | no NPU-load measurement (2B) |
| IPowerStats | `Can't find service: android.hardware.power.stats.IPowerStats/default`; `dumpsys powerstats` prints nothing | no Perfetto power rails |
| `/sys/class/power_supply/*` | `Permission denied` on type, current_now, voltage_now | |
| tools | dmabuf_dump, simpleperf, perfetto (v34.0), procrank, showmap present | 2A works |
| Perfetto `android.power` | the plan's config is **rejected**: `Unexpected value 'BATTERY_COUNTER_VOLTAGE'` (not in Perfetto v34). With CURRENT, CHARGE, CAPACITY_PERCENT it records 41 battery samples / 10 s and 0 rail descriptors | |
| battery current vs load | idle 5.45 mA, 8-core load 5.25 mA, idle 5.26 mA (`power_loadtest30s_summary.txt`) | not a board power reading |
| `dumpsys battery` | AC/USB powered false, level 100, voltage 9019 mV | board looks DC-supplied outside the gauge |

## Part 2 — tools
- **2A memory**: works without root. Snapshots: bev only after load (00:09), all three after load (05:38) and idle
  (05:40), and every 60 s during the T5 runs. `results/probe_20261020/mem/`, summary script `mem_summary.py`.
  bev-decide's RSS grows with use (266 MB fresh, 763 MB after hours of serving); its DMA buffers do not (1,140 MB).
  Board MemTotal 11.6 GB, MemAvailable 3.8 GB with all three servers idle.
- **2B qprof**: not on the board. Installing it needs Windows + a Qualcomm account (plan). Not attempted.
  `GGML_HEXAGON_PROFILE`/`VERBOSE` not tried: the plan says to ask Shubham first.
- **2C power**: options 1–2 unavailable (above); option 3 (Snapdragon Profiler) is documented for a different chip and
  needs root + SELinux off, not tried. **Option 4 (external meter) is the only route left.**

## Part 3 — tests

### T1 — explain + clear_skip + verifier, three reps (COMPARE in `bevideas_C_combo_r3/` and, with the single arms, `bevideas_C_combo_r1/`)
| metric | A1 | combo r1 | r2 | r3 | A3 | \|A1 − A3\| |
|---|---|---|---|---|---|---|
| wall s | 1,350 | 744.1 | 729.1 | 725.2 | 1,372.1 | 22.1 |
| decode per tick | 10.68 | 2.07 | 2.08 | 2.06 | 10.70 | 0.02 |
| library group top-1 | 0.759 | 0.775 | 0.775 | 0.775 | 0.759 | 0 |
| library top-1 | 0.646 | 0.609 | 0.611 | 0.609 | 0.646 | 0 |
| held-out group top-1 | 0.451 | 0.549 | 0.549 | 0.549 | 0.471 | 0.02 |
| model invocation rate | 0.287 | 0.257 | 0.257 | 0.256 | 0.287 | 0 |

Do the savings add up (single arms are one run each, from 2026-10-19):

| arm | wall − A1 | decode/tick − A1 | group top-1 − A1 |
|---|---|---|---|
| B_explain | −437 s | −7.62 | +0.013 |
| B_skip | −101 s | −1.55 | +0.007 |
| B_verifier | +55 s | −0.72 | 0 |
| sum of the three | −483 s | −9.89 | |
| combo r1 | −606 s | −8.61 | +0.016 |

Wall time is super-additive; decode tokens are sub-additive (clear_skip and explain cut the same tokens). Why the wall
time saving exceeds the sum is **not explained** (not tested).

Keep rule of `BEV_IDEAS_FOR_BENCHMARKS.md` for a speed idea: decode per tick down (yes) and group top-1 not below
min(A1, A3) − |A1 − A3| = 0.759 (0.775: yes). The combo passes. Library top-1 (not in the rule) drops 0.037 with a
baseline spread of 0, and the drop is the same as B_explain's alone (−0.041).

### T2 — bev on the CPU (`bevideas_B_explain_bevcpu/COMPARE_bevideas_B_explain.md`)
| | B_explain (bev NPU, 2026-10-19) | bev CPU | |
|---|---|---|---|
| wall s | 913 | 1,505.9 | +65% |
| bev call ms mean / p95 | 694 / 958 | 2,103 / 3,528 | |
| diagnostician (Llama, NPU) ms mean | 1,224 | 1,338 | slower, not faster |
| verifier (Gemma, CPU) ms mean | 1,909 | 2,120 | |
| bev process cores busy | 0.14 | 2.97 | |
| board CPU busy % | 24.4 | 47.8 | |
| library group top-1 | 0.772 | 0.774 | |

Answer to the plan's question: there is no sign that sharing the NPU slows Llama; taking bev off the NPU made Llama
slower, consistent with CPU contention (not tested further). One run each.

### T3 — conformance (`reports/data/bev_conformance_npu-q8-rep{1..5}.json`, `bev_conformance_cpu-16bit.json`)
| run | tokens identical | rank-1 agree | max \|Δp\| | median \|Δp\| | shuffle max \|Δp\| | latency median ms |
|---|---|---|---|---|---|---|
| npu-q8 rep1–5 | 24/24 | 8/24 (each) | 0.740 | 0.114 | 0.0035 | 296–314 |
| cpu-16bit | 24/24 | 8/24 | 0.745 | 0.126 | 0.0072 | 11,311 |

All 5 NPU reps give identical disagreement lists. In the 16 disagreements the reference picks RCA-13 nine times; the
board's picks are spread over 8 cases. Exit code 4 every time (a finding, per the plan).

### T4 — thermal soak (`bevideas_A_soak/COMPARE_bevideas_A3.md`)
| | A2 (cooled) | A3 (cooled) | soak (no waits) |
|---|---|---|---|
| wall s | 1,498.3 | 1,372.1 | 1,502.9 |
| cpu / npu max °C | – | 96.1 / 96.9 | 96.9 / 97.7 |
| episode start temperature | waits to base + margin | | 37.8 → 64.8 °C |

Per episode, the soak is −4.5 to +25.5 s from the mean of A2 and A3; A2 and A3 differ by up to 33 s on the same
episode. No slowdown separable from run-to-run noise. Library accuracy identical.

### T5 — measurement runs (`bevideas_A_meas`, `bevideas_B_explain_meas`; `bevideas_B_explain_meas/COMPARE_bevideas_A3.md`)
Memory snapshots (2A) every 60 s during both runs, 205 process snapshots in all (`results/probe_20261020/mem_summary.txt`).
No qprof (2B) and no power (2C): neither exists on this board. Snapshots catch the llama lanes only while an episode
runs (the runner restarts them per episode); bev-decide stays up throughout.

| moment | lane | snapshots | RSS MB | DMA MB | RSS + DMA max MB |
|---|---|---|---|---|---|
| after load / idle | npu | 1 / 1 | 488.7 | 2,468.4 | 2,957.2 |
| during A_meas | npu | 28 | 451.6–537.8 | 2,468.4 | 3,006.2 |
| during B_explain_meas | npu | 16 | 509.1–533.5 | 2,468.4 | 3,001.9 |
| after load / idle | cpu | 1 / 1 | 1,475.0 | 0 | 1,475.0 |
| during A_meas / B_explain_meas | cpu | 27 / 16 | up to 1,544.3 / 1,553.2 | 0 | 1,553.2 |
| after load / idle | bev | 1 / 1 | 763.2 | 1,139.8 | 1,903.0 |
| during A_meas (bev unused) | bev | 63 | 757.4–763.2 | 1,139.8 | 1,903.0 |
| during B_explain_meas | bev | 47 | 757.4–963.4 | 1,139.8 | 2,103.2 |

(cpu RSS min 19.3 MB in A_meas is a snapshot taken while the lane was still loading.) The sampler's peak RSS agrees
with the snapshots (npu 541.5 MB, bev 963.4 MB), so the sampler is right about RSS and blind to the DMA buffers.
Peak footprint of the three servers together ≈ 6.66 GB of the board's 11.6 GB.

Timing cost of measuring: A_meas 1,358 s vs A3 1,372 s the same night (−14 s; A2–A3 spread 126 s): not
detectable. B_explain_meas 872.8 s (B_explain 913 s, 2026-10-19). Accuracy as the unmeasured arms (group top-1 0.759
and 0.774).

## Direction checks
| claim | expected | measured | OK/FAIL |
|---|---|---|---|
| battery current rises with CPU load, if it measures board draw | up | 5.45 → 5.25 mA | FAIL → it does not measure board draw |
| RSS ≤ true footprint of an NPU process | RSS < RSS + DMA | 489 < 2,957 MB | OK |
| measuring (snapshots every 60 s) slows the run | up or no change | A_meas 1,358 s vs A3 1,372 s | OK (no change detectable) |
| bev on CPU makes bev calls slower | up | 694 → 2,103 ms | OK |
| fewer decode tokens → less wall time (T1) | down | 10.68 → 2.07 tok/tick, 1,350 → 725–744 s | OK |

## Constants introduced
None. Cooling gaps between tests (600 s; 900 s after the soak, as the plan says) are procedure, not model constants.

## Numbers that changed
None in the code or configs. New measured numbers are above.

## Disagreements recorded, not resolved
1. **Board bev-decide vs bev_decider reference: 8/24 top-1** (T3). Both sides recorded; nothing changed.
2. **Library top-1 falls with `explain` (0.646 → 0.605–0.611) while group top-1 rises (0.759 → 0.772–0.775)**,
   in all 5 runs with explain on (B_explain, B_explain_bevcpu, combo r1–r3), with a baseline spread of 0. Not covered by the pre-registered keep rule. Cause
   not tested.
3. **Laptop stage times are not comparable across days.** Hard-path stages tonight are ~40% lower than on 2026-10-19
   for every arm including the A3 baseline (sensor mean 0.54 ms tonight vs 0.93–0.98 ms on 10-19). The laptop's state
   changed (cause unknown); compare stage times only within one session.
4. **A2 vs A3 wall time differ by 126 s** (A1 vs A2 by 22 s). Baseline wall-time noise is larger than one pair
   suggested; same-session comparisons are safer.

## Decisions taken
1. **T2 used the runner's `--bev-device cpu`** instead of the plan's manual `stop bev` / `start bev ... cpu`. With the
   manual route the runner (default `--bev-device npu`) would have refused the CPU-placed bev-decide, and the device
   would not be in the test's params.
2. **The T3 reference was built here** (it did not exist): `bev-decider==0.2.1` installed with `--target` into a
   scratch folder (not into `~/fieldmind-build/venv-convert`, which stays unchanged), torch 2.11.0+cpu, transformers
   4.57.6; weights sha256 `e28f9f5a…4282` = `bench/bev_convert.EXPECTED_SHA256`. Committed requests file unchanged.
3. **Ran the plan's 16-bit-on-CPU conformance once** (label `cpu-16bit`) to separate quantization drift from a port
   difference, as `bench/bev_conformance.py` describes.
4. **`adb root` not used.** Conservative: it restarts adbd and changes the conditions of every later run, and the probe
   shows no power sensor root would unlock.
5. **Test order changed** because of a bug in my queue script (`adb` inside the loop read the remaining command list
   from stdin, so the queue stopped after combo r1). Actual order: combo r1, T2, combo r2, combo r3, A3, soak, T5.
   Every test restarts its lanes; bev-decide was restarted on the NPU (sha256 and placement checked by the runner)
   before combo r2.
6. **Perfetto config**: dropped `BATTERY_COUNTER_VOLTAGE` (rejected by Perfetto v34), added CHARGE and
   CAPACITY_PERCENT.

## Blocked / needs a decision
1. **T3 port difference.** Is bev-decide's head/pooling (or the reference call in `bench/bev_conformance.reference`)
   wrong? Options: (a) Shubham compares bev-decide's per-request intermediate values (backbone hidden state at the
   read positions, head logits) with bev_decider's for one disagreeing request, e.g. `dev_A01_fcv_seize@t79`
   (reference RCA-13, margin 0.81; board RCA-01); (b) treat bev's board answers as a different model and keep using
   them for timing only. Until resolved, board bev accuracy numbers should not be reported as bev-decider's.
2. **Power**: needs an external USB-C/DC meter with logging (plan option 4), or root + qprof via a Windows install.
3. **T6–T9**: need Shubham's script, sampler period option, labelled sheet, and question sign-off (plan).

## What I could not verify
- Whether the board's DC supply has any readable sensor (e.g. via root-only sysfs or the PMIC). Not tried without root.
- Why the combo's wall-time saving exceeds the sum of the single ideas (single arms are one run each, from another day).
- Why the Llama call is slower with bev on the CPU (CPU contention is the likely route, not tested).
- Whether the T3 difference is in the board port or in the reference script: both sides are this repo's code.
