#!/usr/bin/env bash
# Build bev-decide for the QIDK in the SAME container as the board's llama.cpp
# (ghcr.io/snapdragon-toolchain/arm64-android:v0.7, NDK from the image,
# android-34, arm64-v8a: docs/backend/snapdragon/CMakeUserPresets.json at
# llama.cpp 99b95488), linked against the installed package that is on the board.
#
#   device/bev_decide/build_android.sh <llama_src> <llama_pkg>
#
#   <llama_src>  llama.cpp checkout at commit 99b95488 (for vendor/nlohmann)
#   <llama_pkg>  the installed package pushed to the board (has include/ and
#                lib/); if unsure, take the board's own copy:
#                  adb pull /data/local/tmp/llm/llama.cpp <dir>
#
# Output: build-bev-android/bev-decide (repo root). Push it next to llama-server:
#   adb push build-bev-android/bev-decide /data/local/tmp/llm/llama.cpp/bin/
# and compare sha256 on both sides (project rule).
# ENGINE=docker to use docker instead of podman.
set -euo pipefail
unset PYTHONPATH
[ $# -eq 2 ] || { sed -n '2,20p' "$0"; exit 2; }
SRC=$(cd "$1" && pwd)
PKG=$(cd "$2" && pwd)
REPO=$(cd "$(dirname "$0")/../.." && pwd)
ENGINE=${ENGINE:-podman}
IMAGE=ghcr.io/snapdragon-toolchain/arm64-android:v0.7

commit=$(git -C "$SRC" rev-parse HEAD 2>/dev/null || echo unknown)
case "$commit" in
  99b95488*) ;;
  *) echo "STOP: $SRC is at commit $commit, not 99b95488 (the board's llama.cpp)"; exit 3 ;;
esac
for f in include/llama.h lib/libllama.so lib/libggml.so lib/libggml-base.so; do
  [ -e "$PKG/$f" ] || { echo "STOP: $PKG/$f missing (not an installed llama.cpp package)"; exit 3; }
done

"$ENGINE" run --rm -u "$(id -u):$(id -g)" --platform linux/amd64 \
  -v "$REPO":/repo -v "$SRC":/llama:ro -v "$PKG":/pkg:ro "$IMAGE" \
  bash -lc 'cmake -S /repo/device/bev_decide -B /repo/build-bev-android \
              -DCMAKE_TOOLCHAIN_FILE="$ANDROID_NDK_ROOT/build/cmake/android.toolchain.cmake" \
              -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-34 \
              -DCMAKE_BUILD_TYPE=Release -DLLAMA_PKG=/pkg -DLLAMA_SRC=/llama \
            && cmake --build /repo/build-bev-android -j'

out="$REPO/build-bev-android/bev-decide"
echo "built: $out"
echo "sha256: $(sha256sum "$out" | cut -d' ' -f1)"
