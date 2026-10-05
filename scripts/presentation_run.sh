#!/usr/bin/env bash
# One single-agent episode on the board WITH the live stage display, saved into
# results/presentation_benchmark/. Run from the repo root, in a real terminal:
#
#     scripts/presentation_run.sh ep_A01_fcv_seize
#
# It starts a fresh Llama 3.2 3B NPU lane (same flags as the campaign:
# -c 4096 -np 1 -fit off --cache-ram 0 -lv 4), then runs bench/stage_monitor.py.
# Extra arguments go to the monitor, e.g. --max-ticks 18 or --plain.
set -uo pipefail
cd "$(dirname "$0")/.."
unset PYTHONPATH
MODEL=Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf
OUT=results/presentation_benchmark/single_agent_llama32-3b
ep=${1:?usage: scripts/presentation_run.sh <episode id> [monitor args]}
shift
if pgrep -f '[p]ython -m bench.campaign all' >/dev/null; then
    echo "the campaign is running: stop it first (one thing on the board at a time)" >&2
    exit 1
fi
mkdir -p "$OUT"
.venv/bin/python -m bench.board stop >/dev/null
echo "starting the NPU lane ($MODEL) ..."
.venv/bin/python -m bench.board start npu "$MODEL" > logs/presentation_lane_start.json || { cat logs/presentation_lane_start.json; exit 2; }
grep -q '"ready_after_s": [0-9]' logs/presentation_lane_start.json || { echo "lane did not come up:"; cat logs/presentation_lane_start.json; exit 2; }
.venv/bin/python bench/stage_monitor.py --episode "$ep" --backend llamaserver \
    --model-file "$MODEL" --save-run --out "$OUT" "$@"
rc=$?
# every result file carries the suffix _single (the multi-agent's carry _multi),
# so a file copied out of its folder still says which agent made it
for f in "$OUT/$ep".*; do
    [ -f "$f" ] && mv "$f" "$OUT/${ep}_single${f#"$OUT/$ep"}"
done
for f in "$OUT"/stage_timing_"$ep"_*.txt; do
    case "$f" in *_single.txt) ;; *) [ -f "$f" ] && mv "$f" "${f%.txt}_single.txt" ;; esac
done
.venv/bin/python -m bench.board stop >/dev/null
exit $rc
