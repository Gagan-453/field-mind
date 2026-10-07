"""bench/board.py's bev-decide lane: the launch command, and the rule that only
recorded files with a matching board sha256 are started (as for CANDIDATES)."""
import subprocess

import pytest

from bench import board

MODEL = "bev-decider-0.4B-backbone-Q8_0.gguf"


def test_bev_command_env_ctx_port_and_offload():
    lib = "/data/local/tmp/llm/llama.cpp/lib"
    npu, cpu = board.bev_command(MODEL), board.bev_command("backbone-16bit.gguf", "cpu", threads=6)
    for cmd in (npu, cpu):
        assert f"LD_LIBRARY_PATH={lib} " in cmd and f"ADSP_LIBRARY_PATH={lib} " in cmd
        assert " -c 4096 " in cmd and "--port 8082" in cmd
        assert "--head /data/local/tmp/llm/bev_head.json" in cmd and "./bin/bev-decide " in cmd
    assert npu.endswith("--device HTP0 -ngl 99")
    assert cpu.endswith("--device none -t 6") and "HTP0" not in cpu
    with pytest.raises(ValueError):
        board.bev_command(MODEL, "gpu")


def _fake_adb(sha_for):
    calls = []

    def fake(*args, serial="", timeout=60):
        calls.append(args)
        last = args[-1]
        out = ""
        if "sha256sum" in last:
            path = last.split()[-1]
            out = f"{sha_for(path)}  {path}\n"
        return subprocess.CompletedProcess(args, 0, out, "")
    return fake, calls


def _launched(calls):
    return any("bev-decide" in a[-1] and "nohup" in a[-1] for a in calls)


def test_nothing_starts_while_the_build_sha256s_are_not_recorded(monkeypatch):
    """Whatever is recorded in bench/board.py today: a missing value refuses."""
    fake, calls = _fake_adb(lambda p: "a" * 64)
    monkeypatch.setattr(board, "_adb", fake)
    for missing in ("bev-decider-0.4B-backbone-Q8_0.gguf", "bev_head.bin", "bev_head.json", "binary"):
        _record(monkeypatch)
        if missing == "binary":
            monkeypatch.setattr(board, "BEV_BINARY_SHA256", None)
        else:
            monkeypatch.setitem(board.BEV_FILES, missing, None)
        with pytest.raises(board.ModelNotAllowed, match="no recorded sha256"):
            board.start_bev(MODEL)
        assert not _launched(calls), missing


def test_a_file_that_is_not_a_bev_model_is_refused(monkeypatch):
    fake, calls = _fake_adb(lambda p: "a" * 64)
    monkeypatch.setattr(board, "_adb", fake)
    with pytest.raises(board.ModelNotAllowed):
        board.start_bev("Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf")
    assert not _launched(calls)


def _record(monkeypatch):
    shas = {"bev-decider-0.4B-backbone-Q8_0.gguf": "1" * 64, "backbone-16bit.gguf": "2" * 64,
            "bev_head.bin": "3" * 64, "bev_head.json": "4" * 64}
    monkeypatch.setattr(board, "BEV_FILES", shas)
    monkeypatch.setattr(board, "BEV_BINARY_SHA256", "5" * 64)
    by_path = {f"/data/local/tmp/llm/{k}": v for k, v in shas.items()}
    by_path["/data/local/tmp/llm/llama.cpp/bin/bev-decide"] = "5" * 64
    return by_path


def test_a_wrong_sha256_on_any_file_refuses_and_the_right_ones_start(monkeypatch):
    by_path = _record(monkeypatch)
    needed = [p for p in by_path if not p.endswith("backbone-16bit.gguf")]   # not loaded with the Q8_0 model
    assert len(needed) == 4
    for bad in needed:
        fake, calls = _fake_adb(lambda p, bad=bad: "f" * 64 if p == bad else by_path[p])
        monkeypatch.setattr(board, "_adb", fake)
        with pytest.raises(board.ModelNotAllowed):
            board.start_bev(MODEL)
        assert not _launched(calls), bad
    fake, calls = _fake_adb(lambda p: by_path[p])
    monkeypatch.setattr(board, "_adb", fake)
    info = board.start_bev(MODEL)
    assert _launched(calls) and info["url"] == "http://localhost:8082"
    assert ("forward", "tcp:8082", "tcp:8082") in calls


def test_stop_bev_kills_only_bev_decide(monkeypatch):
    fake, calls = _fake_adb(lambda p: "")
    monkeypatch.setattr(board, "_adb", fake)
    board.stop_bev()
    assert calls == [("shell", "pkill bev-decide; sleep 1; pgrep -l bev-decide")]
