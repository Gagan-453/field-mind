"""bev_convert.py output -> bev_decide.cpp's load_head -> the head: the whole
host-side path the board will take, against the pure-Python head of
tests/test_bev_core.py. Needs llama.cpp's headers (bev_decide.cpp includes
llama.h and vendor/nlohmann/json.hpp): set BEV_LLAMA_SRC to a llama.cpp
checkout at commit 99b95488. Skipped otherwise. Nothing from llama.cpp is
called, so its library is not linked (unresolved symbols are allowed).
"""
import hashlib
import json
import os
import random
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import test_bev_convert as tc          # noqa: E402  (the miniature checkpoint)
import test_bev_core as tk             # noqa: E402  (the Python head)
from bench import bev_convert as bc    # noqa: E402

LLAMA = os.environ.get("BEV_LLAMA_SRC")
SRC = Path(__file__).resolve().parent.parent / "device" / "bev_decide"

pytestmark = pytest.mark.skipif(
    not LLAMA or shutil.which("c++") is None,
    reason="set BEV_LLAMA_SRC to a llama.cpp checkout (and have a C++ compiler)")

MAIN = r'''
#define main bev_decide_main
#include "bev_decide.cpp"
#undef main
int main(int, char ** argv) {
    bev::Head h; bev::EncodingConsts c;
    load_head(argv[1], h, c);
    int task, C; std::cin >> task >> C;
    std::vector<std::vector<float>> ch(C, std::vector<float>(h.H));
    for (auto & r : ch) for (auto & z : r) std::cin >> z;
    std::vector<float> a(h.H); for (auto & z : a) std::cin >> z;
    std::cout.precision(17);
    std::cout << c.answer_prompt << "\n" << c.task_prompts["choice"] << "\n"
              << c.max_state_tokens << " " << c.max_choice_tokens << " " << h.eps << "\n";
    for (double p : h.forward(ch, a, task)) std::cout << p << "\n";
}
'''


@pytest.fixture(scope="module")
def loader(tmp_path_factory):
    d = tmp_path_factory.mktemp("loader")
    (d / "main.cpp").write_text(MAIN)
    allow = ["-Wl,-undefined,dynamic_lookup"] if sys.platform == "darwin" \
        else ["-Wl,--unresolved-symbols=ignore-all"]
    L = Path(LLAMA)
    subprocess.run(["c++", "-std=c++17", "-O2", f"-I{SRC}", f"-I{L / 'include'}",
                    f"-I{L / 'ggml' / 'include'}", f"-I{L / 'vendor'}", str(d / "main.cpp"),
                    "-o", str(d / "loader")] + allow, check=True, capture_output=True)
    return d / "loader"


def test_split_output_loads_and_runs_like_the_python_head(loader, tmp_path):
    d, _ = tc._mini(tmp_path)
    out = tmp_path / "out"
    bc.split(d, out, expect_sha256=hashlib.sha256((d / "model.safetensors").read_bytes()).hexdigest())
    # the miniature's random bytes are not sane floats: give the head real values
    m = json.loads((out / "bev_head.json").read_text())
    blob = bytearray((out / "bev_head.bin").read_bytes())
    rng, w = random.Random(11), {}
    for name, t in m["tensors"].items():
        n = t["nbytes"] // 4
        vals = [rng.gauss(0, 0.5) for _ in range(n)]
        if name.endswith("weight") and "norm" in name:
            vals = [1 + 0.2 * v for v in vals]
        raw = struct.pack(f"<{n}f", *vals)
        blob[t["offset"]:t["offset"] + t["nbytes"]] = raw
        w[name] = (list(struct.unpack(f"<{n}f", raw)), t["shape"])
    (out / "bev_head.bin").write_bytes(bytes(blob))

    for task, C, seed in [(0, 3, 4), (1, 2, 5), (2, 5, 6)]:
        choices, answer = tk._inputs(seed, C)
        nums = f"{task} {C} " + " ".join(repr(z) for r in choices for z in r) \
            + " " + " ".join(repr(z) for z in answer)
        lines = subprocess.run([str(loader), str(out / "bev_head.json")], input=nums.encode(),
                               capture_output=True, check=True).stdout.decode().splitlines()
        assert lines[0] == "The answer is:"
        assert lines[1] == "Choose the best option."
        assert lines[2].split() == ["2048", "64", "1.0000000000000001e-05"]
        got = [float(x) for x in lines[3:]]
        want = tk._ref_head(w, choices, answer, task)
        assert max(abs(a - b) for a, b in zip(got, want)) < 1e-12
