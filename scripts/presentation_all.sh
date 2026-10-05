#!/usr/bin/env bash
# The remaining presentation episodes, one after another, each with the live
# stage display. Run from the repo root, in a real terminal:
#
#     scripts/presentation_all.sh
#
# Shortest first. An episode that already has <ep>_single.summary.json is skipped, so
# the same command resumes after Ctrl-C (the interrupted episode starts over).
# Chip temperature is logged before and after every episode (temps_single.jsonl) and
# the next episode waits until the chip is within 5 C of the reading taken at
# the start of this batch, for at most 900 s (the campaign's margin and limit).
set -uo pipefail
cd "$(dirname "$0")/.."
unset PYTHONPATH
OUT=results/presentation_benchmark/single_agent_llama32-3b
EPISODES=(ep_A01_fcv_seize ep_C01_wet_coal ep_B01_tube_leak ep_D01_high_cv_coal ep_E01_fouling_drift)
MARGIN_C=5
MAX_WAIT_S=900

temp() {   # prints the hottest of the CPU and NPU zones
    .venv/bin/python -m bench.board temp | .venv/bin/python -c \
        'import json,sys; d=json.load(sys.stdin); print(max(d["cpu_max_c"], d["npu_max_c"]))'
}
note() {   # note <episode> <when> <temp> [waited_s]
    printf '{"episode": "%s", "when": "%s", "t": "%s", "max_c": %s, "cool_wait_s": %s}\n' \
        "$1" "$2" "$(date +%Y-%m-%dT%H:%M:%S%z)" "$3" "${4:-null}" >> "$OUT/temps_single.jsonl"
}

mkdir -p "$OUT"
.venv/bin/python -m bench.board stop >/dev/null
base=$(temp) || { echo "cannot read the board temperature (is it plugged in?)" >&2; exit 2; }
note batch start "$base"
echo "batch start: chip at $base C"

for ep in "${EPISODES[@]}"; do
    if [ -f "$OUT/${ep}_single.summary.json" ]; then
        echo "$ep: already saved, skipping"
        continue
    fi
    waited=0
    while t=$(temp); ! .venv/bin/python -c "import sys; sys.exit(0 if $t <= $base + $MARGIN_C else 1)"; do
        [ "$waited" -ge "$MAX_WAIT_S" ] && break
        echo "$ep: chip at $t C, cooling to $base + $MARGIN_C C (waited $waited s)"
        sleep 30
        waited=$((waited + 30))
    done
    note "$ep" before "$t" "$waited"
    scripts/presentation_run.sh "$ep"
    rc=$?
    note "$ep" after "$(temp)"
    if [ $rc -ne 0 ] || [ ! -f "$OUT/${ep}_single.summary.json" ]; then
        echo "$ep did not finish (exit $rc): stopping here. Run scripts/presentation_all.sh again to resume." >&2
        exit 1
    fi
    echo "$ep: saved"
done
echo "all presentation episodes are saved in $OUT"
