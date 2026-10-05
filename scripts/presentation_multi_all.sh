#!/usr/bin/env bash
# The presentation episodes on the MULTI-AGENT system, one after another, in
# real time, with a live per-tick display, each saved as soon as it finishes.
# Run from the repo root, in a real terminal (tmux, so a closed window does
# not stop it):
#
#     scripts/presentation_multi_all.sh                       # all six
#     scripts/presentation_multi_all.sh ep_A01_fcv_seize      # only these
#
# Setup = configs/fast.yaml: Llama 3.2 3B on the NPU lane (water and heat
# diagnosticians), Gemma 3 1B on the CPU lane (verifier, text reader). Both
# lanes are restarted fresh before every episode with the fixed flags
# (-c 4096 -np 1 -fit off --cache-ram 0 -lv 4, from bench.board).
#
# Answers are held to the grammars of fieldmind/multi/grammar.py (multi.grammar,
# on in configs/fast.yaml since 2026-10-05), so results go to a "grammar"
# folder and are never mixed with, or resumed over, the runs made before that.
#
# Every result file carries the suffix _multi (the single agent's carry _single), so a
# file copied out of its folder still says which agent made it.
# Per episode, in $OUT:
#   <ep>_multi.log            the live display, written as it is shown
#   <ep>_multi.ticks.jsonl    every tick's full assessment, appended as it is published
#   <ep>_multi.run.json.gz    every tick (written when the episode finishes)
#   <ep>_multi.summary.json   the evaluation
#   <ep>_multi.realtime.json  lanes, slowest calls, stale drops, tick lateness
#   <ep>_multi.lanes.txt      the lane startup lines that prove NPU / CPU placement
#   temps_multi.jsonl       chip temperature before and after
# An episode that already has <ep>_multi.summary.json is skipped, so the same command
# resumes after Ctrl-C (the interrupted episode starts over). The next episode
# waits until the chip is within 5 C of the reading taken at the start of this
# batch, for at most 900 s (the single-agent script's margin and limit).
#
# TICK_S=30 is the agent's own tick: the six episodes are 1,250 ticks, about
# 10.5 hours. Shorten it (TICK_S=15 scripts/...) only if <ep>_multi.realtime.json of
# a finished episode shows every slowest_submit_to_answer_s well under it.
# BACKEND=mock checks this script on the laptop without the board; mock output
# goes to its own folder and is never an agent result.
set -uo pipefail
cd "$(dirname "$0")/.."
unset PYTHONPATH
NPU_MODEL=Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf
CPU_MODEL=gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf
BACKEND=${BACKEND:-llamaserver}
TICK_S=${TICK_S:-30}
if [ "$BACKEND" = llamaserver ]; then
    OUT=${OUT:-results/presentation_benchmark/multi_agent_grammar_llama32-3b_gemma3-1b}
else
    OUT=${OUT:-results/presentation_mock_check}
fi
EPISODES=("$@")
[ ${#EPISODES[@]} -eq 0 ] && EPISODES=(ep_A01_fcv_seize ep_B01_tube_leak ep_C01_wet_coal
                                       ep_D01_high_cv_coal ep_E01_fouling_drift ep_N01_normal)
MARGIN_C=5
MAX_WAIT_S=900
on_board() { [ "$BACKEND" = llamaserver ]; }

temp() {   # prints the hottest of the CPU and NPU zones
    .venv/bin/python -m bench.board temp | .venv/bin/python -c \
        'import json,sys; d=json.load(sys.stdin); print(max(d["cpu_max_c"], d["npu_max_c"]))'
}
note() {   # note <episode> <when> <temp> [waited_s]
    printf '{"episode": "%s", "when": "%s", "t": "%s", "max_c": %s, "cool_wait_s": %s}\n' \
        "$1" "$2" "$(date +%Y-%m-%dT%H:%M:%S%z)" "$3" "${4:-null}" >> "$OUT/temps_multi.jsonl"
}
start_lanes() {   # start_lanes <episode>: both lanes fresh, placement checked from the logs
    local ep=$1 lane model off
    .venv/bin/python -m bench.board stop >/dev/null
    for lane in npu cpu; do
        model=$NPU_MODEL; [ "$lane" = cpu ] && model=$CPU_MODEL
        echo "starting the $lane lane ($model) ..."
        .venv/bin/python -m bench.board start "$lane" "$model" > "logs/presentation_multi_lane_$lane.json" \
            && grep -q '"ready_after_s": [0-9]' "logs/presentation_multi_lane_$lane.json" \
            || { echo "the $lane lane did not come up:"; cat "logs/presentation_multi_lane_$lane.json"; return 2; }
    done
    {
        echo "== npu ($NPU_MODEL)"
        .venv/bin/python -m bench.board log npu | grep -E "offload|HTP0 model buffer|n_ctx_slot"
        echo "== cpu ($CPU_MODEL)"
        .venv/bin/python -m bench.board log cpu | grep -E "offload|HTP0 model buffer|n_ctx_slot|n_threads ="
    } > "$OUT/${ep}_multi.lanes.txt"
    # NPU: a nonzero HTP0 buffer and every layer offloaded; CPU: no HTP0 buffer
    off=$(sed -n '/^== npu/,/^== cpu/s/.*offloaded \([0-9]*\)\/\([0-9]*\) layers.*/\1 \2/p' "$OUT/${ep}_multi.lanes.txt")
    if ! sed -n '/^== npu/,/^== cpu/p' "$OUT/${ep}_multi.lanes.txt" | grep -q "HTP0 model buffer size = *[1-9]" \
        || [ -z "$off" ] || [ "${off% *}" != "${off#* }" ] \
        || sed -n '/^== cpu/,$p' "$OUT/${ep}_multi.lanes.txt" | grep -q "HTP0 model buffer"; then
        echo "lane placement is not as expected (NPU fully offloaded, CPU with no HTP0 buffer):" >&2
        cat "$OUT/${ep}_multi.lanes.txt" >&2
        return 2
    fi
}

mkdir -p "$OUT" logs
if on_board; then
    if pgrep -f '[p]ython -m bench.campaign all' >/dev/null; then
        echo "the campaign is running: stop it first (one thing on the board at a time)" >&2
        exit 1
    fi
    .venv/bin/python -m bench.board stop >/dev/null
    base=$(temp) || { echo "cannot read the board temperature (is it plugged in?)" >&2; exit 2; }
    note batch start "$base"
    echo "batch start: chip at $base C"
fi

for ep in "${EPISODES[@]}"; do
    if [ -f "$OUT/${ep}_multi.summary.json" ]; then
        echo "$ep: already saved, skipping"
        continue
    fi
    if on_board; then
        waited=0
        while t=$(temp); ! .venv/bin/python -c "import sys; sys.exit(0 if $t <= $base + $MARGIN_C else 1)"; do
            [ "$waited" -ge "$MAX_WAIT_S" ] && break
            echo "$ep: chip at $t C, cooling to $base + $MARGIN_C C (waited $waited s)"
            sleep 30
            waited=$((waited + 30))
        done
        start_lanes "$ep" || { .venv/bin/python -m bench.board stop >/dev/null; exit 2; }
        note "$ep" before "$t" "$waited"
    fi
    # ticks of an interrupted attempt are kept under another name, never appended to
    [ -f "$OUT/${ep}_multi.ticks.jsonl" ] && mv "$OUT/${ep}_multi.ticks.jsonl" "$OUT/${ep}_multi.ticks.interrupted-$(date +%Y%m%dT%H%M%S).jsonl"
    echo "=== $ep  started $(date +%Y-%m-%dT%H:%M:%S%z)  tick ${TICK_S}s  backend $BACKEND" | tee "$OUT/${ep}_multi.log"
    PYTHONUNBUFFERED=1 systemd-inhibit --what=sleep:idle --why="FieldMind $ep" \
        .venv/bin/python run_demo.py --backend "$BACKEND" --arch multi \
        --overlay configs/fast.yaml --mode realtime --tick-s "$TICK_S" \
        --episode "$ep" --live-ticks "$OUT/${ep}_multi.ticks.jsonl" --live-print \
        --tag "$ep" --out "$OUT/tmp" 2>&1 | tee -a "$OUT/${ep}_multi.log"
    rc=${PIPESTATUS[0]}
    if on_board; then
        note "$ep" after "$(temp)"
        .venv/bin/python -m bench.board stop >/dev/null
    fi
    runs="$OUT/tmp/runs_${BACKEND}_$ep.json"
    if [ "$rc" -ne 0 ] || [ ! -s "$runs" ]; then
        echo "$ep did not finish (exit $rc): stopping here. Run the same command again to resume." >&2
        exit 1
    fi
    .venv/bin/python bench/realtime_summary.py "$runs" > "$OUT/${ep}_multi.realtime.json"
    gzip -c "$runs" > "$OUT/${ep}_multi.run.json.gz" && rm "$runs"
    mv "$OUT/tmp/summary_${BACKEND}_$ep.json" "$OUT/${ep}_multi.summary.json"
    echo "$ep: saved"
done
rmdir "$OUT/tmp" 2>/dev/null
echo "all presentation episodes are saved in $OUT"
