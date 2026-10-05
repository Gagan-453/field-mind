#!/usr/bin/env bash
# One multi-agent episode on the board with the live stage monitor in THIS
# window. Nothing is saved: no benchmark files, no results/ folder. The
# multi-agent counterpart of scripts/presentation_run.sh without --save-run.
#
#     scripts/monitor_multi.sh ep_A01_fcv_seize              # ticks back to back
#     TICK_S=30 scripts/monitor_multi.sh ep_A01_fcv_seize    # real time, a tick every 30 s
#
# It starts both lanes fresh (configs/fast.yaml: Llama 3.2 3B on the NPU, Gemma
# 3 1B on the CPU, answer grammars on), runs the episode in the background into
# a temporary folder, and shows bench/stage_monitor_multi.py on top of it.
# Ctrl-C closes the monitor, stops the run and the lanes, and deletes the
# temporary folder. When the episode ends the monitor says FINISHED and stays
# up until Ctrl-C. An episode id starting with dev_ is read from data/episodes_dev.
# BACKEND=mock tries the script on the laptop without the board.
set -uo pipefail
cd "$(dirname "$0")/.."
unset PYTHONPATH
NPU_MODEL=Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf
CPU_MODEL=gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf
BACKEND=${BACKEND:-llamaserver}
ep=${1:?usage: scripts/monitor_multi.sh <episode id>   (TICK_S=30 in front for real time)}
on_board() { [ "$BACKEND" = llamaserver ]; }

if on_board && pgrep -f '[p]ython -m bench.campaign all|[p]resentation_multi_all.sh|[b]enchmark_multi_lockstep_all.sh|[r]un_demo.py .*--backend llamaserver|[s]tage_monitor.py' >/dev/null; then
    echo "another board run is going: wait for it or stop it first (one thing on the board at a time)" >&2
    exit 1
fi

TMP=$(mktemp -d /tmp/fieldmind_monitor_XXXXXX)
run_pid=""
cleanup() {
    trap - EXIT INT TERM
    [ -n "$run_pid" ] && kill "$run_pid" 2>/dev/null
    on_board && .venv/bin/python -m bench.board stop >/dev/null 2>&1
    rm -rf "$TMP"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

if on_board; then
    .venv/bin/python -m bench.board stop >/dev/null
    for lane in npu cpu; do
        model=$NPU_MODEL; [ "$lane" = cpu ] && model=$CPU_MODEL
        echo "starting the $lane lane ($model) ..."
        .venv/bin/python -m bench.board start "$lane" "$model" > "$TMP/lane_$lane.json" \
            && grep -q '"ready_after_s": [0-9]' "$TMP/lane_$lane.json" \
            || { echo "the $lane lane did not come up:"; cat "$TMP/lane_$lane.json"; exit 2; }
    done
    # NPU: a nonzero HTP0 buffer; CPU: none
    if ! .venv/bin/python -m bench.board log npu | grep -q "HTP0 model buffer size = *[1-9]" \
        || .venv/bin/python -m bench.board log cpu | grep -q "HTP0 model buffer"; then
        echo "lane placement is not as expected (NPU with an HTP0 buffer, CPU with none)" >&2
        exit 2
    fi
fi

mode=(--mode lockstep)
[ -n "${TICK_S:-}" ] && mode=(--mode realtime --tick-s "$TICK_S")
dir=()
case "$ep" in dev_*) dir=(--episodes-dir data/episodes_dev) ;; esac
ticks="$TMP/${ep}_multi.ticks.jsonl"
(
    PYTHONUNBUFFERED=1 .venv/bin/python run_demo.py --backend "$BACKEND" --arch multi \
        --overlay configs/fast.yaml "${mode[@]}" "${dir[@]}" --episode "$ep" \
        --live-ticks "$ticks" --tag "$ep" --out "$TMP/out" > "$TMP/run.log" 2>&1
    rc=$?
    # tells the monitor the episode is over (it shows FINISHED)
    [ $rc -eq 0 ] && touch "$TMP/${ep}_multi.summary.json"
    exit $rc
) &
run_pid=$!

# the monitor needs the first tick on disk
for _ in $(seq 1 300); do
    [ -s "$ticks" ] && break
    if ! kill -0 "$run_pid" 2>/dev/null; then
        echo "the run stopped before its first tick:" >&2
        tail -20 "$TMP/run.log" >&2
        exit 1
    fi
    sleep 0.1
done
[ -s "$ticks" ] || { echo "no tick after 30 s:" >&2; tail -20 "$TMP/run.log" >&2; exit 1; }

poll=()
on_board || poll=(--no-poll)
.venv/bin/python bench/stage_monitor_multi.py --dir "$TMP" --episode "$ep" \
    --tick-s "${TICK_S:-30}" "${poll[@]}"
