#!/usr/bin/env bash
# bev-decider's backbone -> GGUF, for bev-decide on the board (reports/bev_decider.md,
# Part C step 2). Run on the QIDK laptop after `git lfs pull` in the model folder.
#
#   device/bev_decide/build_gguf.sh <bev-decider-0.4B dir>
#
# 1. bench/bev_convert.py splits the checkpoint: a plain Qwen3 folder
#    (backbone/) and the head (bev_head.bin + bev_head.json).
# 2. llama.cpp's convert_hf_to_gguf.py (the pinned checkout, venv-convert):
#    backbone/ -> 16-bit GGUF (bf16 stays bf16), kept for the CPU conformance run.
# 3. llama-quantize --pure Q8_0: EVERY matrix Q8_0, token embedding included
#    (DECISION, reports/bev_decider.md: Q8_0 rather than the lanes' Q4_0 recipe;
#    plan rule allows only Q4_0 or Q8_0 on HTP; a 0.4B decision model is the
#    one place the extra precision is cheap). There is no output.weight: the
#    embeddings are tied and bev reads hidden states, not logits.
# 4. bench.gguf_types: every matrix must be Q8_0 (exit 3 otherwise).
#
# BUILD (default ~/fieldmind-build) holds llama.cpp (at 99b95488), build-host/
# bin/llama-quantize and venv-convert, as for bench/build_candidate_gguf.sh.
# Output: $BUILD/gguf/bev/ (backbone-16bit.gguf, bev-decider-0.4B-backbone-Q8_0.gguf,
# bev_head.bin, bev_head.json). Prints sizes and sha256 for bench.board.BEV_FILES.
set -euo pipefail
unset PYTHONPATH
[ $# -eq 1 ] || { sed -n '2,22p' "$0"; exit 2; }
SRC=$(cd "$1" && pwd)
REPO=$(cd "$(dirname "$0")/../.." && pwd)
BUILD=${BUILD:-$HOME/fieldmind-build}
LLAMA=$BUILD/llama.cpp
OUT=$BUILD/gguf/bev
mkdir -p "$OUT" "$REPO/logs"

commit=$(git -C "$LLAMA" rev-parse HEAD)
case "$commit" in
  99b95488*) ;;
  *) echo "STOP: $LLAMA is at $commit, not 99b95488 (the board's llama.cpp)"; exit 3 ;;
esac
echo "[$(date +%FT%T%z)] bev-decider: llama.cpp $commit"

# 1. split (refuses lfs pointers, a different file, any unexpected tensor)
"$REPO/.venv/bin/python" -m bench.bev_convert "$SRC" "$OUT/split" | tee "$REPO/logs/bev_split.log"

# 2. 16-bit GGUF
"$BUILD/venv-convert/bin/python" "$LLAMA/convert_hf_to_gguf.py" "$OUT/split/backbone" \
    --outtype auto --outfile "$OUT/backbone-16bit.gguf" > "$REPO/logs/bev_convert_gguf.log" 2>&1

# 3. Q8_0 everywhere
"$LLAMA/build-host/bin/llama-quantize" --pure "$OUT/backbone-16bit.gguf" \
    "$OUT/bev-decider-0.4B-backbone-Q8_0.gguf" Q8_0 > "$REPO/logs/bev_quantize.log" 2>&1

# 4. every matrix Q8_0
"$REPO/.venv/bin/python" -m bench.gguf_types "$OUT/bev-decider-0.4B-backbone-Q8_0.gguf" \
    > "$REPO/logs/bev_gguf_types.log"
grep -E '"(type_counts|Q8_0|Q4_0|F16|BF16|F32|verdict)"' "$REPO/logs/bev_gguf_types.log" || true
grep -q '"verdict": "OK' "$REPO/logs/bev_gguf_types.log" || { echo "STOP: a matrix is not Q8_0"; exit 3; }

cp "$OUT/split/bev_head.bin" "$OUT/split/bev_head.json" "$OUT/"
for f in backbone-16bit.gguf bev-decider-0.4B-backbone-Q8_0.gguf bev_head.bin bev_head.json; do
  echo "$f  $(stat -c %s "$OUT/$f") B  $(sha256sum "$OUT/$f" | cut -d' ' -f1)"
done
