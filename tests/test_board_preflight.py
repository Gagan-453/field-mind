"""bench/board_preflight.py: the checks that stop a board session before it
measures anything with a lane that is not what it should be."""

import json
from types import SimpleNamespace

from bench import board_preflight as bp

L = bp.LLAMA


def R(text="OK", model=f"/data/local/tmp/llm/{L}", backend="npu", status="ok"):
    return SimpleNamespace(text=text, model=model, backend=backend, status=status, error="")


def test_a_good_reply_passes():
    assert bp.check_reply(R(), "npu") == []
    assert bp.check_reply(R(backend="cpu"), "cpu") == []


def test_wrong_model_wrong_backend_failed_or_empty_reply_are_caught():
    assert any("model" in p for p in bp.check_reply(R(model="/x/gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf"), "cpu"))
    assert any("backend" in p for p in bp.check_reply(R(backend="npu"), "cpu"))
    assert any("status" in p for p in bp.check_reply(R(status="timeout"), "npu"))
    assert any("empty" in p for p in bp.check_reply(R(text="  "), "npu"))


NPU_LOG = (f"llama_model_loader: loaded meta data from /data/local/tmp/llm/{L}\n"
           "load_tensors: offloaded 29/29 layers to GPU\n"
           "load_tensors:         HTP0 model buffer size =  1911.90 MiB\n")
CPU_LOG = (f"llama_model_loader: loaded meta data from /data/local/tmp/llm/{L}\n"
           "load_tensors: offloaded 0/29 layers to GPU\n")


def test_lane_logs_prove_placement():
    assert bp.check_lane_log("npu", NPU_LOG) == []
    assert bp.check_lane_log("cpu", CPU_LOG) == []
    assert bp.check_lane_log("npu", NPU_LOG.replace("29/29", "20/29"))              # partial offload
    assert bp.check_lane_log("npu", NPU_LOG.replace("1911.90", "0.00"))             # no HTP0 memory
    assert bp.check_lane_log("cpu", NPU_LOG)                                         # CPU lane on HTP0
    assert bp.check_lane_log("cpu", CPU_LOG + "load_tensors: HTP0 model buffer size = 12.00 MiB\n")
    assert bp.check_lane_log("npu", NPU_LOG.replace(L, "gemma.gguf"))               # another file
    assert bp.check_lane_log("npu", "nothing useful")


def test_meminfo_and_rss_parsing():
    m = bp.parse_meminfo("MemTotal:       15728640 kB\nMemFree:  100 kB\nMemAvailable:    6291456 kB\nCached: 1 kB\n")
    assert m == {"MemTotal_kB": 15728640, "MemFree_kB": 100, "MemAvailable_kB": 6291456}
    assert bp.parse_rss("8080 VmRSS:   489012 kB\n8081 VmRSS:  2001234 kB\n") == {8080: 489012, 8081: 2001234}


def _run(envs, text=()):
    return {"assessments": [{"tick": 5, "envelopes": envs,
                             "multi": {"text": [{"envelope": e} for e in text]}}]}


def E(agent, backend, model=f"/data/local/tmp/llm/{L}", status="ok"):
    return {"agent": agent, "backend": backend, "model": model, "calls": [{"status": status}]}


def test_saved_runs_must_report_the_model_and_the_placed_lane():
    good = _run([E("diagnostician", "npu"), E("verifier", "cpu")], [E("text_reader", "cpu")])
    assert bp.check_run_models(good, "multi") == []
    assert bp.check_run_models(_run([E("diagnostician", "cpu")]), "multi")           # wrong lane
    assert bp.check_run_models(_run([E("verifier", "cpu", model="gemma.gguf")]), "multi")
    assert bp.check_run_models(_run([], [E("text_reader", "npu")]), "multi")
    assert bp.check_run_models(_run([E("diagnostician", "npu", status="error")]), "multi")
    assert bp.check_run_models(_run([E("diagnostician", "npu"), E("verifier", "npu")]), "single") == []
    assert bp.check_run_models(_run([E("diagnostician", "cpu")]), "single")


def test_runs_cli_exit_code(tmp_path):
    import gzip
    import subprocess
    import sys
    f = tmp_path / "r.run.json.gz"
    f.write_bytes(gzip.compress(json.dumps(_run([E("diagnostician", "cpu")])).encode()))
    r = subprocess.run([sys.executable, "-m", "bench.board_preflight", "runs", "multi", str(f)],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "problems" in r.stdout
